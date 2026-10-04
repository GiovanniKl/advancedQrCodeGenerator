"""QR code generation, independent of any GUI.

The GUI (or any other front end) fills in a `QrSettings` instance and
passes it to `make_qr_image`.
"""

from dataclasses import dataclass
from pathlib import Path

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles import colormasks
from qrcode.image.styles.moduledrawers import pil as drawers
from qrcode.image.svg import SvgImage

Color = tuple[int, int, int]

ERROR_CORRECTIONS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}
"""Error correction level names mapped to qrcode constants."""

MODULE_DRAWERS = {
    "square": drawers.SquareModuleDrawer,
    "gapsquare": drawers.GappedSquareModuleDrawer,
    "circle": drawers.CircleModuleDrawer,
    "rounded": drawers.RoundedModuleDrawer,
    "vbars": drawers.VerticalBarsDrawer,
    "hbars": drawers.HorizontalBarsDrawer,
}
"""Box style names mapped to PIL module drawer classes."""

COLOR_MASKS = {
    "solid": colormasks.SolidFillColorMask,
    "rgrad": colormasks.RadialGradiantColorMask,
    "sgrad": colormasks.SquareGradiantColorMask,
    "hgrad": colormasks.HorizontalGradiantColorMask,
    "vgrad": colormasks.VerticalGradiantColorMask,
    "image": colormasks.ImageColorMask,
}
"""Color mask names mapped to qrcode color mask classes."""

FORMATS = (".png", ".svg")
"""Supported output file extensions."""


@dataclass
class QrSettings:
    """All options that define how a QR code looks.

    Attributes
    ----------
    data : str
        Message or URL to encode.
    version : int, default 1
        Size standard from 1 (21x21 modules) to 40. Grows
        automatically if the data does not fit.
    error_correction : {"L", "M", "Q", "H"}, default "M"
        Error correction level (recovers 7, 15, 25 or 30 % of data).
    extension : {".png", ".svg"}, default ".png"
        Output format. SVG supports only the square style in black and
        white; all styling options below are ignored for SVG.
    box_size : int, default 10
        Pixels per module (box).
    border : int, default 5
        Border width in modules. The QR standard requires at least 4.
    box_style : str, default "square"
        Key of `MODULE_DRAWERS`.
    color_mask : str, default "solid"
        Key of `COLOR_MASKS`.
    back_color : tuple of int, default (255, 255, 255)
        Background RGB color.
    front_color : tuple of int, default (0, 0, 0)
        Face (module) RGB color.
    edge_color : tuple of int, default (0, 0, 255)
        Second RGB color, used by the gradient color masks.
    mask_image_path : str or None, default None
        Path to the image used by the "image" color mask.
    embedded_image_path : str or None, default None
        Path to an image embedded in the center of the QR code, or
        None for no image.
    """

    data: str
    version: int = 1
    error_correction: str = "M"
    extension: str = ".png"
    box_size: int = 10
    border: int = 5
    box_style: str = "square"
    color_mask: str = "solid"
    back_color: Color = (255, 255, 255)
    front_color: Color = (0, 0, 0)
    edge_color: Color = (0, 0, 255)
    mask_image_path: str | None = None
    embedded_image_path: str | None = None


def make_qr_image(settings):
    """Generate a QR code image.

    Parameters
    ----------
    settings : QrSettings
        Options of the QR code.

    Returns
    -------
    qrcode.image.base.BaseImage
        Generated image (a styled PIL image for PNG, an SVG image for
        SVG). Save it with its ``save`` method.
    """
    is_svg = settings.extension == ".svg"
    qr = qrcode.QRCode(
        version=settings.version,
        error_correction=ERROR_CORRECTIONS[settings.error_correction],
        box_size=settings.box_size,
        border=settings.border,
        image_factory=SvgImage if is_svg else StyledPilImage,
    )
    qr.add_data(settings.data)
    qr.make(fit=True)
    if is_svg:
        return qr.make_image()
    return qr.make_image(
        module_drawer=MODULE_DRAWERS[settings.box_style](),
        color_mask=_make_color_mask(settings),
        embedded_image_path=settings.embedded_image_path,
    )


def parse_color(text):
    """Parse an RGB color from text.

    Parameters
    ----------
    text : str
        Either an RGB triplet such as ``"(255, 128, 0)"`` (parentheses
        optional) or a hex code such as ``"#ff8000"``.

    Returns
    -------
    tuple of int
        The color as an ``(r, g, b)`` tuple.

    Raises
    ------
    ValueError
        If the text is not a valid color or a component is outside
        the range 0 to 255.
    """
    stripped = text.strip()
    if stripped.startswith("#"):
        digits = stripped[1:]
        if len(digits) != 6:
            raise ValueError(f"{text!r} is not a #rrggbb hex color.")
        try:
            return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            raise ValueError(f"{text!r} is not a #rrggbb hex color.") from None
    parts = stripped.removeprefix("(").removesuffix(")").split(",")
    try:
        color = tuple(int(part) for part in parts)
    except ValueError:
        color = ()
    if len(color) != 3 or not all(0 <= c <= 255 for c in color):
        raise ValueError(
            f"{text!r} is not an RGB triplet of three integers from 0 to "
            "255, e.g. (255, 128, 0)."
        )
    return color


def output_path(directory, name, extension):
    """Return the file path a QR code image is saved to.

    Parameters
    ----------
    directory : str or pathlib.Path
        Target directory.
    name : str
        File name without extension.
    extension : {".png", ".svg"}
        File extension.

    Returns
    -------
    pathlib.Path
        Path of the image file.
    """
    return Path(directory) / f"{name}{extension}"


def save_qr_image(image, directory, name, extension):
    """Save a generated QR code image.

    Parameters
    ----------
    image : qrcode.image.base.BaseImage
        Image returned by `make_qr_image`.
    directory : str or pathlib.Path
        Target directory.
    name : str
        File name without extension.
    extension : {".png", ".svg"}
        File extension.

    Returns
    -------
    pathlib.Path
        Path of the saved file.
    """
    path = output_path(directory, name, extension)
    image.save(path)
    return path


def _make_color_mask(settings):
    """Build the color mask object for a PNG QR code.

    Parameters
    ----------
    settings : QrSettings
        Options of the QR code.

    Returns
    -------
    qrcode.image.styles.colormasks.QRColorMask
        Color mask instance for `StyledPilImage`.
    """
    mask_class = COLOR_MASKS[settings.color_mask]
    if settings.color_mask == "solid":
        return mask_class(settings.back_color, settings.front_color)
    if settings.color_mask == "image":
        return mask_class(settings.back_color, settings.mask_image_path)
    return mask_class(
        settings.back_color, settings.front_color, settings.edge_color
    )
