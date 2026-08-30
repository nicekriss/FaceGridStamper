from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
import math

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageStat

try:
    import cv2
    import numpy as np
except ImportError:  # The GUI explains how to run setup when these are missing.
    cv2 = None
    np = None


VALID_MODES = ("grid", "keep", "erase")


@dataclass
class FaceRegion:
    x: float
    y: float
    width: float
    height: float
    angle: float = 0.0
    score: float = 1.0
    mode: str = "grid"

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            self.mode = "grid"

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x2 and self.y <= y <= self.y2

    def cycle_mode(self) -> None:
        self.mode = VALID_MODES[(VALID_MODES.index(self.mode) + 1) % len(VALID_MODES)]

    def to_dict(self) -> dict:
        return asdict(self)


def _iou(a: FaceRegion, b: FaceRegion) -> float:
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x2, b.x2)
    bottom = min(a.y2, b.y2)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = a.width * a.height + b.width * b.height - intersection
    return intersection / union if union else 0.0


def _deduplicate(regions: Iterable[FaceRegion], overlap: float = 0.35) -> list[FaceRegion]:
    kept: list[FaceRegion] = []
    for candidate in sorted(regions, key=lambda item: item.score, reverse=True):
        if all(_iou(candidate, existing) < overlap for existing in kept):
            kept.append(candidate)
    return sorted(kept, key=lambda item: (item.y, item.x))


def _detect_yunet(image: Image.Image, model_path: Path, threshold: float) -> list[FaceRegion]:
    rgb = np.asarray(image.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    detector = cv2.FaceDetectorYN.create(
        str(model_path), "", (width, height), float(threshold), 0.3, 5000
    )
    detector.setInputSize((width, height))
    _unused, faces = detector.detect(bgr)
    if faces is None:
        return []

    regions: list[FaceRegion] = []
    for face in faces:
        x, y, w, h = [float(value) for value in face[:4]]
        right_eye = (float(face[4]), float(face[5]))
        left_eye = (float(face[6]), float(face[7]))
        angle = math.degrees(
            math.atan2(left_eye[1] - right_eye[1], left_eye[0] - right_eye[0])
        )
        regions.append(
            FaceRegion(
                max(0.0, x),
                max(0.0, y),
                min(w, width - max(0.0, x)),
                min(h, height - max(0.0, y)),
                angle=angle,
                score=float(face[-1]),
            )
        )
    return _deduplicate(regions)


def _detect_haar(image: Image.Image) -> list[FaceRegion]:
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    cascades = [
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
        cv2.data.haarcascades + "haarcascade_profileface.xml",
    ]
    regions: list[FaceRegion] = []
    for cascade_path in cascades:
        cascade = cv2.CascadeClassifier(cascade_path)
        for x, y, w, h in cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=4, minSize=(24, 24)
        ):
            regions.append(FaceRegion(float(x), float(y), float(w), float(h), score=0.5))
    return _deduplicate(regions)


def detect_faces(
    image: Image.Image, model_path: str | Path | None = None, threshold: float = 0.72
) -> list[FaceRegion]:
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV가 설치되지 않았습니다. setup.ps1을 먼저 실행하세요.")
    path = Path(model_path) if model_path else None
    if path and path.exists() and hasattr(cv2, "FaceDetectorYN"):
        try:
            return _detect_yunet(image, path, threshold)
        except cv2.error:
            pass
    return _detect_haar(image)


def _expanded_box(
    region: FaceRegion, image_size: tuple[int, int], margin_percent: float
) -> tuple[int, int, int, int]:
    margin_x = region.width * margin_percent / 100.0
    margin_y = region.height * margin_percent / 100.0
    left = max(0, int(round(region.x - margin_x)))
    top = max(0, int(round(region.y - margin_y)))
    right = min(image_size[0], int(round(region.x2 + margin_x)))
    bottom = min(image_size[1], int(round(region.y2 + margin_y)))
    return left, top, max(left + 1, right), max(top + 1, bottom)


def _draw_line_family(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    angle_degrees: float,
    spacing: int,
    fill: tuple[int, int, int, int],
    width: int,
) -> None:
    patch_w, patch_h = size
    diagonal = int(math.ceil(math.hypot(patch_w, patch_h)))
    theta = math.radians(angle_degrees)
    direction = (math.cos(theta), math.sin(theta))
    normal = (-direction[1], direction[0])
    cx, cy = patch_w / 2.0, patch_h / 2.0
    for offset in range(-diagonal, diagonal + spacing, spacing):
        ox, oy = normal[0] * offset, normal[1] * offset
        p1 = (cx + ox - direction[0] * diagonal, cy + oy - direction[1] * diagonal)
        p2 = (cx + ox + direction[0] * diagonal, cy + oy + direction[1] * diagonal)
        draw.line((p1, p2), fill=fill, width=width)


def _sample_surrounding_color(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    left, top, right, bottom = box
    outer_left = max(0, left - (right - left) // 4)
    outer_top = max(0, top - (bottom - top) // 4)
    outer_right = min(image.width, right + (right - left) // 4)
    outer_bottom = min(image.height, bottom + (bottom - top) // 4)
    crop = image.convert("RGB").crop((outer_left, outer_top, outer_right, outer_bottom))
    if np is not None:
        pixels = np.asarray(crop).reshape(-1, 3)
        return tuple(int(value) for value in np.median(pixels, axis=0))
    mean = ImageStat.Stat(crop).mean
    return tuple(int(value) for value in mean[:3])


def render_regions(
    image: Image.Image,
    regions: Iterable[FaceRegion],
    *,
    color: str | tuple[int, int, int] = "#0b1830",
    opacity: int = 235,
    spacing_percent: float = 11.0,
    thickness_percent: float = 1.15,
    margin_percent: float = 6.0,
) -> Image.Image:
    base = image.convert("RGBA")
    rgb = ImageColor.getrgb(color) if isinstance(color, str) else color

    for region in regions:
        if region.mode == "keep":
            continue
        box = _expanded_box(region, base.size, margin_percent)
        left, top, right, bottom = box
        patch_size = (right - left, bottom - top)
        mask = Image.new("L", patch_size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, patch_size[0] - 1, patch_size[1] - 1), fill=255)

        if region.mode == "erase":
            fill_color = _sample_surrounding_color(base, box)
            fill_layer = Image.new("RGBA", patch_size, (*fill_color, 255))
            base.alpha_composite(Image.composite(fill_layer, Image.new("RGBA", patch_size), mask), (left, top))
            continue

        spacing = max(4, int(round(region.width * spacing_percent / 100.0)))
        thickness = max(1, int(round(region.width * thickness_percent / 100.0)))
        line_layer = Image.new("RGBA", patch_size, (0, 0, 0, 0))
        line_draw = ImageDraw.Draw(line_layer)
        line_color = (*rgb, max(0, min(255, int(opacity))))
        _draw_line_family(line_draw, patch_size, 72.0 + region.angle, spacing, line_color, thickness)
        _draw_line_family(line_draw, patch_size, 108.0 + region.angle, spacing, line_color, thickness)
        alpha = ImageChops.multiply(line_layer.getchannel("A"), mask)
        line_layer.putalpha(alpha)
        base.alpha_composite(line_layer, (left, top))

    return base

