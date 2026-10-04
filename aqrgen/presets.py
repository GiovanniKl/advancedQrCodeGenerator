"""Reading and writing of preset files.

A preset is a JSON file ``<name>.json`` in `PRESETS_DIR`, a per-user
folder (see `default_presets_dir`)::

    {
      "format_version": 1,
      "settings": {"message": "https://example.com", "version": 1, ...}
    }

Setting names are the variable names of the GUI. Older versions of the
app stored presets as ``<name>.txt`` files with ``key=value`` lines in
a ``presets`` folder in the working directory; `import_legacy_presets`
converts those.
"""

import dataclasses
import json
import locale
import os
import sys
from pathlib import Path

FORMAT_VERSION = 1
"""Version of the preset file format written by this module."""

FORBIDDEN_NAME_CHARS = set('<>:"/\\|?*')
"""Characters not allowed in preset names (invalid in file names)."""

LEGACY_DIR = Path("presets")
"""Folder of old ``.txt`` presets, relative to the working directory."""

LEGACY_KEYS = {
    "mess": "message",
    "savedir": "save_dir",
    "picname": "file_name",
    "collide": "on_collision",
    "size": "version",
    "errcor": "error_correction",
    "ext": "extension",
    "embim": "embed_image",
    "embimp": "embedded_image_path",
    "bgcolor": "back_color",
    "fcolor": "front_color",
    "boxsize": "box_size",
    "bdsize": "border",
    "boxstyle": "box_style",
    "cmask": "color_mask",
    "cmipath": "mask_image_path",
    "color2": "edge_color",
}
"""Keys of old ``.txt`` presets mapped to current setting names."""

IMPORT_LOG = ".imported-legacy-presets"
"""File in `PRESETS_DIR` listing the old preset files imported."""

_OLD_IMPORT_MARKER = ".imported-legacy-dirs"  # used by early versions


@dataclasses.dataclass
class LegacyImport:
    """Result of `import_legacy_presets`.

    Attributes
    ----------
    imported : list of tuple of str
        ``(old file name, new preset name)`` of every imported preset.
        The names differ when a preset with the old name already
        existed.
    failed : list of tuple of str
        ``(old file name, reason)`` of files that couldn't be read;
        they are tried again on the next start.
    """

    imported: list = dataclasses.field(default_factory=list)
    failed: list = dataclasses.field(default_factory=list)


def default_presets_dir():
    """Return the per-user presets folder of the current platform.

    Returns
    -------
    pathlib.Path
        ``%APPDATA%/aqrgen/presets`` on Windows,
        ``~/Library/Application Support/aqrgen/presets`` on macOS and
        ``$XDG_CONFIG_HOME/aqrgen/presets`` (default
        ``~/.config/aqrgen/presets``) elsewhere.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home() / "AppData/Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "aqrgen" / "presets"


PRESETS_DIR = default_presets_dir()
"""Folder with the preset files."""


def ensure_presets_dir():
    """Create `PRESETS_DIR` if it does not exist yet.

    Returns
    -------
    pathlib.Path
        The presets folder.
    """
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return PRESETS_DIR


def check_name(name):
    """Check that a preset name can be used as a file name.

    Parameters
    ----------
    name : str
        Preset name without extension.

    Raises
    ------
    ValueError
        If the name is empty, starts with a dot or contains characters
        that are not allowed in file names.
    """
    if not name.strip():
        raise ValueError("Please enter a preset name.")
    if name.startswith(".") or FORBIDDEN_NAME_CHARS & set(name):
        raise ValueError(
            f"Preset name {name!r} must not start with a dot or contain "
            "any of " + " ".join(sorted(FORBIDDEN_NAME_CHARS)) + "."
        )


def preset_path(name):
    """Return the path of the preset file with the given name.

    Parameters
    ----------
    name : str
        Preset name without extension.

    Returns
    -------
    pathlib.Path
        Path of the preset file (it may not exist).

    Raises
    ------
    ValueError
        If the name is not valid, see `check_name`.
    """
    check_name(name)
    return PRESETS_DIR / f"{name}.json"


def list_presets():
    """List the names of all saved presets.

    Returns
    -------
    list of str
        Preset names without extension, sorted alphabetically
        (ignoring case).
    """
    return sorted(
        (path.stem for path in ensure_presets_dir().glob("*.json")),
        key=str.casefold,
    )


def read_preset(name):
    """Read a preset file.

    Parameters
    ----------
    name : str
        Preset name without extension.

    Returns
    -------
    dict
        Setting names mapped to their values.

    Raises
    ------
    FileNotFoundError
        If no preset with this name exists.
    ValueError
        If the name is not valid or the file is not a valid preset.
    """
    path = preset_path(name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"{path.name} is not valid JSON ({err}).") from None
    if not isinstance(data, dict) or not isinstance(data.get("settings"), dict):
        raise ValueError(f"{path.name} is not an aqrgen preset.")
    return data["settings"]


def write_preset(name, settings):
    """Write a preset file, overwriting any existing one.

    Parameters
    ----------
    name : str
        Preset name without extension.
    settings : dict
        Setting names mapped to JSON-serializable values.

    Raises
    ------
    ValueError
        If the name is not valid, see `check_name`.
    """
    path = preset_path(name)
    ensure_presets_dir()
    data = {"format_version": FORMAT_VERSION, "settings": settings}
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def delete_preset(name):
    """Delete a preset file.

    Parameters
    ----------
    name : str
        Preset name without extension.

    Raises
    ------
    FileNotFoundError
        If no preset with this name exists.
    ValueError
        If the name is not valid, see `check_name`.
    """
    preset_path(name).unlink()


def read_legacy_preset(path):
    """Read an old ``.txt`` preset and convert it to current settings.

    Parameters
    ----------
    path : str or pathlib.Path
        Path of the ``.txt`` file.

    Returns
    -------
    dict
        Current setting names mapped to their values. Numbers and
        booleans are converted; values that fail to convert are kept
        as text. Unknown keys are dropped.
    """
    settings = {}
    for line in _read_legacy_text(path).splitlines():
        key, sep, value = line.partition("=")
        if sep and key in LEGACY_KEYS:
            settings[LEGACY_KEYS[key]] = _convert_legacy_value(key, value)
    return settings


def find_legacy_folder(folder):
    """Find old ``.txt`` presets in a folder or its ``presets`` folder.

    Parameters
    ----------
    folder : str or pathlib.Path
        The old presets folder, or the folder of the old app that
        contains it.

    Returns
    -------
    pathlib.Path or None
        The folder with the ``.txt`` files, or None if there are none.
    """
    for candidate in (Path(folder), Path(folder) / "presets"):
        if any(path.is_file() for path in candidate.glob("*.txt")):
            return candidate
    return None


def legacy_presets(legacy_dir):
    """Split the old presets of a folder into new and imported ones.

    Parameters
    ----------
    legacy_dir : str or pathlib.Path
        Folder with old ``.txt`` presets.

    Returns
    -------
    new : list of pathlib.Path
        Files not imported yet.
    imported : list of pathlib.Path
        Files imported before, according to `IMPORT_LOG`.
    """
    done = _imported_files()
    files = sorted(Path(legacy_dir).glob("*.txt"))
    return (
        [path for path in files if str(path.resolve()) not in done],
        [path for path in files if str(path.resolve()) in done],
    )


def import_legacy_presets(legacy_dir=None, again=False):
    """Convert old ``.txt`` presets to JSON presets.

    Each old file is imported once; `IMPORT_LOG` remembers which. If a
    preset with the same name already exists, the old one is imported
    as e.g. ``name 2``. The old files are left untouched. Files that
    can't be read are reported and tried again next time.

    Parameters
    ----------
    legacy_dir : str or pathlib.Path, optional
        Folder with old presets, `LEGACY_DIR` by default.
    again : bool, default False
        Also import files that were imported before.

    Returns
    -------
    LegacyImport
        What was imported and what failed.
    """
    result = LegacyImport()
    legacy_dir = Path(LEGACY_DIR if legacy_dir is None else legacy_dir)
    if not legacy_dir.is_dir():
        return result
    folder = ensure_presets_dir()
    (folder / _OLD_IMPORT_MARKER).unlink(missing_ok=True)
    log = folder / IMPORT_LOG
    done = set() if again else _imported_files()
    handled = []
    for path in sorted(legacy_dir.glob("*.txt")):
        key = str(path.resolve())
        if key in done:
            continue
        try:
            settings = read_legacy_preset(path)
        except OSError as err:
            result.failed.append((path.name, err.strerror or str(err)))
            continue
        name = _free_name(_usable_name(path.stem))
        write_preset(name, settings)
        result.imported.append((path.name, name))
        handled.append(key)
    if handled:
        with log.open("a", encoding="utf-8") as file:
            file.writelines(key + "\n" for key in handled)
    return result


def _imported_files():
    """Read the list of old preset files imported so far.

    Returns
    -------
    set of str
        Resolved paths from `IMPORT_LOG`.
    """
    log = PRESETS_DIR / IMPORT_LOG
    if not log.exists():
        return set()
    return set(log.read_text(encoding="utf-8").splitlines())


def _read_legacy_text(path):
    """Read an old preset file, whatever its encoding.

    Early versions saved presets in the system's default encoding,
    e.g. cp1250 on Czech Windows, not in UTF-8.

    Parameters
    ----------
    path : str or pathlib.Path
        Path of the ``.txt`` file.

    Returns
    -------
    str
        The file content.
    """
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", locale.getencoding()):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    return raw.decode("latin-1")  # never fails


def _usable_name(name):
    """Turn a file name into a valid preset name.

    Parameters
    ----------
    name : str
        Name of an old preset file without extension.

    Returns
    -------
    str
        The name with forbidden characters replaced by ``_`` and
        leading dots removed.
    """
    name = "".join("_" if c in FORBIDDEN_NAME_CHARS else c for c in name)
    return name.lstrip(".") or "imported"


def _free_name(name):
    """Return a preset name that isn't taken yet.

    Parameters
    ----------
    name : str
        Wanted name.

    Returns
    -------
    str
        The name itself, or ``name 2``, ``name 3``, … if it is taken.
    """
    candidate, number = name, 2
    while preset_path(candidate).exists():
        candidate, number = f"{name} {number}", number + 1
    return candidate


def _convert_legacy_value(key, value):
    """Convert a value of an old ``.txt`` preset to its proper type.

    Parameters
    ----------
    key : str
        Key in the old preset file.
    value : str
        Value as stored in the old preset file.

    Returns
    -------
    bool or int or str
        The converted value, or the text itself if it doesn't convert.
    """
    if key == "embim" and value in ("True", "False"):
        return value == "True"
    if key in ("size", "boxsize", "bdsize"):
        try:
            return int(value)
        except ValueError:
            pass
    return value
