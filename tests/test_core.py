from pathlib import Path
import sys

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from face_grid_core import FaceRegion, render_regions


def test_grid_changes_only_target_region(tmp_path):
    image = Image.new("RGB", (320, 240), "#d8d0ca")
    region = FaceRegion(100, 40, 100, 130)
    rendered = render_regions(image, [region])
    assert rendered.getpixel((10, 10))[:3] == image.getpixel((10, 10))
    difference = ImageChops.difference(rendered.convert("RGB"), image)
    assert difference.getbbox() is not None
    left, top, right, bottom = difference.getbbox()
    assert 90 <= left < right <= 210
    assert 30 <= top < bottom <= 180
    output = tmp_path / "grid.png"
    rendered.save(output)
    assert output.exists()


def test_keep_mode_is_pixel_identical():
    image = Image.new("RGB", (120, 120), "white")
    region = FaceRegion(20, 20, 80, 80, mode="keep")
    rendered = render_regions(image, [region]).convert("RGB")
    assert list(rendered.getdata()) == list(image.getdata())


def test_cycle_modes():
    region = FaceRegion(0, 0, 10, 10)
    assert region.mode == "grid"
    region.cycle_mode()
    assert region.mode == "keep"
    region.cycle_mode()
    assert region.mode == "erase"
    region.cycle_mode()
    assert region.mode == "grid"
