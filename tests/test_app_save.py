from pathlib import Path
import json
import sys
import tkinter as tk

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import DEFAULT_SETTINGS, Document, FaceGridApp
from face_grid_core import FaceRegion


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Status:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


def test_default_save_is_next_to_source_with_embedded_metadata(tmp_path):
    source_path = tmp_path / "character_sheet.png"
    Image.new("RGB", (240, 180), "#ded8d2").save(source_path)

    app = FaceGridApp.__new__(FaceGridApp)
    app.documents = [
        Document(
            source_path,
            Image.open(source_path).convert("RGBA"),
            [FaceRegion(70, 25, 90, 110)],
        )
    ]
    app.grid_color = DEFAULT_SETTINGS["grid_color"]
    app.opacity = Value(DEFAULT_SETTINGS["opacity"])
    app.spacing = Value(DEFAULT_SETTINGS["spacing"])
    app.thickness = Value(DEFAULT_SETTINGS["thickness"])
    app.margin = Value(DEFAULT_SETTINGS["margin"])
    app.status = Status()

    app._save_documents(None)

    output_path = tmp_path / "character_sheet_얼굴격자.png"
    assert source_path.exists()
    assert output_path.exists()
    with Image.open(output_path) as result:
        metadata = json.loads(result.info["FaceGridStamper"])
    assert metadata["source"] == str(source_path)
    assert metadata["regions"][0]["mode"] == "grid"
    assert "저장했습니다" in app.status.value

