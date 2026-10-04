# Roadmap

Planned changes for this repo. Each item has an ID, so items can be
picked, discussed and ticked off one by one.

Legend: `[ ]` planned · `[x]` done · `[~]` partly done · `[-]` dropped

---

## Decisions

### D1 · GUI toolkit: stay on tkinter ✅

Stay on tkinter, with the GUI separated from the backend (done in A1).
Theming (e.g. `sv-ttk`) may be looked at later (E10).

For reference, if a switch is ever reconsidered: use **PySide6**
(LGPL, works with the MIT license, ~77 MB wheel). PyQt6 is GPL, and
PyQt5 is built on Qt 5, which is end-of-life.

### D2 · Dependency versions ✅

| Package | Requirement | Note |
|---|---|---|
| Python | `>=3.11` | develop on 3.14, test down to 3.11 (see D6) |
| `qrcode[pil]` | `>=8.0,<9` | develop on 8.2; capped below 9 to avoid API breaks |
| `pillow` | `>=10.0` | imported directly (`PIL.ImageTk` for E1) |

The code was verified on qrcode 8.2 + Pillow 12.3 (all box styles ×
color masks, embedded image, SVG). Upgrading from 7.3.1 makes these
available: `embedded_image_ratio`, passing a PIL image directly
(`embedded_image=`), SVG module drawers (`SvgCircleDrawer`,
`SvgPathImage`, `SvgFillImage`).

### D3 · Dependencies in `pyproject.toml` ✅

There is no `requirements.txt`. Runtime dependencies are in
`[project]`, dev tools in `[dependency-groups] dev`, and the `aqrgen`
command in `[project.scripts]`.

How users install it:
- **Users:** `pipx install git+…` or `uv tool install git+…`. These
  create a hidden isolated environment and put `aqrgen` on PATH, so
  users never deal with a venv themselves. Later, a standalone `.exe`
  (E9) can cover friends without Python.
- **Developers:** clone, then `.venv` + `pip install -e . --group dev`,
  or just `uv sync`.

### D4 · Ruff for formatting and linting, no Pylint ✅

Ruff runs as formatter and linter (80 characters per line, numpydoc
convention, 72 characters for docstrings and comments via W505).
numpydoc's validation hook checks that docstrings match the
signatures. Both run through pre-commit.

---

## A · Repo structure and code organization

- [x] **A1** Split the code into a package (flat layout, no `src/`):
  `aqrgen/core.py` (QR generation, `QrSettings` dataclass),
  `aqrgen/presets.py` (preset file IO), `aqrgen/gui.py` (tkinter),
  `aqrgen/__main__.py` (`python -m aqrgen`).
- [ ] **A2** Rename the GUI to PEP 8 names (`qrCodeGen` →
  `QrCodeGeneratorApp`, `optMngr0` → `_update_svg_state`, …). After
  that, remove the N801/N802 per-file ignores in `pyproject.toml`.
- [x] **A3** Added a `main()` function and an `if __name__ ==
  "__main__":` guard.
- [x] **A4** Replaced the `if/elif` chains with lookup dicts (in
  `core.py`).
- [ ] **A5** Stop toggling widgets by position
  (`svgrelatedwidgets[23]`) and use named widget groups. Split the
  200-statement `__init__` into builder methods (removes the PLR0915
  ignore).
- [ ] **A6** Convert the `gui.py` docstrings to numpydoc. Then remove
  the remaining per-file ignores and the numpydoc hook exclude in
  `.pre-commit-config.yaml`.

## B · Bugs and robustness

- [x] **B1** Crash on a fresh clone: `presets/` is now created when
  it's missing.
- [ ] **B2** "warn & abort" always aborts, even when the file name
  doesn't collide.
- [ ] **B3** When the save dir is empty and you answer "use current
  dir", the collision check is skipped and existing files are silently
  overwritten.
- [ ] **B4** Cancelling the color picker crashes (`hex2rgb(None)`).
- [ ] **B5** `eval()` runs on user input (colors and preset values in
  `gui.py`). Replace it with a proper RGB/hex parser.
- [x] **B6** Deleting a preset now uses `Path.unlink()` instead of
  `os.system("del …")` (Windows-only, open to shell injection).
- [ ] **B7** Presets and output paths depend on the current working
  directory. Resolve them relative to a user config dir instead (only
  `presets.PRESETS_DIR` needs to change).
- [ ] **B8** No input validation (version 1–40, border ≥ 4, box size
  > 0, RGB 0–255). Bad input gives a traceback in the console. Once
  this and an error dialog are done, switch `[project.scripts]` to
  `[project.gui-scripts]` (no console window on Windows).
- [ ] **B9** SVG + a non-square style shows a warning but still
  generates the file.
- [~] **B10** Presets are now matched by variable name instead of line
  position, so missing or extra lines no longer break loading. Still
  to do: move to JSON, and keep a reader for the old `.txt` format.
- [~] **B11** Done: the subtitle now shows the real app and qrcode
  versions instead of the hard-coded "Python 3.7.7 / qrcode 7.3.1".
  Still to do: "Crtl" typo, copy-pasted docstrings ("color of the
  background" ×3), `IntVar(value="10")`.

## C · Installation and tooling

- [x] **C1** `pyproject.toml` with runtime and dev dependencies and
  the `aqrgen` command.
- [x] **C2** Install guide in the README (pipx/uv for users;
  venv/uv for development).
- [ ] **C3** Confirm the minimum versions (Python 3.11, qrcode 8.0,
  Pillow 10.0) by installing the lowest allowed set
  (`uv pip install --resolution lowest-direct`) and running the tests.
- [x] **C4** Updated `.gitignore`.
- [x] **C5** Ruff + numpydoc validation configured in `pyproject.toml`,
  `.pre-commit-config.yaml` added.
- [ ] **C6** Optional: `setup.bat` / `setup.sh` one-click setup scripts.
  Probably not needed now that pipx/uv cover users.

## D · Quality

- [ ] **D5** pytest tests for `core.py` (each style × mask, SVG) and
  preset round-trips. Add `pytest` to the dev group.
- [ ] **D6** GitHub Actions: pre-commit + pytest on Python 3.11 and
  3.14, plus the lowest-direct dependency run from C3.

## E · Features

- [ ] **E1** Live preview of the QR code in the window.
- [ ] **E2** File and folder pickers for the save dir, embedded image
  and mask image.
- [ ] **E3** Generate in a background thread, so the window no longer
  freezes.
- [ ] **E4** Switch error correction to H automatically (or warn) when
  embedding an image.
- [ ] **E5** Expose the new qrcode 8 features: logo size ratio, styled
  and colored SVG output.
- [ ] **E6** Hex color input next to RGB triplets.
- [ ] **E7** Presets as a dropdown or list box instead of a read-only
  text widget.
- [ ] **E8** Optional command-line mode (`aqrgen --preset foo "text"`)
  that reuses `core.py`.
- [ ] **E9** A standalone `.exe` via PyInstaller on GitHub Releases.
- [ ] **E10** Modern ttk theme (e.g. `sv-ttk`).

## F · Docs

- [~] **F1** README: install and usage are done. Still to do: a
  screenshot, a feature list, the preset format.
- [ ] **F2** `CHANGELOG.md` and version tags.
