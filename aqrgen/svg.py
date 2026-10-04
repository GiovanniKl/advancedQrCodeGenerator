"""SVG output with colors, gradients and an embedded logo.

qrcode's own SVG images are black on white or transparent.
`StyledSvgImage` extends the single-path SVG image with the options the
PNG output has: background and face colors, radial/horizontal/vertical
gradients matching qrcode's PNG color masks, and a logo in the center.
"""

import base64
import io
import math
from dataclasses import dataclass

from qrcode.compat.etree import ET
from qrcode.image.svg import SvgPathImage

XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
"""Namespace of the ``xlink:href`` attribute used for the logo."""

MAX_LOGO_SIZE = 1024
"""Logos are scaled down to this width or height before embedding."""

ET.register_namespace("xlink", XLINK_NAMESPACE)


def hex_color(color):
    """Format an RGB color for SVG.

    Parameters
    ----------
    color : tuple of int
        The ``(r, g, b)`` color.

    Returns
    -------
    str
        The color as ``#rrggbb``.
    """
    return "#{:02x}{:02x}{:02x}".format(*color)


@dataclass
class SvgStyle:
    """Colors, gradient and logo of a `StyledSvgImage`.

    Attributes
    ----------
    back_color : tuple of int, default (255, 255, 255)
        Background RGB color.
    back_opacity : float, default 1.0
        Background opacity from 0 (no background) to 1 (opaque).
    front_color : tuple of int, default (0, 0, 0)
        Face RGB color, or the start color of a gradient (center,
        left or top).
    edge_color : tuple of int, default (0, 0, 255)
        End color of a gradient (edge, right or bottom).
    gradient : {None, "radial", "horizontal", "vertical"}, optional
        Gradient shape, None for a solid face color.
    logo : PIL.Image.Image, optional
        Square image embedded in the center.
    logo_ratio : float, default 0.25
        Logo width relative to the image width.
    """

    back_color: tuple = (255, 255, 255)
    back_opacity: float = 1.0
    front_color: tuple = (0, 0, 0)
    edge_color: tuple = (0, 0, 255)
    gradient: str | None = None
    logo: object = None
    logo_ratio: float = 0.25


class StyledSvgImage(SvgPathImage):
    """Single-path SVG image with colors, a gradient and a logo.

    Parameters
    ----------
    *args
        Positional arguments of `qrcode.image.svg.SvgPathImage`.
    style : SvgStyle, optional
        Colors, gradient and logo. Black on white without one.
    **kwargs
        Keyword arguments of `qrcode.image.svg.SvgPathImage`.
    """

    def __init__(self, *args, style=None, **kwargs):
        self.style = SvgStyle() if style is None else style
        opacity = self.style.back_opacity
        self.background = hex_color(self.style.back_color) if opacity else None
        super().__init__(*args, **kwargs)
        if 0 < opacity < 1:
            # the background rect is created by SvgImage._svg
            self._img.find("rect").set("fill-opacity", f"{opacity:g}")

    def process(self):
        """Build the QR code path, then apply the fill and the logo."""
        super().process()
        if self.style.gradient is None:
            self.path.set("fill", hex_color(self.style.front_color))
        else:
            defs = ET.Element("defs")
            defs.append(self._gradient_element("qr-gradient"))
            self._img.insert(0, defs)
            self.path.set("fill", "url(#qr-gradient)")
        if self.style.logo is not None:
            self._img.append(self._logo_element())

    def _gradient_element(self, element_id):
        """Create the gradient definition, matching the PNG masks.

        Parameters
        ----------
        element_id : str
            ``id`` attribute of the gradient.

        Returns
        -------
        xml.etree.ElementTree.Element
            A ``radialGradient`` or ``linearGradient`` element.
        """
        size = float(self.units(self.pixel_size, text=False))
        if self.style.gradient == "radial":
            # PNG: distance from the center, 1 at the corners
            tag = "radialGradient"
            geometry = {
                "cx": size / 2,
                "cy": size / 2,
                "r": size / math.sqrt(2),
            }
        elif self.style.gradient == "horizontal":
            tag = "linearGradient"
            geometry = {"x1": 0, "y1": 0, "x2": size, "y2": 0}
        else:
            tag = "linearGradient"
            geometry = {"x1": 0, "y1": 0, "x2": 0, "y2": size}
        element = ET.Element(
            tag,
            id=element_id,
            gradientUnits="userSpaceOnUse",
            **{key: f"{value:.3f}" for key, value in geometry.items()},
        )
        stops = (("0", self.style.front_color), ("1", self.style.edge_color))
        for offset, color in stops:
            ET.SubElement(
                element,
                "stop",
                offset=offset,
                **{"stop-color": hex_color(color)},
            )
        return element

    def _logo_element(self):
        """Create the embedded logo, placed like in the PNG output.

        Returns
        -------
        xml.etree.ElementTree.Element
            An ``image`` element with the logo as a base64 PNG.
        """
        # same placement as qrcode's StyledPilImage.draw_embedded_image
        total = self.pixel_size
        approximate = int(total * self.style.logo_ratio)
        offset = (
            int((int(total / 2) - int(approximate / 2)) / self.box_size)
            * self.box_size
        )
        width = total - 2 * offset
        logo = self.style.logo.copy()
        logo.thumbnail((MAX_LOGO_SIZE, MAX_LOGO_SIZE))
        buffer = io.BytesIO()
        logo.save(buffer, format="PNG")
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return ET.Element(
            "image",
            x=self.units(offset, text=False).to_eng_string(),
            y=self.units(offset, text=False).to_eng_string(),
            width=self.units(width, text=False).to_eng_string(),
            height=self.units(width, text=False).to_eng_string(),
            preserveAspectRatio="xMidYMid meet",
            **{f"{{{XLINK_NAMESPACE}}}href": f"data:image/png;base64,{data}"},
        )
