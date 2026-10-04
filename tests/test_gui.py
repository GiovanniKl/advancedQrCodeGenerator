"""Behaviour tests of the tkinter GUI with message boxes stubbed out.

Skipped when no display is available (e.g. on headless Linux).
"""

import tkinter
from tkinter import colorchooser, messagebox

import pytest

from aqrgen import gui


class Dialogs:
    """Record message boxes and answer yes/no questions."""

    def __init__(self, monkeypatch):
        self.log = []
        self.answer = True
        for kind in ("showinfo", "showwarning"):
            monkeypatch.setattr(messagebox, kind, self.recorder(kind))
        monkeypatch.setattr(messagebox, "askyesno", self.ask)

    def recorder(self, kind):
        return lambda title, message, **kw: self.log.append((kind, message))

    def ask(self, title, message, **kw):
        self.log.append(("askyesno", message))
        return self.answer

    def kinds(self):
        return [kind for kind, _ in self.log]


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def app(tmp_path, monkeypatch, dialogs):
    monkeypatch.chdir(tmp_path)
    try:
        root = tkinter.Tk()
    except tkinter.TclError as err:
        pytest.skip(f"Tk not available: {err}")
    root.withdraw()
    app = gui.qrCodeGen(root)
    app.mess.set("hello")
    app.picname.set("qr")
    app.savedir.set(str(tmp_path))
    yield app
    root.destroy()


def test_starts_without_presets_dir(app, tmp_path):
    # B1: the app used to crash when presets/ was missing
    assert (tmp_path / "presets").is_dir()


def test_generates_png(app, dialogs, tmp_path):
    app.make()
    assert (tmp_path / "qr.png").is_file()
    assert dialogs.kinds() == ["showinfo"]


@pytest.mark.parametrize("collide", ["ask", "overwrite", "warn & abort"])
def test_no_collision_always_saves(app, dialogs, tmp_path, collide):
    # B2: "warn & abort" used to abort even without a collision
    app.collide.set(collide)
    app.make()
    assert (tmp_path / "qr.png").is_file()
    assert dialogs.kinds() == ["showinfo"]


def test_collision_warn_and_abort(app, dialogs, tmp_path):
    (tmp_path / "qr.png").write_bytes(b"old")
    app.collide.set("warn & abort")
    app.make()
    assert (tmp_path / "qr.png").read_bytes() == b"old"
    assert dialogs.kinds() == ["showwarning"]


@pytest.mark.parametrize("answer", [True, False])
def test_collision_ask(app, dialogs, tmp_path, answer):
    (tmp_path / "qr.png").write_bytes(b"old")
    app.collide.set("ask")
    dialogs.answer = answer
    app.make()
    overwritten = (tmp_path / "qr.png").read_bytes() != b"old"
    assert overwritten == answer


def test_empty_savedir_still_checks_collision(app, dialogs, tmp_path):
    # B3: after "use current directory?" the collision check was skipped
    (tmp_path / "qr.png").write_bytes(b"old")
    app.savedir.set("")
    app.collide.set("warn & abort")
    app.make()
    assert app.savedir.get() == str(tmp_path)
    assert (tmp_path / "qr.png").read_bytes() == b"old"
    assert dialogs.kinds() == ["askyesno", "showwarning"]


def test_color_picker_cancel_keeps_color(app, monkeypatch):
    # B4: cancelling the color dialog used to crash
    monkeypatch.setattr(colorchooser, "askcolor", lambda **kw: (None, None))
    app.bgcolor.set("(1, 2, 3)")
    app.gimmecolorbg()
    assert app.bgcolor.get() == "(1, 2, 3)"


def test_color_picker_sets_color(app, monkeypatch):
    monkeypatch.setattr(
        colorchooser, "askcolor", lambda **kw: ((10, 20, 30), "#0a141e")
    )
    app.gimmecolorf()
    assert app.fcolor.get() == "(10, 20, 30)"


@pytest.mark.parametrize("text", ["(300, 0, 0)", "__import__('os')"])
def test_invalid_color_shows_warning(app, dialogs, tmp_path, text):
    # B5: colors used to go through eval()
    app.fcolor.set(text)
    app.make()
    assert not (tmp_path / "qr.png").exists()
    assert dialogs.kinds() == ["showwarning"]
    assert dialogs.log[0][1].startswith("Face color:")


def test_unused_invalid_color_is_ignored(app, dialogs, tmp_path):
    app.cmask.set("solid")
    app.color2.set("not a color")
    app.make()
    assert (tmp_path / "qr.png").is_file()


def test_preset_round_trip(app, dialogs):
    app.presetname.set("p")
    app.size.set(7)
    app.embim.set(True)
    app.savepresets()
    app.size.set(1)
    app.embim.set(False)
    app.loadpresets()
    assert app.size.get() == 7
    assert app.embim.get() is True
    assert "showwarning" not in dialogs.kinds()


def test_preset_bad_value_warns(app, dialogs, tmp_path):
    (tmp_path / "presets" / "bad.txt").write_text(
        "size=__import__('os')\n", encoding="utf-8"
    )
    app.presetname.set("bad")
    app.loadpresets()
    assert app.size.get() == 1
    assert "showwarning" in dialogs.kinds()


def test_delete_preset(app, dialogs, tmp_path):
    app.presetname.set("p")
    app.savepresets()
    app.delpresets()
    assert not (tmp_path / "presets" / "p.txt").exists()
