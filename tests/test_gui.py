"""Behaviour tests of the tkinter GUI with dialogs stubbed out.

Skipped when Tk can't open a window (e.g. on headless Linux).
"""

import time
import tkinter
from tkinter import colorchooser, filedialog, messagebox

import pytest
from PIL import Image

from aqrgen import core, gui, presets


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


def test_svg_locks_style_and_mask(app, dialogs, tmp_path):
    # B9: SVG with a non-square style used to warn and generate anyway
    app.box_style.set("circle")
    app.color_mask.set("rgrad")
    app.extension.set(".svg")
    app._update_states()
    assert (app.box_style.get(), app.color_mask.get()) == ("square", "solid")
    generate(app)
    assert (tmp_path / "qr.svg").is_file()
    assert dialogs.kinds() == ["showinfo"]
    app.extension.set(".png")
    app._update_states()
    assert (app.box_style.get(), app.color_mask.get()) == ("circle", "rgrad")


def test_mask_widgets_follow_color_mask(app):
    app.color_mask.set("image")
    app._update_states()
    assert state(app._mask_image_widgets[1]) == "normal"
    assert state(app._edge_widgets[1]) == "disabled"
    app.color_mask.set("vgrad")
    app._update_states()
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
    assert app._preview_photo.width() == gui.PREVIEW_SIZE


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
    app.box_style.set("circle")
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
    assert app.box_style.get() == "circle"


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
