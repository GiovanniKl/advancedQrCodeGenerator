"""Advanced QR Code Generator: a tkinter GUI for the qrcode package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aqrgen")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0+unknown"
