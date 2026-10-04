"""Tests of the GUI-independent QR code generation."""

import base64
import io
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


@pytest.mark.parametrize("box_style", core.PNG_DRAWERS)
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


@pytest.mark.parametrize(
    ("eye_style", "corner"), [("square", FRONT), ("circle", BACK)]
)
def test_png_eye_style(tmp_path, eye_style, corner):
    # the top-left eye's outer corner pixel is only set for squares;
    # big boxes keep that pixel clear of the circles' antialiasing
    box = 20
    path = render(
        tmp_path,
        settings(box_style="circle", eye_style=eye_style, box_size=box),
    )
    with Image.open(path) as img:
        assert img.getpixel((BORDER * box, BORDER * box))[:3] == corner


def test_png_logo_size(tmp_path, logo):
    def red_pixels(ratio):
        path = render(
            tmp_path, settings(embedded_image_path=logo, logo_ratio=ratio)
        )
        with Image.open(path) as img:
            colors = img.convert("RGB").getcolors(maxcolors=1 << 24)
        return dict((color, n) for n, color in colors).get((255, 0, 0), 0)

    assert red_pixels(0.4) > 2 * red_pixels(0.2)


def test_load_logo_pads_to_square(tmp_path):
    path = tmp_path / "wide.png"
    Image.new("RGB", (60, 20), (255, 0, 0)).save(path)
    logo = core.load_logo(path)
    assert logo.size == (60, 60)
    assert logo.getpixel((30, 30)) == (255, 0, 0, 255)
    assert logo.getpixel((30, 5))[3] == 0  # transparent padding


def test_load_logo_keeps_square_images(logo):
    image = core.load_logo(logo)
    assert (image.size, image.mode) == ((60, 60), "RGB")


# --- SVG -------------------------------------------------------------


def svg_root(tmp_path, **kwargs):
    path = render(tmp_path, settings(extension=".svg", **kwargs))
    assert path.suffix == ".svg"
    return ET.parse(path).getroot()


def children(root, tag):
    return [el for el in root.iter() if el.tag.rpartition("}")[2] == tag]


@pytest.mark.parametrize("box_style", core.SVG_DRAWERS)
@pytest.mark.parametrize("eye_style", core.SVG_DRAWERS)
def test_svg_styles(tmp_path, box_style, eye_style):
    root = svg_root(tmp_path, box_style=box_style, eye_style=eye_style)
    assert root.tag.endswith("svg")
    assert len(children(root, "path")) == 1  # single path, no seams


def test_svg_colors(tmp_path):
    root = svg_root(tmp_path)
    assert children(root, "rect")[0].get("fill") == "#ffff00"
    assert children(root, "path")[0].get("fill") == "#000080"


@pytest.mark.parametrize(
    ("color_mask", "tag", "geometry"),
    [
        ("rgrad", "radialGradient", {"cx", "cy", "r"}),
        ("hgrad", "linearGradient", {"x1", "x2"}),
        ("vgrad", "linearGradient", {"y1", "y2"}),
    ],
)
def test_svg_gradients(tmp_path, color_mask, tag, geometry):
    root = svg_root(tmp_path, color_mask=color_mask, edge_color=(1, 2, 3))
    (gradient,) = children(root, tag)
    assert geometry <= set(gradient.attrib)
    stops = [stop.get("stop-color") for stop in children(gradient, "stop")]
    assert stops == ["#000080", "#010203"]
    assert children(root, "path")[0].get("fill") == "url(#qr-gradient)"


def test_svg_logo(tmp_path, logo):
    root = svg_root(tmp_path, embedded_image_path=logo)
    (image,) = children(root, "image")
    href = image.get("{http://www.w3.org/1999/xlink}href")
    assert href.startswith("data:image/png;base64,")
    data = base64.b64decode(href.partition(",")[2])
    with Image.open(io.BytesIO(data)) as embedded:
        assert embedded.size == (60, 60)
    assert float(image.get("width")) > 0


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
        ({"eye_style": "triangle"}, "Unknown eye style"),
        (
            {"extension": ".svg", "box_style": "vbars"},
            "box style 'vbars' for SVG",
        ),
        ({"extension": ".svg", "eye_style": "rounded"}, "eye style"),
        ({"extension": ".svg", "color_mask": "sgrad"}, "color mask"),
        ({"extension": ".svg", "color_mask": "image"}, "color mask"),
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


@pytest.mark.parametrize("ratio", [0.01, 0.6])
def test_logo_size_out_of_range(logo, ratio):
    with pytest.raises(ValueError, match="Logo size"):
        core.check_settings(
            settings(embedded_image_path=logo, logo_ratio=ratio)
        )


def test_embedded_file_must_be_an_image(tmp_path):
    path = tmp_path / "notes.png"
    path.write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="not an image"):
        core.check_settings(settings(embedded_image_path=str(path)))


@pytest.mark.parametrize("extension", core.FORMATS)
def test_embedded_image_requires_h_for_both_formats(logo, extension):
    with pytest.raises(ValueError, match="error correction H"):
        core.check_settings(
            settings(
                extension=extension,
                embedded_image_path=logo,
                error_correction="Q",
            )
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


def test_preview_of_svg_uses_its_colors():
    image = core.make_preview(settings(extension=".svg"), 300)
    assert image.convert("RGB").getpixel((0, 0)) == BACK


def test_border_below_four_is_allowed(tmp_path):
    path = render(tmp_path, settings(border=0))
    with Image.open(path) as img:
        assert img.size == (21 * BOX, 21 * BOX)


def test_preview_validates():
    with pytest.raises(ValueError, match="Border size"):
        core.make_preview(settings(border=-1), 300)


def test_output_path(tmp_path):
    assert core.output_path(tmp_path, "a", ".png") == tmp_path / "a.png"


# --- background opacity ----------------------------------------------


@pytest.fixture
def palette_mask(tmp_path):
    # palette images used to crash the image color mask
    path = tmp_path / "palette.png"
    Image.new("P", (40, 40), 7).save(path)
    return str(path)


@pytest.mark.parametrize("opacity", [1.0, 0.5, 0.0])
@pytest.mark.parametrize("color_mask", core.COLOR_MASKS)
def test_png_opacity_all_masks(tmp_path, palette_mask, opacity, color_mask):
    path = render(
        tmp_path,
        settings(
            back_opacity=opacity,
            color_mask=color_mask,
            mask_image_path=palette_mask,
            box_style="circle",
        ),
    )
    with Image.open(path) as img:
        assert img.mode == ("RGB" if opacity == 1 else "RGBA")
        if opacity < 1:
            corner = img.getpixel((0, 0))
            assert corner == (*BACK, round(opacity * 255))


def test_png_transparent_modules_stay_opaque(tmp_path):
    path = render(tmp_path, settings(back_opacity=0.0))
    with Image.open(path) as img:
        finder = BORDER * BOX + BOX // 2
        assert img.getpixel((finder, finder)) == (*FRONT, 255)


@pytest.mark.parametrize(
    ("opacity", "rects", "fill_opacity"),
    [(1.0, 1, None), (0.4, 1, "0.4"), (0.0, 0, None)],
)
def test_svg_opacity(tmp_path, opacity, rects, fill_opacity):
    root = svg_root(tmp_path, back_opacity=opacity)
    found = children(root, "rect")
    assert len(found) == rects
    if found:
        assert found[0].get("fill-opacity") == fill_opacity


@pytest.mark.parametrize("opacity", [-0.1, 1.1])
def test_opacity_out_of_range(opacity):
    with pytest.raises(ValueError, match="Background opacity"):
        core.check_settings(settings(back_opacity=opacity))


def test_preview_keeps_transparency():
    image = core.make_preview(settings(back_opacity=0.0), 300)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
