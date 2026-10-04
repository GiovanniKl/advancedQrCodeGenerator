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

- The window has three columns: content, dimensions and colors on
  the left; styles, color mask and logo in the middle; the preview and
  the save options on the right. Presets are at the top.
- The **preview** updates as you type. If an input is invalid, the
  preview shows what's wrong. Enlarge the window to enlarge the preview
  (up to twice its normal size).
- **Browse…** buttons pick the save folder and image files.
- **Insert…** (next to the message) fills in the message from a form
  for a standard type that phones understand: Wi-Fi network (phones
  join it), contact card, e-mail, SMS, phone call, WhatsApp message,
  location, calendar event, Czech QR Platba or EU SEPA (EPC) payment.
  Inputs like IBANs, account numbers, dates and phone numbers are
  checked; a Czech account number (`19-2000145399/0800`) is converted
  to an IBAN automatically. The message box grows with longer messages
  and scrolls once it fills the column.
- **Generate** (Ctrl+Enter) saves the QR code; generating runs in
  the background, so the window stays responsive.
- **Copy PNG to clipboard** (Ctrl+Shift+Enter) copies the QR code as
  an image (as PNG also when SVG is selected), ready to paste into a
  document or chat. On Linux this needs `wl-clipboard` or `xclip`.
- Hover over the error correction options to see what L, M, Q and H
  mean.
- **Styles:** square, gapped square, rounded, circle, gapped circle and
  vertical/horizontal bars. The **eye style** sets the three corner
  squares separately (square eyes help scanners with fancy styles).
- **Colors:** background and face color, or a gradient (radial, square,
  horizontal, vertical) between the face color and a 2nd color, or an
  image as color mask. The **background opacity** goes from 100 %
  (opaque) down to 0 % (fully transparent), for PNG and SVG; the
  preview shows transparency as a checkerboard.
- **Logo:** tick "Embed an image" and pick an image; non-square logos
  keep their proportions. The logo size is set in % of the code width
  (25 % recommended; bigger logos can make the code unreadable).
  Embedding needs the highest error correction, so H is selected
  automatically.
- **SVG** output supports the square, gapped square, circle and gapped
  circle styles, solid colors, radial/horizontal/vertical gradients and
  logos. Options SVG can't do are greyed out while SVG is selected;
  your previous choice comes back when you switch to PNG.
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
