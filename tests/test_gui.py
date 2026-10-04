"""Behaviour tests of the tkinter GUI with dialogs stubbed out.

Skipped when Tk can't open a window (e.g. on headless Linux).
"""

import time
import tkinter
from tkinter import colorchooser, filedialog, messagebox
from types import SimpleNamespace

import pytest
from PIL import Image

from aqrgen import clipboard, core, gui, payloads, presets


class Dialogs:
    """Record message boxes and answer yes/no questions."""

    def __init__(self, monkeypatch):
        self.log = []
        self.answer = True
        for kind in ("showinfo", "showwarning", "showerror"):
            monkeypatch.setattr(messagebox, kind, self.recorder(kind))
        monkeypatch.setattr(messagebox, "askyesno", self.ask)

    def recorder(self, kind):
        return lambda title, message, **kw: self.log.append((kind, message))

    def ask(self, title, message, **kw):
        self.log.append(("askyesno", message))
        return self.answer

    def kinds(self):
        return [kind for kind, _ in self.log]

    def last_message(self):
        return self.log[-1][1]


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def tk_root(tmp_path, monkeypatch, dialogs):
    monkeypatch.chdir(tmp_path)
    try:
        root = tkinter.Tk()
    except tkinter.TclError as err:
        pytest.skip(f"Tk not available: {err}")
    root.withdraw()
    return root


@pytest.fixture
def app(tk_root, tmp_path):
    app = make_app(tk_root, tmp_path)
    yield app
    wait_idle(app)
    app.close()


def make_app(root, tmp_path):
    app = gui.QrCodeGeneratorApp(root)
    app.message.set("hello")
    app.file_name.set("qr")
    app.save_dir.set(str(tmp_path))
    return app


@pytest.fixture
def logo(tmp_path):
    path = tmp_path / "logo.png"
    Image.new("RGB", (60, 60), (255, 0, 0)).save(path)
    return str(path)


def wait_idle(app, timeout=30):
    """Process Tk events until all background work has finished."""
    deadline = time.monotonic() + timeout
    while app.is_busy():
        assert time.monotonic() < deadline, "background work timed out"
        app.root.update()
        time.sleep(0.01)
    app.root.update()


def generate(app):
    app.generate()
    wait_idle(app)


def state(widget):
    return "disabled" if widget.instate(["disabled"]) else "normal"


# --- startup and saving ----------------------------------------------


def test_starts_without_presets_dir(app, presets_dir):
    # B1: the app used to crash when the presets folder was missing
    assert presets_dir.is_dir()


def test_generates_png(app, dialogs, tmp_path):
    generate(app)
    assert (tmp_path / "qr.png").is_file()
    assert dialogs.kinds() == ["showinfo"]


def test_generate_button_disabled_while_saving(app):
    app.generate()
    assert app.generate_button.instate(["disabled"])
    wait_idle(app)
    assert not app.generate_button.instate(["disabled"])


@pytest.mark.parametrize("collide", ["ask", "overwrite", "warn & abort"])
def test_no_collision_always_saves(app, dialogs, tmp_path, collide):
    # B2: "warn & abort" used to abort even without a collision
    app.on_collision.set(collide)
    generate(app)
    assert (tmp_path / "qr.png").is_file()
    assert dialogs.kinds() == ["showinfo"]


def test_collision_warn_and_abort(app, dialogs, tmp_path):
    (tmp_path / "qr.png").write_bytes(b"old")
    app.on_collision.set("warn & abort")
    generate(app)
    assert (tmp_path / "qr.png").read_bytes() == b"old"
    assert dialogs.kinds() == ["showwarning"]


@pytest.mark.parametrize("answer", [True, False])
def test_collision_ask(app, dialogs, tmp_path, answer):
    (tmp_path / "qr.png").write_bytes(b"old")
    app.on_collision.set("ask")
    dialogs.answer = answer
    generate(app)
    overwritten = (tmp_path / "qr.png").read_bytes() != b"old"
    assert overwritten == answer


def test_empty_save_dir_still_checks_collision(app, dialogs, tmp_path):
    # B3: after "use current directory?" the collision check was skipped
    (tmp_path / "qr.png").write_bytes(b"old")
    app.save_dir.set("")
    app.on_collision.set("warn & abort")
    generate(app)
    assert app.save_dir.get() == str(tmp_path)
    assert (tmp_path / "qr.png").read_bytes() == b"old"
    assert dialogs.kinds() == ["askyesno", "showwarning"]


def test_missing_save_dir_warns(app, dialogs, tmp_path):
    app.save_dir.set(str(tmp_path / "missing"))
    generate(app)
    assert dialogs.kinds() == ["showwarning"]
    assert "does not exist" in dialogs.last_message()


def test_empty_file_name_warns(app, dialogs):
    app.file_name.set("")
    generate(app)
    assert dialogs.kinds() == ["showwarning"]


def test_unexpected_error_shows_dialog(app, dialogs, monkeypatch):
    # B8: unexpected errors go to a dialog, not to a (hidden) console
    def broken(settings):
        raise RuntimeError("boom")

    monkeypatch.setattr(core, "make_qr_image", broken)
    generate(app)
    assert dialogs.kinds() == ["showerror"]
    assert "boom" in dialogs.last_message()


# --- input validation ------------------------------------------------


@pytest.mark.parametrize(
    ("attr", "value", "message"),
    [
        ("front_color", "(300, 0, 0)", "Face color:"),
        ("front_color", "__import__('os')", "Face color:"),  # B5
        ("box_size", "abc", "Box size must be a whole number"),
        ("version", "41", "Size standard must be from 1 to 40"),
        ("border", "-1", "Border size must not be negative"),
    ],
)
def test_invalid_input_warns(app, dialogs, tmp_path, attr, value, message):
    app.root.setvar(str(getattr(app, attr)), value)
    generate(app)
    assert not (tmp_path / "qr.png").exists()
    assert dialogs.kinds() == ["showwarning"]
    assert dialogs.last_message().startswith(message)


def test_unused_invalid_color_is_ignored(app, tmp_path):
    app.color_mask.set("solid")
    app.edge_color.set("not a color")
    generate(app)
    assert (tmp_path / "qr.png").is_file()


def test_missing_embedded_image_warns(app, dialogs):
    app.embed_image.set(True)
    app._update_states()
    app.embedded_image_path.set("missing.png")
    generate(app)
    assert "not found" in dialogs.last_message()


# --- locks and widget states -----------------------------------------


def test_embedding_locks_error_correction(app, logo, tmp_path):
    # E4: qrcode requires H for embedded images
    app.error_correction.set("M")
    app.embed_image.set(True)
    app._update_states()
    assert app.error_correction.get() == "H"
    assert state(app._error_correction_buttons["M"]) == "disabled"
    app.embedded_image_path.set(logo)
    generate(app)
    assert (tmp_path / "qr.png").is_file()
    app.embed_image.set(False)
    app._update_states()
    assert app.error_correction.get() == "M"
    assert state(app._error_correction_buttons["M"]) == "normal"


def svg_mode(app, svg=True):
    app.extension.set(".svg" if svg else ".png")
    app._update_states()


def test_svg_replaces_unsupported_options(app, dialogs, tmp_path):
    # B9: SVG with a non-square style used to warn and generate anyway
    app.box_style.set("vbars")
    app.eye_style.set("rounded")
    app.color_mask.set("sgrad")
    svg_mode(app)
    assert (app.box_style.get(), app.eye_style.get()) == ("square", "square")
    assert app.color_mask.get() == "solid"
    generate(app)
    assert (tmp_path / "qr.svg").is_file()
    assert dialogs.kinds() == ["showinfo"]
    svg_mode(app, svg=False)
    assert (app.box_style.get(), app.eye_style.get()) == ("vbars", "rounded")
    assert app.color_mask.get() == "sgrad"


def test_svg_keeps_supported_options(app):
    app.box_style.set("gapcircle")
    app.color_mask.set("rgrad")
    svg_mode(app)
    assert (app.box_style.get(), app.color_mask.get()) == ("gapcircle", "rgrad")
    assert state(app._edge_widgets[1]) == "normal"


def test_choice_made_under_svg_survives(app):
    app.box_style.set("vbars")
    svg_mode(app)
    app.box_style.set("circle")  # user picks another style in SVG mode
    app._update_states()
    svg_mode(app, svg=False)
    assert app.box_style.get() == "circle"


def test_eye_style_buttons(app):
    assert app.eye_style.get() == "square"
    app._eye_buttons["gapcircle"].invoke()
    assert app.eye_style.get() == "gapcircle"
    svg_mode(app)
    assert app.eye_style.get() == "gapcircle"  # SVG supports it
    assert state(app._eye_buttons["vbars"]) == "disabled"
    assert state(app._eye_buttons["gapcircle"]) == "normal"


def test_svg_with_logo_and_gradient(app, logo, tmp_path):
    svg_mode(app)
    app.color_mask.set("hgrad")
    app.embed_image.set(True)
    app._update_states()
    app.embedded_image_path.set(logo)
    generate(app)
    text = (tmp_path / "qr.svg").read_text(encoding="utf-8")
    assert "linearGradient" in text
    assert "data:image/png;base64," in text


@pytest.mark.parametrize(
    ("value", "message"),
    [("abc", "Logo size must be a whole number"), ("70", "Logo size must be")],
)
def test_invalid_logo_size_warns(app, dialogs, logo, value, message):
    app.embed_image.set(True)
    app._update_states()
    app.embedded_image_path.set(logo)
    app.root.setvar(str(app.logo_size), value)
    generate(app)
    assert dialogs.last_message().startswith(message)


GRADIENTS = ("rgrad", "sgrad", "hgrad", "vgrad")


@pytest.mark.parametrize("extension", core.FORMATS)
@pytest.mark.parametrize("color_mask", core.COLOR_MASKS)
@pytest.mark.parametrize("embed", [False, True])
def test_widget_states(app, extension, color_mask, embed):
    """Every enabled/disabled connection, for every combination."""
    app.extension.set(extension)
    app.color_mask.set(color_mask)
    app.embed_image.set(embed)
    app._update_states()
    svg = extension == ".svg"
    # SVG replaces masks it can't do with solid fill
    mask = (
        "solid" if svg and color_mask not in core.SVG_GRADIENTS else color_mask
    )
    assert app.color_mask.get() == mask

    def expect(widgets, enabled):
        for widget in widgets:
            assert state(widget) == ("normal" if enabled else "disabled"), (
                widget,
                enabled,
            )

    expect(app._mask_image_widgets, mask == "image")
    expect(app._face_widgets, mask != "image")
    expect(app._edge_widgets, mask in GRADIENTS)
    expect(app._embed_widgets, embed)
    for value, button in app._error_correction_buttons.items():
        expect([button], value == "H" or not embed)
    for buttons, svg_values in (
        (app._style_buttons, core.SVG_DRAWERS),
        (app._eye_buttons, core.SVG_DRAWERS),
        (app._mask_buttons, core.SVG_GRADIENTS),
    ):
        for value, button in buttons.items():
            expect([button], not svg or value in svg_values)


def test_mask_buttons_update_states(app):
    # clicking a mask button (not just setting the variable) updates
    app._mask_buttons["image"].invoke()
    assert state(app._mask_image_widgets[1]) == "normal"
    assert state(app._face_widgets[1]) == "disabled"
    app._mask_buttons["rgrad"].invoke()
    assert state(app._mask_image_widgets[1]) == "disabled"
    assert state(app._edge_widgets[1]) == "normal"


# --- dialogs ---------------------------------------------------------


def test_color_picker_cancel_keeps_color(app, monkeypatch):
    # B4: cancelling the color dialog used to crash
    monkeypatch.setattr(colorchooser, "askcolor", lambda **kw: (None, None))
    app.back_color.set("(1, 2, 3)")
    app._pick_color(app.back_color)
    assert app.back_color.get() == "(1, 2, 3)"


def test_color_picker_sets_color(app, monkeypatch):
    monkeypatch.setattr(
        colorchooser, "askcolor", lambda **kw: ((10, 20, 30), "#0a141e")
    )
    app._pick_color(app.front_color)
    assert app.front_color.get() == "(10, 20, 30)"


@pytest.mark.parametrize("chosen", ["C:/qr", ""])
def test_browse_save_dir(app, monkeypatch, tmp_path, chosen):
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: chosen)
    app._browse_save_dir()
    assert app.save_dir.get() == (chosen or str(tmp_path))


@pytest.mark.parametrize("chosen", ["C:/logo.png", ""])
def test_browse_image(app, monkeypatch, chosen):
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: chosen)
    app.mask_image_path.set("old.png")
    app._browse_image(app.mask_image_path, "Image mask")
    assert app.mask_image_path.get() == (chosen or "old.png")


# --- preview ---------------------------------------------------------


def test_preview_shows_image(app):
    wait_idle(app)
    assert app._preview_photo is not None
    width = app._preview_photo.width()
    assert gui.PREVIEW_SIZE <= width <= gui.MAX_PREVIEW_SIZE


@pytest.mark.parametrize(
    ("space", "expected"),
    [(200, gui.PREVIEW_SIZE), (450, 450), (5000, gui.MAX_PREVIEW_SIZE)],
)
def test_preview_size_follows_space(app, space, expected):
    # synthetic resize events: independent of the screen size
    app.root.update_idletasks()
    column = app._preview_column
    others = column.winfo_reqheight() - (app._preview_size + 4)
    event = SimpleNamespace(width=space + 4, height=others + space + 4)
    app._on_preview_area_resized(event)
    assert app._preview_size == expected


def test_preview_grows_with_window(app):
    enlarge(app, 600, 600, need=150)
    assert gui.PREVIEW_SIZE < app._preview_size <= gui.MAX_PREVIEW_SIZE
    assert app._preview_photo.width() == app._preview_size
    show(app, f"{app.root.minsize()[0]}x{app.root.minsize()[1]}")
    assert app._preview_size < gui.MAX_PREVIEW_SIZE


def test_preview_shows_errors_and_hints(app):
    app.front_color.set("nope")
    wait_idle(app)
    assert app._preview_photo is None
    assert "Face color" in app.preview_label.cget("text")
    app.message.set("")
    wait_idle(app)
    assert "Enter a message" in app.preview_label.cget("text")


def test_preview_does_not_open_dialogs(app, dialogs):
    app.border.set(-1)
    wait_idle(app)
    assert dialogs.log == []


# --- presets ---------------------------------------------------------


def test_preset_round_trip(app, dialogs, presets_dir):
    app.preset_name.set("p")
    app.version.set(7)
    app.embed_image.set(True)
    app.back_color.set("#ff0000")
    app.save_preset()
    assert (presets_dir / "p.json").is_file()
    assert app.preset_combo["values"] == ("p",)
    app.version.set(1)
    app.embed_image.set(False)
    app.back_color.set("(0, 0, 0)")
    app.load_preset()
    assert app.version.get() == 7
    assert app.embed_image.get() is True
    assert app.back_color.get() == "#ff0000"
    assert "showwarning" not in dialogs.kinds()


def test_preset_keeps_locked_values(app):
    app.box_style.set("vbars")
    app.extension.set(".svg")
    app._update_states()
    app.preset_name.set("p")
    app.save_preset()
    app.extension.set(".png")
    app._update_states()
    app.box_style.set("rounded")
    app.load_preset()
    assert app.box_style.get() == "square"  # locked by SVG
    app.extension.set(".png")
    app._update_states()
    assert app.box_style.get() == "vbars"


def test_preset_wrong_types_warn(app, dialogs):
    presets.write_preset(
        "bad", {"version": "7", "embed_image": 1, "border": True}
    )
    app.preset_name.set("bad")
    app.load_preset()
    assert app.version.get() == 1
    assert dialogs.kinds() == ["showwarning"]
    for name in ("version", "embed_image", "border"):
        assert name in dialogs.last_message()


@pytest.mark.parametrize(
    ("name", "message"), [("", "enter a preset name"), ("a/b", "must not")]
)
def test_invalid_preset_name_warns(app, dialogs, name, message):
    app.preset_name.set(name)
    for action in (app.save_preset, app.load_preset, app.delete_preset):
        action()
        assert dialogs.kinds()[-1] == "showwarning"
        assert message in dialogs.last_message()


def test_broken_preset_file_warns(app, dialogs, presets_dir):
    (presets_dir / "broken.json").write_text("{", encoding="utf-8")
    app.preset_name.set("broken")
    app.load_preset()
    assert "not valid JSON" in dialogs.last_message()


def test_delete_preset(app, presets_dir):
    app.preset_name.set("p")
    app.save_preset()
    app.delete_preset()
    assert not (presets_dir / "p.json").exists()
    assert app.preset_combo["values"] in ("", ())
    assert app.preset_name.get() == ""


def test_open_presets_folder(app, monkeypatch, presets_dir):
    opened = []
    monkeypatch.setattr(gui, "_open_in_file_manager", opened.append)
    app.open_presets_folder()
    assert opened == [presets_dir]


def test_imports_legacy_presets_on_start(tk_root, tmp_path, dialogs):
    legacy = tmp_path / "presets"
    legacy.mkdir()
    (legacy / "old.txt").write_text("mess=hi\nsize=3\n", encoding="utf-8")
    app = make_app(tk_root, tmp_path)
    try:
        wait_idle(app)
        assert dialogs.kinds() == ["showinfo"]
        assert "old" in dialogs.last_message()
        assert app.preset_combo["values"] == ("old",)
        app.preset_name.set("old")
        app.load_preset()
        assert (app.message.get(), app.version.get()) == ("hi", 3)
    finally:
        wait_idle(app)
        app.close()


# --- background opacity ----------------------------------------------


def test_transparent_background(app, tmp_path):
    app.back_opacity.set(0)
    generate(app)
    with Image.open(tmp_path / "qr.png") as img:
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0
    # the preview shows transparency on a checkerboard
    assert app._preview_photo is not None


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("abc", "Background opacity must be a whole number"),
        ("150", "Background opacity must be from 0 to 100"),
    ],
)
def test_invalid_opacity_warns(app, dialogs, value, message):
    app.root.setvar(str(app.back_opacity), value)
    generate(app)
    assert dialogs.last_message().startswith(message)


def test_preset_keeps_opacity(app):
    app.back_opacity.set(30)
    app.preset_name.set("p")
    app.save_preset()
    app.back_opacity.set(100)
    app.load_preset()
    assert app.back_opacity.get() == 30


def test_checkerboard():
    board = gui._checkerboard((40, 20), square=10)
    grey, white = (204, 204, 204, 255), (255, 255, 255, 255)
    assert [board.getpixel(xy) for xy in ((0, 0), (10, 0), (0, 10))] == [
        grey,
        white,
        white,
    ]
    assert board.getpixel((10, 10)) == grey


# --- layout ----------------------------------------------------------


def show(app, geometry=None):
    app.root.deiconify()  # hidden windows are never laid out
    if geometry:
        app.root.geometry(geometry)
    app.root.update()
    wait_idle(app)


def enlarge(app, extra_width, extra_height, need=50):
    """Enlarge the window as far as the screen allows.

    CI screens are small: skip the test if the window can't grow by at
    least ``need`` pixels in each requested direction.
    """
    show(app)
    min_width, min_height = app.root.minsize()
    width = min(min_width + extra_width, app.root.winfo_screenwidth() - 20)
    height = min(min_height + extra_height, app.root.winfo_screenheight() - 80)
    if (extra_width and width - min_width < need) or (
        extra_height and height - min_height < need
    ):
        pytest.skip("screen too small to enlarge the window")
    show(app, f"{width}x{height}+0+0")


def right_edge(widget, ancestor):
    """X of a widget's right edge, relative to an ancestor widget."""
    return widget.winfo_rootx() + widget.winfo_width() - ancestor.winfo_rootx()


def long_entries(app):
    """Last widget (entry or button) of each row whose entry fills."""
    return [
        app.message_entry,
        app._mask_image_widgets[-1],
        app._embed_widgets[2],
        app._save_dir_widgets[-1],
    ]


def test_long_entries_fill_column_width(app):
    show(app)
    for last in long_entries(app):
        body = last.master.master  # row frame, then the group body
        assert abs(right_edge(last, body) - body.winfo_width()) <= 2, last


def test_long_entries_do_not_grow_with_window(app):
    show(app)
    before = app._save_dir_widgets[1].winfo_width()
    enlarge(app, 1400, 900)
    assert app._save_dir_widgets[1].winfo_width() == before


def test_save_group_directly_below_preview(app):
    enlarge(app, 1400, 900)
    preview_group = app._preview_box.master.master
    save_group = app._save_dir_widgets[0].master.master
    gap = save_group.winfo_y() - (
        preview_group.winfo_y() + preview_group.winfo_height()
    )
    assert 0 <= gap <= 4 * gui.PAD


# --- copy to clipboard -----------------------------------------------


@pytest.fixture
def copied(monkeypatch):
    images = []
    monkeypatch.setattr(clipboard, "copy_image", images.append)
    return images


def copy(app):
    app.copy_to_clipboard()
    wait_idle(app)


def test_copy_png_to_clipboard(app, copied, dialogs):
    app.copy_to_clipboard()
    assert app.generate_button.instate(["disabled"])
    assert app.copy_button.instate(["disabled"])
    wait_idle(app)
    (image,) = copied
    assert image.size[0] > 100
    assert "copied" in app.status.get()
    assert dialogs.log == []  # no message box, just the status line


def test_status_message_clears_only_itself(app):
    app._flash_status("old")
    app.status.set("newer")
    app._clear_status("old")
    assert app.status.get() == "newer"
    app._clear_status("newer")
    assert app.status.get() == ""


def test_copy_in_svg_mode_copies_png(app, copied):
    svg_mode(app)
    app.box_style.set("circle")
    copy(app)
    (image,) = copied
    assert image.mode in ("RGB", "RGBA")


def test_copy_invalid_input_warns(app, copied, dialogs):
    app.front_color.set("nope")
    copy(app)
    assert copied == []
    assert dialogs.last_message().startswith("Face color")


def test_copy_failure_warns(app, dialogs, monkeypatch):
    def fail(image):
        raise clipboard.ClipboardError("in use")

    monkeypatch.setattr(clipboard, "copy_image", fail)
    copy(app)
    assert dialogs.kinds() == ["showwarning"]
    assert "in use" in dialogs.last_message()


def test_shortcuts_are_bound_and_shown(app):
    assert app.root.bind("<Control-Return>")
    assert app.root.bind("<Control-Shift-Return>")
    hints = [
        widget.cget("text")
        for widget in app.generate_button.master.grid_slaves(row=1)
    ]
    assert sorted(hints) == ["Ctrl+Enter", "Ctrl+Shift+Enter"]
    assert "Ctrl" not in app.generate_button.cget("text")
    assert "Ctrl" not in app.copy_button.cget("text")


# --- tooltips --------------------------------------------------------


def test_error_correction_tooltips(app):
    for value, button in app._error_correction_buttons.items():
        assert button.tooltip.text == gui.ERROR_CORRECTION_TIPS[value]
    assert "logo" in gui.ERROR_CORRECTION_TIPS["H"]


def test_tooltip_shows_and_hides(app):
    app.root.deiconify()
    app.root.update()
    tip = app._error_correction_buttons["Q"].tooltip
    tip.show()
    app.root.update()
    assert tip.window is not None
    assert tip.window.winfo_ismapped()
    tip.hide()
    assert tip.window is None


def test_tooltip_appears_after_delay(app, monkeypatch):
    monkeypatch.setattr(gui, "TOOLTIP_DELAY_MS", 10)
    tip = app._error_correction_buttons["L"].tooltip
    tip._schedule()
    assert tip.window is None
    time.sleep(0.05)
    app.root.update()
    assert tip.window is not None
    tip.hide()


# --- multi-line message and Insert forms -----------------------------


SAMPLES = {
    payloads.Wifi: {"ssid": "Home", "password": "secret"},
    payloads.Contact: {"first_name": "Jan", "phone": "+420 123 456 789"},
    payloads.Email: {"address": "a@b.cz", "body": "Hi\nthere"},
    payloads.Sms: {"number": "+420 777 000 111", "text": "Hello"},
    payloads.Phone: {"number": "+420 777 000 111"},
    payloads.WhatsApp: {"number": "+420 777 000 111", "text": "Hi"},
    payloads.Location: {"latitude": "49.1951", "longitude": "16.6068"},
    payloads.Event: {
        "summary": "Party",
        "start_date": "4.10.2026",
        "start_time": "18:00",
    },
    payloads.CzPayment: {"account": "19-2000145399/0800", "amount": "100"},
    payloads.EuPayment: {"name": "A", "account": "DE89370400440532013000"},
}


def fill(dialog, values):
    for name, value in values.items():
        kind, widget, var = dialog.inputs[name]
        if kind == "text":
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
        else:
            var.set(value)


def test_insert_menu_lists_all_types(app):
    labels = [
        app.insert_menu.entrycget(i, "label")
        for i in range(app.insert_menu.index("end") + 1)
    ]
    assert labels == [t.title + "…" for t in payloads.PAYLOAD_TYPES]


@pytest.mark.parametrize("payload_type", payloads.PAYLOAD_TYPES)
def test_insert_each_type(app, dialogs, payload_type):
    app.open_insert_dialog(payload_type)
    dialog = app.insert_dialog
    fill(dialog, SAMPLES[payload_type])
    assert dialog.insert()
    expected = payload_type(**SAMPLES[payload_type]).build()
    assert app.message.get() == expected
    assert app.message_entry.get("1.0", "end-1c") == expected
    assert not dialog.window.winfo_exists()
    wait_idle(app)
    assert app._preview_photo is not None  # the message renders
    assert dialogs.log == []


def test_insert_invalid_keeps_dialog_open(app, dialogs):
    app.message.set("old")
    app.open_insert_dialog(payloads.Wifi)
    fill(app.insert_dialog, {"ssid": "Home"})  # password missing
    assert not app.insert_dialog.insert()
    assert dialogs.kinds() == ["showwarning"]
    assert "Password" in dialogs.last_message()
    assert app.insert_dialog.window.winfo_exists()
    assert app.message.get() == "old"
    app.insert_dialog.close()


def test_insert_remembers_values(app):
    app.open_insert_dialog(payloads.Phone)
    fill(app.insert_dialog, {"number": "+420 777 000 111"})
    app.insert_dialog.insert()
    app.open_insert_dialog(payloads.Phone)
    assert app.insert_dialog.values() == {"number": "+420 777 000 111"}
    app.insert_dialog.close()


def test_insert_cancel_keeps_message(app):
    app.message.set("keep me")
    app.open_insert_dialog(payloads.Sms)
    fill(app.insert_dialog, {"number": "123456"})
    app.insert_dialog.close()
    assert app.message.get() == "keep me"


def test_enter_inserts_except_in_multiline_text(app):
    app.open_insert_dialog(payloads.Sms)
    dialog = app.insert_dialog
    fill(dialog, {"number": "123456", "text": "Hi"})
    text_widget = dialog.inputs["text"][1]
    dialog._on_return(SimpleNamespace(widget=text_widget))
    assert dialog.window.winfo_exists()  # Enter adds a line there
    dialog._on_return(SimpleNamespace(widget=dialog.inputs["number"][1]))
    assert not dialog.window.winfo_exists()
    assert app.message.get() == "SMSTO:123456:Hi"


def test_message_box_and_variable_stay_in_sync(app):
    app.message.set("line 1\nline 2")
    assert app.message_entry.get("1.0", "end-1c") == "line 1\nline 2"
    app.message_entry.insert("end", "!")
    app.root.update()
    assert app.message.get() == "line 1\nline 2!"


def test_shortcuts_work_inside_message_box(app, tmp_path, copied):
    show(app)
    app.message_entry.focus_force()
    app.root.update()
    app.message_entry.event_generate("<Control-Return>")
    wait_idle(app)
    assert (tmp_path / "qr.png").is_file()
    app.message_entry.event_generate("<Control-Shift-Return>")
    wait_idle(app)
    assert len(copied) == 1
    assert "\n" not in app.message.get()  # no new line was typed


def test_preset_keeps_multiline_message(app):
    app.message.set("BEGIN:VCARD\nVERSION:3.0\nFN:Jan\nEND:VCARD")
    app.preset_name.set("card")
    app.save_preset()
    app.message.set("")
    app.load_preset()
    assert app.message_entry.get("1.0", "end-1c").count("\n") == 3


def center(window):
    return (
        window.winfo_rootx() + window.winfo_width() // 2,
        window.winfo_rooty() + window.winfo_height() // 2,
    )


@pytest.mark.parametrize("position", ["+40+40", "+300+150"])
def test_insert_dialog_is_centered_on_main_window(app, position):
    show(app, position)
    app.open_insert_dialog(payloads.Contact)
    dialog = app.insert_dialog.window
    dialog.update()
    (main_x, main_y), (dialog_x, dialog_y) = center(app.root), center(dialog)
    # allow for the dialog's title bar and border
    assert abs(dialog_x - main_x) <= 20
    assert abs(dialog_y - main_y) <= 40
    app.insert_dialog.close()


# --- growing message box ---------------------------------------------


def message_lines(app):
    return int(app.message_entry.cget("height"))


def scrollbar_shown(app):
    return bool(app._message_scrollbar.winfo_ismapped())


def set_message(app, text):
    app.message.set(text)
    wait_idle(app)


def test_message_box_grows_with_content(app):
    show(app)
    assert message_lines(app) == gui.MIN_MESSAGE_LINES
    set_message(app, "\n".join(f"line {i}" for i in range(8)))
    assert message_lines(app) == 8
    assert not scrollbar_shown(app)


def test_message_box_counts_wrapped_lines(app):
    show(app)
    set_message(app, "x" * 400)  # one long line, wrapped in the box
    assert message_lines(app) > gui.MIN_MESSAGE_LINES


def test_message_box_stops_at_column_height_and_scrolls(app):
    show(app)
    size = (app.root.winfo_width(), app.root.winfo_height())
    set_message(app, "\n".join(f"line {i}" for i in range(80)))
    left = app._left_column
    assert gui.MIN_MESSAGE_LINES < message_lines(app) < 80
    assert left.winfo_reqheight() <= left.winfo_height()
    assert scrollbar_shown(app)
    assert (app.root.winfo_width(), app.root.winfo_height()) == size
    set_message(app, "short")
    assert message_lines(app) == gui.MIN_MESSAGE_LINES
    assert not scrollbar_shown(app)


def test_message_box_uses_space_of_larger_window(app):
    set_message(app, "\n".join(f"line {i}" for i in range(80)))
    show(app)
    before = message_lines(app)
    enlarge(app, 0, 300, need=100)
    wait_idle(app)
    assert message_lines(app) > before
