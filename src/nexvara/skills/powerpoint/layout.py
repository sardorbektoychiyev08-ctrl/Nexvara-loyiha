"""Pure layout checks for slides: overlapping shapes and overflowing text."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Box:
    name: str
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


def overlaps(a: Box, b: Box, tolerance: float = 1.0) -> bool:
    """True if the boxes share more than `tolerance` points in both directions."""
    dx = min(a.right, b.right) - max(a.left, b.left)
    dy = min(a.bottom, b.bottom) - max(a.top, b.top)
    return dx > tolerance and dy > tolerance


def find_overlaps(boxes: list[Box], tolerance: float = 1.0) -> list[tuple[str, str]]:
    return [(a.name, b.name) for a, b in combinations(boxes, 2) if overlaps(a, b, tolerance)]


def outside_slide(box: Box, width: float, height: float, tolerance: float = 1.0) -> bool:
    return (
        box.left < -tolerance
        or box.top < -tolerance
        or box.right > width + tolerance
        or box.bottom > height + tolerance
    )


def text_overflows(text_height: float, shape_height: float, tolerance: float = 2.0) -> bool:
    return text_height > shape_height + tolerance
