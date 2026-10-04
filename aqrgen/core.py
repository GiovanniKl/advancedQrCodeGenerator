"""QR code generation, independent of any GUI.

The GUI (or any other front end) fills in a `QrSettings` instance and
passes it to `make_qr_image`.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from functools import partial
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles import colormasks
from qrcode.image.styles.moduledrawers import pil as drawers
from qrcode.image.styles.moduledrawers import svg as svg_drawers

from aqrgen.svg import StyledSvgImage, SvgStyle

Color = tuple[int, int, int]

ERROR_CORRECTIONS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}
"""Error correction level names mapped to qrcode constants."""

GAP_RATIO = Decimal("0.8")
"""Size of gapped squares and circles relative to the box size."""


class GappedCircleModuleDrawer(drawers.CircleModuleDrawer):
    """PNG module drawer for circles with a gap around them.

    qrcode only offers gapped circles for SVG; this is the PNG version.

    Parameters
    ----------
    size_ratio : float, default 0.8
        Circle diameter relative to the box size.
    """

    def __init__(self, size_ratio=float(GAP_RATIO)):
        self.size_ratio = size_ratio

    def initialize(self, *args, **kwargs):
        """Pre-render one antialiased circle, like the parent class.

        Parameters
        ----------
        *args, **kwargs
            Passed on to the base drawer's ``initialize``.
        """
        # skip CircleModuleDrawer.initialize, which draws a full circle
        drawers.StyledPilQRModuleDrawer.initialize(self, *args, **kwargs)
        box_size = self.img.box_size
        fake_size = box_size * drawers.ANTIALIASING_FACTOR
        inset = fake_size * (1 - self.size_ratio) / 2
        self.circle = Image.new(
            self.img.mode,
            (fake_size, fake_size),
            self.img.color_mask.back_color,
        )
        ImageDraw.Draw(self.circle).ellipse(
            (inset, inset, fake_size - inset, fake_size - inset),
            fill=self.img.paint_color,
        )
        self.circle = self.circle.resize(
            (box_size, box_size), Image.Resampling.LANCZOS
        )


PNG_DRAWERS = {
    "square": drawers.SquareModuleDrawer,
    "gapsquare": partial(
        drawers.GappedSquareModuleDrawer, size_ratio=float(GAP_RATIO)
    ),
    "circle": drawers.CircleModuleDrawer,
    "gapcircle": GappedCircleModuleDrawer,
    "rounded": drawers.RoundedModuleDrawer,
    "vbars": drawers.VerticalBarsDrawer,
    "hbars": drawers.HorizontalBarsDrawer,
}
"""Box style names mapped to PNG module drawer factories."""

SVG_DRAWERS = {
    "square": svg_drawers.SvgPathSquareDrawer,
    "gapsquare": partial(svg_drawers.SvgPathSquareDrawer, size_ratio=GAP_RATIO),
    "circle": svg_drawers.SvgPathCircleDrawer,
    "gapcircle": partial(svg_drawers.SvgPathCircleDrawer, size_ratio=GAP_RATIO),
}
"""Box style names mapped to SVG module drawer factories."""

COLOR_MASKS = {
    "solid": colormasks.SolidFillColorMask,
    "rgrad": colormasks.RadialGradiantColorMask,
    "sgrad": colormasks.SquareGradiantColorMask,
    "hgrad": colormasks.HorizontalGradiantColorMask,
    "vgrad": colormasks.VerticalGradiantColorMask,
    "image": colormasks.ImageColorMask,
}
"""Color mask names mapped to the PNG color mask classes."""

SVG_GRADIENTS = {
    "solid": None,
    "rgrad": "radial",
    "hgrad": "horizontal",
    "vgrad": "vertical",
}
"""Color masks available for SVG mapped to SVG gradient shapes."""

FORMATS = (".png", ".svg")
"""Supported output file extensions."""

LOGO_RATIO_RANGE = (0.05, 0.5)
"""Smallest and largest allowed logo width relative to the code."""


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
        Output format. SVG supports the box styles in `SVG_DRAWERS`
        and the color masks in `SVG_GRADIENTS`.
    box_size : int, default 10
        Pixels per module (box).
    border : int, default 4
        Border width in modules. The QR standard recommends at least 4;
        smaller borders are allowed, e.g. for cropping.
    box_style : str, default "square"
        Key of `PNG_DRAWERS` or `SVG_DRAWERS`.
    eye_style : str, default "square"
        Style of the three finder patterns ("eyes"), same keys as
        `box_style`.
    color_mask : str, default "solid"
        Key of `COLOR_MASKS` or `SVG_GRADIENTS`.
    back_color : tuple of int, default (255, 255, 255)
        Background RGB color.
    back_opacity : float, default 1.0
        Background opacity from 0 (fully transparent) to 1 (opaque).
    front_color : tuple of int, default (0, 0, 0)
        Face (module) RGB color, or the start color of a gradient.
    edge_color : tuple of int, default (0, 0, 255)
        End color of the gradient color masks.
    mask_image_path : str or None, default None
        Path to the image used by the "image" color mask.
    embedded_image_path : str or None, default None
        Path to an image embedded in the center of the QR code, or
        None for no image.
    logo_ratio : float, default 0.25
        Width of the embedded image relative to the QR code width.
    """

    data: str
    version: int = 1
    error_correction: str = "M"
    extension: str = ".png"
    box_size: int = 10
    border: int = 4
    box_style: str = "square"
    eye_style: str = "square"
    color_mask: str = "solid"
    back_color: Color = (255, 255, 255)
    back_opacity: float = 1.0
    front_color: Color = (0, 0, 0)
    edge_color: Color = (0, 0, 255)
    mask_image_path: str | None = None
    embedded_image_path: str | None = None
    logo_ratio: float = 0.25


def check_settings(settings):
    """Check that settings are valid before generating a QR code.

    Parameters
    ----------
    settings : QrSettings
        Options of the QR code.

    Raises
    ------
    ValueError
        With a user-readable message describing the first problem
        found.
    """
    if not 1 <= settings.version <= 40:
        raise ValueError("Size standard must be from 1 to 40.")
    if settings.box_size < 1:
        raise ValueError("Box size must be at least 1 pixel.")
    if settings.border < 0:
        raise ValueError("Border size must not be negative.")
    if not 0 <= settings.back_opacity <= 1:
        raise ValueError("Background opacity must be from 0 to 100 %.")
    if settings.error_correction not in ERROR_CORRECTIONS:
        raise ValueError(
            f"Unknown error correction {settings.error_correction!r}."
        )
    if settings.extension not in FORMATS:
        raise ValueError(f"Unknown image extension {settings.extension!r}.")
    svg = settings.extension == ".svg"
    styles = SVG_DRAWERS if svg else PNG_DRAWERS
    masks = SVG_GRADIENTS if svg else COLOR_MASKS
    image_format = "SVG" if svg else "PNG"
    for value, options, name in (
        (settings.box_style, styles, "box style"),
        (settings.eye_style, styles, "eye style"),
        (settings.color_mask, masks, "color mask"),
    ):
        if value not in options:
            raise ValueError(f"Unknown {name} {value!r} for {image_format}.")
    if settings.embedded_image_path is not None:
        _check_logo(settings)
    if settings.color_mask == "image" and not (
        settings.mask_image_path and Path(settings.mask_image_path).is_file()
    ):
        raise ValueError(f"Image mask {settings.mask_image_path!r} not found.")


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

    Raises
    ------
    ValueError
        If the settings are invalid, see `check_settings`.
    """
    check_settings(settings)
    is_svg = settings.extension == ".svg"
    qr = qrcode.QRCode(
        version=settings.version,
        error_correction=ERROR_CORRECTIONS[settings.error_correction],
        box_size=settings.box_size,
        border=settings.border,
        image_factory=StyledSvgImage if is_svg else StyledPilImage,
    )
    qr.add_data(settings.data)
    qr.make(fit=True)
    logo = (
        None
        if settings.embedded_image_path is None
        else load_logo(settings.embedded_image_path)
    )
    if is_svg:
        return qr.make_image(
            module_drawer=SVG_DRAWERS[settings.box_style](),
            eye_drawer=SVG_DRAWERS[settings.eye_style](),
            style=SvgStyle(
                back_color=settings.back_color,
                back_opacity=settings.back_opacity,
                front_color=settings.front_color,
                edge_color=settings.edge_color,
                gradient=SVG_GRADIENTS[settings.color_mask],
                logo=logo,
                logo_ratio=settings.logo_ratio,
            ),
        )
    logo_options = {}
    if logo is not None:
        logo_options = {
            "embedded_image": logo,
            "embedded_image_ratio": settings.logo_ratio,
        }
    return qr.make_image(
        module_drawer=PNG_DRAWERS[settings.box_style](),
        eye_drawer=PNG_DRAWERS[settings.eye_style](),
        color_mask=_make_color_mask(settings),
        **logo_options,
    )


def make_preview(settings, size):
    """Render a QR code as a PIL image that fits into a square.

    The preview is drawn with a smaller box size when possible, so it
    stays fast even for large QR codes. SVG settings are previewed with
    the equivalent PNG options.

    Parameters
    ----------
    settings : QrSettings
        Options of the QR code.
    size : int
        Maximum width and height of the preview in pixels.

    Returns
    -------
    PIL.Image.Image
        The preview image.

    Raises
    ------
    ValueError
        If the settings are invalid, see `check_settings`.
    """
    check_settings(settings)
    # every SVG option has a PNG equivalent
    settings = replace(settings, extension=".png")
    # fix the version first, then draw at about twice the preview size
    qr = qrcode.QRCode(
        version=settings.version,
        error_correction=ERROR_CORRECTIONS[settings.error_correction],
        border=settings.border,
    )
    qr.add_data(settings.data)
    qr.make(fit=True)
    modules = qr.modules_count + 2 * settings.border
    box_size = min(settings.box_size, max(1, -(-2 * size // modules)))
    image = make_qr_image(
        replace(settings, version=qr.version, box_size=box_size)
    ).get_image()
    scale = size / max(image.size)
    resample = (
        Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.LANCZOS
    )
    return image.resize(
        (round(image.width * scale), round(image.height * scale)), resample
    )


def load_logo(path):
    """Load an image to embed, padded to a square if necessary.

    qrcode stretches embedded images to a square; padding non-square
    images with transparency keeps their proportions.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the image.

    Returns
    -------
    PIL.Image.Image
        The image, square.
    """
    with Image.open(path) as image:
        logo = image.copy()
    if logo.width == logo.height:
        return logo
    side = max(logo.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(
        logo.convert("RGBA"),
        ((side - logo.width) // 2, (side - logo.height) // 2),
    )
    return square


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


def _check_logo(settings):
    """Check the embedded image settings.

    Parameters
    ----------
    settings : QrSettings
        Options of the QR code, with an embedded image.

    Raises
    ------
    ValueError
        If the image is missing or unreadable, the logo size is out of
        range, or error correction is not H.
    """
    path = settings.embedded_image_path
    if not Path(path).is_file():
        raise ValueError(f"Embedded image {path!r} not found.")
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, SyntaxError):  # PIL raises SyntaxError for some files
        raise ValueError(f"Embedded image {path!r} is not an image.") from None
    low, high = LOGO_RATIO_RANGE
    if not low <= settings.logo_ratio <= high:
        raise ValueError(
            f"Logo size must be from {low:.0%} to {high:.0%} of the width."
        )
    if settings.error_correction != "H":
        raise ValueError("Embedding an image requires error correction H.")


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
    alpha = round(settings.back_opacity * 255)
    # qrcode switches to RGBA when the background has 4 values; all
    # other colors then need an alpha value too
    transparent = alpha < 255
    back, front, edge = (
        settings.back_color,
        settings.front_color,
        settings.edge_color,
    )
    if transparent:
        back, front, edge = (*back, alpha), (*front, 255), (*edge, 255)
    if settings.color_mask == "solid":
        return mask_class(back, front)
    if settings.color_mask == "image":
        # convert, so palette or grayscale images give matching pixels
        with Image.open(settings.mask_image_path) as image:
            colors = image.convert("RGBA" if transparent else "RGB")
        return mask_class(back, color_mask_image=colors)
    return mask_class(back, front, edge)
