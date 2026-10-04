# advancedQrCodeGenerator
Python GUI for advanced QR code generation using the `qrcode` module.

> [!WARNING]
> This repo is WIP and the script is not optimized or prepared for public use. I just wanted to share it among friends.

Check some QR codes in the `examples` section of the [`qrcode`][qrcode] module to see what it can do.

## Requirements
- Python **3.11 or newer** with `tkinter` (included in the official
  Windows and macOS installers; on Linux install e.g. `python3-tk`)
- [`qrcode`][qrcode] **8.x** (`>=8.0,<9`)
- [`pillow`](https://pypi.org/project/pillow/) **10.0 or newer**

The Python packages are installed automatically by the steps below.

## Installation

### For users
The easiest way is [`pipx`](https://pipx.pypa.io) (or
[`uv`](https://docs.astral.sh/uv/)). It installs the app into its own
isolated environment and adds the `aqrgen` command, so you don't have
to manage a virtual environment yourself:

```bash
pipx install git+https://github.com/GiovanniKl/advancedQrCodeGenerator.git
```

or

```bash
uv tool install git+https://github.com/GiovanniKl/advancedQrCodeGenerator.git
```

### From a clone (for development)
```bash
git clone https://github.com/GiovanniKl/advancedQrCodeGenerator.git
cd advancedQrCodeGenerator
python -m venv .venv
```

Activate the virtual environment:

| OS | Command |
|---|---|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

Then install the app in editable mode together with the development
tools (needs pip 25.1 or newer, update with
`python -m pip install --upgrade pip`):

```bash
pip install -e . --group dev
pre-commit install
```

With `uv`, `uv sync` replaces the venv and pip steps (it creates `.venv`
itself and installs the dev tools too).

## Usage
Run

```bash
aqrgen
```

or `python -m aqrgen`. Presets are saved as `.txt` files in a `presets/`
folder in the directory you start the app from.

*Further instructions might be added in the future...*

## Development
- Code style: [Ruff](https://docs.astral.sh/ruff/) formatter and linter,
  80 characters per line, numpydoc docstrings with at most 72 characters
  per line. Configuration is in `pyproject.toml`.
- `pre-commit install` runs Ruff and numpydoc validation on every commit;
  `pre-commit run --all-files` runs them manually.
- Package layout: `aqrgen/core.py` (QR generation, no GUI),
  `aqrgen/presets.py` (preset files), `aqrgen/gui.py` (tkinter GUI).
- Planned changes are tracked in [ROADMAP.md](ROADMAP.md).


[qrcode]:https://github.com/lincolnloop/python-qrcode
