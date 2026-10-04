# advancedQrCodeGenerator
Python GUI for advanced QR code generation using the `qrcode` module.

> [!WARNING]
> This repo is WIP and the script is not optimized or prepared for public use. I just wanted to share it among friends.

Check some QR codes in the `examples` section of the [`qrcode`][qrcode] module to see what it can do.

## Requirements
- Python **3.11 or newer** with `tkinter` (included in the official
  Windows and macOS installers; on Linux install e.g. `python3-tk`)
- [`qrcode`][qrcode] **8.2 or newer within 8.x** (`>=8.2,<9`)
- [`pillow`](https://pypi.org/project/pillow/) **10.0 or newer**

The Python packages are installed automatically by the steps below.

## Installation

### For users
No git needed: pip downloads the code straight from GitHub and installs
it together with its dependencies.

Windows:

```bash
py -m pip install --user https://github.com/GiovanniKl/advancedQrCodeGenerator/archive/refs/heads/main.zip
```

macOS / Linux:

```bash
python3 -m pip install --user https://github.com/GiovanniKl/advancedQrCodeGenerator/archive/refs/heads/main.zip
```

To update, run the same command again.

> [!TIP]
> If you have [`pipx`](https://pipx.pypa.io), use
> `pipx install <the URL above>` instead. It keeps the app in its own
> isolated environment, so it can't clash with other Python packages.
> On recent Linux distributions (Debian, Ubuntu, Fedora, …) plain
> `pip install --user` is blocked with an "externally-managed-environment"
> error. Use pipx there.

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
Start the app with

```bash
py -m aqrgen
```

(`python3 -m aqrgen` on macOS / Linux, `python -m aqrgen` inside an
activated virtual environment). This always works. The shorter
`aqrgen` command works too if pip's scripts folder is on your PATH
(always the case with pipx or inside a virtual environment).

- The **preview** on the right updates as you type. If an input is
  invalid, the preview shows what's wrong.
- **Browse…** buttons pick the save folder and image files.
- **Generate** (or Ctrl+Enter) saves the QR code; generating runs in
  the background, so the window stays responsive.
- Embedding an image needs the highest error correction, so ticking
  "Embed an image" selects H automatically. SVG output only supports
  square, black and white modules, so the style options are locked
  while SVG is selected.
- Colors can be written as `(255, 128, 0)` or `#ff8000`.
- **Presets** store all settings under a name: type a name in the
  presets box and click **Save**; pick one from the dropdown and click
  **Load**. **Open folder** shows where they are stored:

  | OS | Presets folder |
  |---|---|
  | Windows | `%APPDATA%\aqrgen\presets` |
  | macOS | `~/Library/Application Support/aqrgen/presets` |
  | Linux | `~/.config/aqrgen/presets` (or `$XDG_CONFIG_HOME/aqrgen/presets`) |

  Each preset is one `.json` file, so you can share a preset by sending
  the file and dropping it into a friend's presets folder. Presets
  from older versions (`.txt` files in a `presets` folder next to where
  you started the app) are imported automatically on first start; the
  old files are left untouched.

*Further instructions might be added in the future...*

## Development
- Code style: [Ruff](https://docs.astral.sh/ruff/) formatter and linter,
  80 characters per line, numpydoc docstrings with at most 72 characters
  per line. Configuration is in `pyproject.toml`.
- Tests: `pytest` (GUI tests are skipped automatically when Tk can't
  open a window).
- `pre-commit install` runs Ruff and numpydoc validation on every commit;
  `pre-commit run --all-files` runs them manually.
- GitHub Actions runs pre-commit and the tests on pushes to `main` and
  on pull requests: Python 3.11–3.14 on Ubuntu, 3.14 on Windows, and
  3.11 with the lowest allowed dependency versions. Start it manually
  for other branches from the Actions tab ("Run workflow").
- Package layout: `aqrgen/core.py` (QR generation, no GUI),
  `aqrgen/presets.py` (preset files), `aqrgen/gui.py` (tkinter GUI).
- Planned changes are tracked in [ROADMAP.md](ROADMAP.md).


[qrcode]:https://github.com/lincolnloop/python-qrcode
