"""Tests of copying images to the clipboard.

The platform calls are replaced by fakes, so the real clipboard is not
touched. Set AQRGEN_TEST_CLIPBOARD=1 to also run a real round trip
(this overwrites the clipboard content).
"""

import io
import os
import sys

import pytest
from PIL import Image

from aqrgen import clipboard


@pytest.fixture
def image():
    img = Image.new("RGBA", (30, 20), (255, 0, 0, 128))
    img.putpixel((0, 0), (0, 0, 255, 255))
    return img


def test_png_bytes_keep_transparency(image):
    with Image.open(io.BytesIO(clipboard.png_bytes(image))) as back:
        assert back.size == (30, 20)
        assert back.getpixel((5, 5)) == (255, 0, 0, 128)


def test_dib_bytes_are_a_bitmap_without_file_header(image):
    dib = clipboard.dib_bytes(image)
    # BITMAPINFOHEADER: header size, width, height
    assert int.from_bytes(dib[0:4], "little") == 40
    assert int.from_bytes(dib[4:8], "little") == 30
    assert int.from_bytes(dib[8:12], "little", signed=True) == 20


def test_linux_without_tools_explains(monkeypatch, image):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
    with pytest.raises(clipboard.ClipboardError, match="xclip"):
        clipboard.copy_image(image)


@pytest.mark.parametrize(
    ("tool", "command"),
    [
        ("wl-copy", ["wl-copy", "--type", "image/png"]),
        ("xclip", ["xclip", "-selection", "clipboard", "-target"]),
    ],
)
def test_linux_pipes_png_to_tool(monkeypatch, image, tool, command):
    calls = []

    class FakeProcess:
        def __init__(self, args, **kwargs):
            calls.append(args)
            self.stdin = io.BytesIO()
            self.stdin.close = lambda: calls.append(self.stdin.getvalue())

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    monkeypatch.setattr(
        clipboard.shutil, "which", lambda name: name if name == tool else None
    )
    monkeypatch.setattr(clipboard.subprocess, "Popen", FakeProcess)
    clipboard.copy_image(image)
    assert calls[0][: len(command)] == command
    assert calls[1].startswith(b"\x89PNG")


@pytest.mark.parametrize("returncode", [0, 1])
def test_macos_uses_osascript(monkeypatch, image, returncode):
    calls = []

    class Result:
        stderr = b"no clipboard"

    def fake_run(args, **kwargs):
        calls.append(args)
        result = Result()
        result.returncode = returncode
        return result

    monkeypatch.setattr(clipboard.sys, "platform", "darwin")
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    if returncode:
        with pytest.raises(clipboard.ClipboardError, match="no clipboard"):
            clipboard.copy_image(image)
    else:
        clipboard.copy_image(image)
    assert calls[0][0] == "osascript"
    assert "«class PNGf»" in calls[0][2]


@pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("AQRGEN_TEST_CLIPBOARD") != "1",
    reason="overwrites the clipboard; set AQRGEN_TEST_CLIPBOARD=1 on Windows",
)
def test_windows_round_trip(image):
    from PIL import ImageGrab  # noqa: PLC0415 - Windows/macOS only

    clipboard.copy_image(image)
    back = ImageGrab.grabclipboard()
    assert back.size == image.size
