"""Reading and writing of preset files.

A preset is a plain text file ``<name>.txt`` in `PRESETS_DIR` with one
``<variable name>=<value>`` pair per line.
"""

from pathlib import Path

PRESETS_DIR = Path("presets")
"""Directory with preset files, relative to the working directory."""


def ensure_presets_dir():
    """Create `PRESETS_DIR` if it does not exist yet.

    Returns
    -------
    pathlib.Path
        The presets directory.
    """
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return PRESETS_DIR


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
    """
    return PRESETS_DIR / f"{name}.txt"


def list_presets():
    """List the names of all saved presets.

    Returns
    -------
    list of str
        Preset names without extension, sorted alphabetically.
    """
    return sorted(path.stem for path in ensure_presets_dir().glob("*.txt"))


def read_preset(name):
    """Read a preset file.

    Parameters
    ----------
    name : str
        Preset name without extension.

    Returns
    -------
    dict[str, str]
        Variable names mapped to their unparsed values, in file order.

    Raises
    ------
    FileNotFoundError
        If no preset with this name exists.
    """
    values = {}
    with preset_path(name).open(encoding="utf-8") as file:
        for line in file:
            key, sep, value = line.rstrip("\n").partition("=")
            if sep:
                values[key] = value
    return values


def write_preset(name, values):
    """Write a preset file, overwriting any existing one.

    Parameters
    ----------
    name : str
        Preset name without extension.
    values : dict
        Variable names mapped to values. Values are stored using
        `str`.
    """
    ensure_presets_dir()
    with preset_path(name).open("w", encoding="utf-8") as file:
        for key, value in values.items():
            file.write(f"{key}={value}\n")


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
    """
    preset_path(name).unlink()
