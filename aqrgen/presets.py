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

import json
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

_IMPORT_MARKER = ".imported-legacy-dirs"


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
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in LEGACY_KEYS:
            settings[LEGACY_KEYS[key]] = _convert_legacy_value(key, value)
    return settings


def import_legacy_presets(legacy_dir=None):
    """Convert old ``.txt`` presets to JSON presets, once per folder.

    A preset is skipped if a JSON preset with the same name already
    exists. The old files are left untouched. Each legacy folder is
    imported only once; later runs skip it.

    Parameters
    ----------
    legacy_dir : str or pathlib.Path, optional
        Folder with old presets, `LEGACY_DIR` by default.

    Returns
    -------
    list of str
        Names of the imported presets.
    """
    legacy_dir = Path(LEGACY_DIR if legacy_dir is None else legacy_dir)
    if not legacy_dir.is_dir():
        return []
    marker = ensure_presets_dir() / _IMPORT_MARKER
    done = (
        marker.read_text(encoding="utf-8").splitlines()
        if marker.exists()
        else []
    )
    key = str(legacy_dir.resolve())
    if key in done:
        return []
    imported = []
    for path in sorted(legacy_dir.glob("*.txt")):
        try:
            if preset_path(path.stem).exists():
                continue
            write_preset(path.stem, read_legacy_preset(path))
        except (OSError, UnicodeDecodeError, ValueError):
            continue  # unreadable file or unusable name: skip it
        imported.append(path.stem)
    with marker.open("a", encoding="utf-8") as file:
        file.write(key + "\n")
    return imported


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
