"""Tests of the GUI-independent QR code generation."""

import time
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from aqrgen import core

BOX = 4
BORDER = 4
# version 1 is 21x21 modules; "hello" fits into version 1 even at "H"
SIDE = (21 + 2 * BORDER) * BOX

BACK = (255, 255, 0)
FRONT = (0, 0, 128)


@pytest.fixture
def logo(tmp_path):
    path = tmp_path / "logo.png"
    Image.new("RGB", (60, 60), (255, 0, 0)).save(path)
    return str(path)


def settings(**kwargs):
    defaults = {
        "data": "hello",
        "error_correction": "H",
        "box_size": BOX,
        "border": BORDER,
        "back_color": BACK,
        "front_color": FRONT,
    }
    return core.QrSettings(**(defaults | kwargs))


def render(tmp_path, qr_settings):
    path = core.save_qr_image(
        core.make_qr_image(qr_settings),
        tmp_path,
        "qr",
        qr_settings.extension,
    )
    return path


# --- parse_color -----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(255, 128, 0)", (255, 128, 0)),
        ("255,128,0", (255, 128, 0)),
        ("  ( 0 , 0 , 0 )  ", (0, 0, 0)),
        ("#ff8000", (255, 128, 0)),
        ("#FF8000", (255, 128, 0)),
    ],
)
def test_parse_color_valid(text, expected):
    assert core.parse_color(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "(255, 255)",
        "(255, 255, 255, 255)",
        "(256, 0, 0)",
        "(-1, 0, 0)",
        "(1.5, 0, 0)",
        "red",
        "#fff",
        "#gggggg",
        "__import__('os').getcwd()",
    ],
)
def test_parse_color_invalid(text):
    with pytest.raises(ValueError, match="color|triplet"):
        core.parse_color(text)


# --- make_qr_image ---------------------------------------------------


@pytest.mark.parametrize("box_style", core.MODULE_DRAWERS)
@pytest.mark.parametrize("color_mask", core.COLOR_MASKS)
def test_png_all_styles_and_masks(tmp_path, logo, box_style, color_mask):
    path = render(
        tmp_path,
        settings(
            box_style=box_style, color_mask=color_mask, mask_image_path=logo
        ),
    )
    with Image.open(path) as img:
        assert img.size == (SIDE, SIDE)
        # the border is always background
        assert img.getpixel((0, 0))[:3] == BACK


def test_png_solid_colors(tmp_path):
    path = render(tmp_path, settings())
    with Image.open(path) as img:
        # center of the top-left module of the finder pattern
        finder = BORDER * BOX + BOX // 2
        assert img.getpixel((finder, finder))[:3] == FRONT


def test_png_embedded_image(tmp_path, logo):
    path = render(tmp_path, settings(embedded_image_path=logo))
    with Image.open(path) as img:
        assert img.getpixel((SIDE // 2, SIDE // 2))[:3] == (255, 0, 0)


def test_version_grows_to_fit_data(tmp_path):
    path = render(tmp_path, settings(data="x" * 100))
    with Image.open(path) as img:
        assert img.size[0] > SIDE


def test_svg(tmp_path):
    # styling options are ignored for SVG
    path = render(tmp_path, settings(extension=".svg", box_style="circle"))
    assert path.suffix == ".svg"
    assert ET.parse(path).getroot().tag.endswith("svg")


# --- check_settings --------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"version": 0}, "Size standard"),
        ({"version": 41}, "Size standard"),
        ({"box_size": 0}, "Box size"),
        ({"border": -1}, "Border size"),
        ({"error_correction": "X"}, "Unknown error correction"),
        ({"extension": ".jpg"}, "Unknown image extension"),
        ({"box_style": "triangle"}, "Unknown box style"),
        ({"color_mask": "plaid"}, "Unknown color mask"),
        ({"embedded_image_path": "missing.png"}, "Embedded image"),
        ({"color_mask": "image"}, "Image mask"),
        ({"color_mask": "image", "mask_image_path": "x.png"}, "Image mask"),
    ],
)
def test_invalid_settings(changes, message):
    with pytest.raises(ValueError, match=message):
        core.make_qr_image(settings(**changes))


def test_embedded_image_requires_h(logo):
    with pytest.raises(ValueError, match="error correction H"):
        core.check_settings(
            settings(embedded_image_path=logo, error_correction="M")
        )


def test_svg_ignores_png_only_options():
    core.check_settings(
        settings(extension=".svg", color_mask="image", error_correction="L")
    )


# --- make_preview ----------------------------------------------------


@pytest.mark.parametrize("version", [1, 10, 40])
def test_preview_fits_size(version):
    image = core.make_preview(settings(version=version), 300)
    assert max(image.size) == 300


def test_preview_of_large_code_is_fast():
    start = time.perf_counter()
    core.make_preview(
        settings(version=40, box_size=50, box_style="circle"), 300
    )
    assert time.perf_counter() - start < 5


def test_preview_of_svg_is_black_and_white():
    image = core.make_preview(settings(extension=".svg"), 300)
    assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)


def test_border_below_four_is_allowed(tmp_path):
    path = render(tmp_path, settings(border=0))
    with Image.open(path) as img:
        assert img.size == (21 * BOX, 21 * BOX)


def test_preview_validates():
    with pytest.raises(ValueError, match="Border size"):
        core.make_preview(settings(border=-1), 300)


def test_output_path(tmp_path):
    assert core.output_path(tmp_path, "a", ".png") == tmp_path / "a.png"
