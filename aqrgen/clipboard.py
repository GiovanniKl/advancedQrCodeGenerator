"""Copying images to the system clipboard.

tkinter's clipboard only holds text, so images go through the platform:
the Win32 clipboard API on Windows (via ctypes), ``osascript`` on macOS
and ``wl-copy`` or ``xclip`` on Linux.
"""

import io
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OPEN_ATTEMPTS = 10
"""Tries to open the Windows clipboard while another app holds it."""


class ClipboardError(RuntimeError):
    """The image could not be copied to the clipboard."""


def png_bytes(image):
    """Encode an image as PNG.

    Parameters
    ----------
    image : PIL.Image.Image
        The image.

    Returns
    -------
    bytes
        The PNG file content.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def dib_bytes(image):
    """Encode an image as a device-independent bitmap (``CF_DIB``).

    Parameters
    ----------
    image : PIL.Image.Image
        The image. Transparency is dropped.

    Returns
    -------
    bytes
        A BMP file without its 14-byte file header.
    """
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="BMP")
    return buffer.getvalue()[14:]


def copy_image(image):
    """Put an image on the system clipboard.

    Parameters
    ----------
    image : PIL.Image.Image
        The image to copy.

    Raises
    ------
    ClipboardError
        If the clipboard can't be accessed, or on Linux no clipboard
        tool is installed.
    """
    if sys.platform == "win32":
        _copy_windows(image)
    elif sys.platform == "darwin":
        _copy_macos(image)
    else:
        _copy_linux(image)


def _copy_windows(image):
    """Copy an image as both a bitmap and a PNG on Windows.

    Parameters
    ----------
    image : PIL.Image.Image
        The image to copy.

    Raises
    ------
    ClipboardError
        If the clipboard can't be opened or written.
    """
    import ctypes  # noqa: PLC0415 - Windows only
    from ctypes import wintypes  # noqa: PLC0415

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = (wintypes.LPCWSTR,)
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    cf_dib = 8
    cf_png = user32.RegisterClipboardFormatW("PNG")
    gmem_moveable = 0x0002

    def put(clipboard_format, data):
        """Copy bytes to global memory and give it to the clipboard.

        Parameters
        ----------
        clipboard_format : int
            Clipboard format ID.
        data : bytes
            Content in that format.
        """
        handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
        if not handle:
            raise ClipboardError("Not enough memory for the clipboard.")
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(clipboard_format, handle):
            kernel32.GlobalFree(handle)
            raise ClipboardError("Writing to the clipboard failed.")
        # on success the system owns the memory, don't free it

    for _ in range(OPEN_ATTEMPTS):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)  # another application holds the clipboard
    else:
        raise ClipboardError(
            "The clipboard is in use by another application. Try again."
        )
    try:
        user32.EmptyClipboard()
        put(cf_dib, dib_bytes(image))
        put(cf_png, png_bytes(image))
    finally:
        user32.CloseClipboard()


def _copy_macos(image):
    """Copy an image as PNG on macOS using ``osascript``.

    Parameters
    ----------
    image : PIL.Image.Image
        The image to copy.

    Raises
    ------
    ClipboardError
        If ``osascript`` fails.
    """
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "qr.png"
        path.write_bytes(png_bytes(image))
        script = (
            f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            check=False,
        )
    if result.returncode:
        raise ClipboardError(result.stderr.decode(errors="replace").strip())


def _copy_linux(image):
    """Copy an image as PNG on Linux using wl-copy or xclip.

    Parameters
    ----------
    image : PIL.Image.Image
        The image to copy.

    Raises
    ------
    ClipboardError
        If neither tool is installed or the tool fails.
    """
    for command in (
        ["wl-copy", "--type", "image/png"],
        ["xclip", "-selection", "clipboard", "-target", "image/png", "-i"],
    ):
        if shutil.which(command[0]):
            break
    else:
        raise ClipboardError(
            "Copying images needs wl-clipboard (Wayland) or xclip (X11). "
            "Install one of them, e.g. 'sudo apt install xclip'."
        )
    try:
        # wl-copy and xclip keep running to serve the clipboard
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        )
        process.stdin.write(png_bytes(image))
        process.stdin.close()
    except OSError as err:
        raise ClipboardError(f"{command[0]} failed: {err}") from None
