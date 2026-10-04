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
| `qrcode[pil]` | `>=8.2,<9` | 8.0/8.1 silently ignore `embedded_image_path` (see C3); capped below 9 to avoid API breaks |
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
- **Users:** `py -m pip install --user <GitHub archive .zip URL>` (no
  git needed; rerun to update), then `py -m aqrgen`. pipx with the same
  URL is suggested for isolation, and is required on Linux distributions
  that block `pip --user` (PEP 668). Later, a standalone `.exe` (E9) can
  cover friends without Python.
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
- [x] **A2** The GUI uses PEP 8 names (`QrCodeGeneratorApp`,
  `message`, `save_dir`, `_update_states`, …). Preset files keep their
  old keys (`mess=`, `picname=`, …) through `gui.PRESET_KEYS`.
- [x] **A3** Added a `main()` function and an `if __name__ ==
  "__main__":` guard.
- [x] **A4** Replaced the `if/elif` chains with lookup dicts (in
  `core.py`).
- [x] **A5** Widgets are enabled and disabled by named groups instead
  of list positions. `__init__` is split into one builder method per
  section, with small helpers for repeated widget patterns.
- [x] **A6** All of `gui.py` has numpydoc docstrings. The temporary
  lint exceptions for it are gone; numpydoc only skips `__init__`
  methods (documented in the class docstring) and `tests/`.

## B · Bugs and robustness

- [x] **B1** Crash on a fresh clone: `presets/` is now created when
  it's missing.
- [x] **B2** "warn & abort" now aborts only when the file name
  actually collides.
- [x] **B3** The collision check now also runs after "use current
  dir?" is answered.
- [x] **B4** Cancelling the color picker keeps the old color instead of
  crashing.
- [x] **B5** `eval()` is gone. Colors go through `core.parse_color`
  (accepts `(r, g, b)` or `#rrggbb`, checks the 0–255 range), and preset
  values are converted by variable type. Invalid colors show a warning
  instead of a traceback. Only the colors the selected mode actually
  uses are parsed.
- [x] **B6** Deleting a preset now uses `Path.unlink()` instead of
  `os.system("del …")` (Windows-only, open to shell injection).
- [x] **B7** Presets live in a per-user folder (`%APPDATA%\aqrgen\presets`,
  `~/Library/Application Support/aqrgen/presets`,
  `$XDG_CONFIG_HOME` or `~/.config/aqrgen/presets`), independent of the
  working directory. No new dependency.
- [x] **B8** Inputs are validated with readable messages:
  `core.check_settings` covers version 1–40, box size ≥ 1, border ≥ 0
  (4 is the default and recommendation, smaller borders are allowed),
  missing image files and option names; the GUI covers non-numbers,
  missing save dir and empty file name. Unexpected errors show an error
  dialog with the traceback. `aqrgen` is now a `gui-scripts` entry
  point, so no console window opens with it on Windows.
- [x] **B9** SVG now locks the box style to square and the color mask
  to solid fill (previous choices come back when switching to PNG), so
  there is nothing to warn about.
- [x] **B10** Presets are JSON, one `<name>.json` per preset, with
  `format_version` and typed values (numbers, booleans), using the
  GUI's variable names as keys. Old `.txt` presets in `./presets` are
  imported once per folder on startup (existing JSON presets win, old
  files stay untouched). Preset names are validated, so they can't
  escape the folder or contain characters invalid in file names.
- [x] **B11** The subtitle shows the real app and qrcode versions.
  The copy-pasted docstrings, the "Crtl" typo and
  `IntVar(value="10")` are fixed, and the unused
  `clamp`/`rgb2hex`/`hex2rgb` helpers are removed.

## C · Installation and tooling

- [x] **C1** `pyproject.toml` with runtime and dev dependencies and
  the `aqrgen` command.
- [x] **C2** Install guide in the README (pipx/uv for users;
  venv/uv for development).
- [x] **C3** Minimum versions checked with
  `uv pip install --resolution lowest-direct` on Python 3.11. This
  showed that qrcode 8.0 and 8.1 only know the misspelled
  `embeded_image_path` and silently drop the logo, so the floor is now
  **8.2**. Python 3.11 + qrcode 8.2 + Pillow 10.0.0 pass all tests.
- [x] **C4** Updated `.gitignore`.
- [x] **C5** Ruff + numpydoc validation configured in `pyproject.toml`,
  `.pre-commit-config.yaml` added.
- [ ] **C6** Optional: `setup.bat` / `setup.sh` one-click setup scripts.
  Probably not needed now that pipx/uv cover users.

## D · Quality

- [x] **D5** pytest suite in `tests/` (139 tests):
  - `core`: each style × mask, colors, embedded image, SVG, color
    parsing, settings validation, previews.
  - `presets`: JSON round-trip, names, broken files, platform folders,
    legacy conversion and import.
  - GUI behaviour with stubbed dialogs: saving, collisions,
    validation, locks, file dialogs, preview, presets, legacy import,
    error dialog. These are skipped when Tk can't start (headless
    Linux). `tests/conftest.py` redirects the presets folder so tests
    never touch the real one.
- [x] **D6** GitHub Actions (`.github/workflows/ci.yml`):
  - pre-commit
  - pytest on Python 3.11–3.14 on Ubuntu, and 3.14 on Windows
  - a lowest-direct job on Windows with Python 3.11

  It runs on pushes to `main` and on pull requests (not for docs-only
  changes), or by hand from the Actions tab. Every job has a timeout.

  Verified on GitHub with a test pull request.

## E · Features

- [x] **E1** Live preview next to the inputs. It's redrawn 0.3 s after
  the last change, drawn with a reduced box size so even version 40
  stays fast, and shows input errors as text instead of dialogs.
- [x] **E2** "Browse…" buttons for the save dir, the embedded image and
  the mask image.
- [x] **E3** Previews and saving run in a worker thread; the Generate
  button is disabled while saving.
- [x] **E4** qrcode doesn't switch to H itself, it raises an error when
  an embedded image is used with a lower level. Ticking "Embed an
  image" now locks error correction to H (L/M/Q disabled), and
  unticking restores the previous level.
- [ ] **E5** Expose the new qrcode 8 features: logo size ratio, styled
  and colored SVG output.
- [x] **E6** Color fields accept `(r, g, b)` and `#rrggbb`, and the
  labels say so.
- [x] **E7** Editable preset dropdown with Load / Save / Delete / Open
  folder buttons instead of the entry and the read-only text list.
- [ ] **E8** Optional command-line mode (`aqrgen --preset foo "text"`)
  that reuses `core.py`.
- [ ] **E9** A standalone `.exe` via PyInstaller on GitHub Releases.
- [ ] **E10** Modern ttk theme (e.g. `sv-ttk`).

## F · Docs

- [~] **F1** README: install and usage are done. Still to do: a
  screenshot, a feature list, the preset format.
- [ ] **F2** `CHANGELOG.md` and version tags.
