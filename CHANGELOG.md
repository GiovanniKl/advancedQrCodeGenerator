# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-10-05

### Added
- "Import…" button next to the presets: imports old `.txt` presets
  from any folder (the old app's folder or its `presets` folder), and
  asks before importing files a second time.

### Changed
- When an imported preset's name is taken, it gets a number
  (`name 2`, `name 3`, …) instead of being skipped.

### Fixed
- Old `.txt` presets saved in the Windows encoding (e.g. cp1250, as
  the original script did) were skipped during the automatic import.
- The automatic import skipped presets silently and then never tried
  again; it now remembers each imported file, retries unreadable ones
  on the next start and lists every renamed or unreadable file.

## [0.1.0] - 2026-10-04

The first release as an installable package: a rewrite of the original
script with a new window layout, many new options and a test suite.

### Added
- Installable package `aqrgen` with the `aqrgen` command
  (`py -m aqrgen` also works); installation with pip, pipx or uv.
- Live preview that updates as you type and shows input problems as
  text; it grows with the window up to twice its size.
- "Insert…" forms for standard message types: Wi-Fi network, contact
  (vCard), e-mail, SMS, phone call, WhatsApp message, location, calendar
  event, Czech QR Platba and EU SEPA (EPC) payment, with input checks
  (IBAN and Czech account checksums, dates, phone numbers).
- Eye style: the three corner squares get their own style.
- "Gapped circle" box style (for PNG and SVG).
- Logo size setting; non-square logos keep their proportions.
- Background opacity from 0 % (transparent) to 100 %, for PNG and SVG.
- Styled SVG output: circle and gapped styles, colors, gradients and
  logos, as one path without seams between boxes.
- "Copy PNG to clipboard" button (Ctrl+Shift+Enter) on Windows, macOS
  and Linux.
- "Browse…" buttons for the save folder, the logo and the mask image.
- Colors can also be written as `#rrggbb`.
- Tooltips explaining the error correction levels.
- Presets dropdown with Load, Save, Delete and Open folder.
- Error dialog for unexpected errors instead of a console traceback.
- Test suite and GitHub Actions on Python 3.11–3.14 (Ubuntu, Windows),
  including the lowest supported dependency versions.

### Changed
- New three-column window: content and colors on the left, styles and
  logo in the middle, preview and saving on the right, presets at the
  top. The window can be resized.
- The message box is multi-line, grows with its content and scrolls
  when needed.
- Generating and copying run in the background; the window no longer
  freezes.
- Presets are JSON files in a per-user folder (e.g.
  `%APPDATA%\aqrgen\presets`); old `.txt` presets are imported once.
- Embedding a logo selects error correction H automatically, as qrcode
  requires it.
- SVG mode replaces options it can't do and restores them when
  switching back to PNG.
- The default border is 4 boxes (the recommended minimum); smaller
  borders are allowed.
- Requires Python 3.11+, qrcode 8.2+ (below 9) and Pillow 10.0+.

### Fixed
- Crash on start when the presets folder was missing.
- "Warn & abort" aborted even when no file of that name existed.
- The file name collision check was skipped after choosing the current
  directory.
- Crash when the color picker was cancelled.
- Color and preset values are no longer run through `eval()`.
- Deleting a preset no longer uses a Windows-only shell command.
- Palette and grayscale images used as image color masks crashed
  generation.
- Invalid inputs show a clear message instead of a traceback.

## [0.0.1] - 2025-11-10

The original single-file script (`advancedQrCodeGenAsClass.py`): a
tkinter window for qrcode 7.3.1 with box styles, color masks, embedded
images, SVG output and text presets.

[0.1.1]: https://github.com/GiovanniKl/advancedQrCodeGenerator/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/GiovanniKl/advancedQrCodeGenerator/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/GiovanniKl/advancedQrCodeGenerator/releases/tag/v0.0.1
