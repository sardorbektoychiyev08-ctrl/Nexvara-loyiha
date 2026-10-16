from nexvara.skills.powerpoint.layout import (
    Box,
    find_overlaps,
    outside_slide,
    overlaps,
    text_overflows,
)


def test_overlaps():
    a = Box("a", 0, 0, 100, 100)
    assert overlaps(a, Box("b", 50, 50, 100, 100))
    assert not overlaps(a, Box("c", 100, 0, 50, 50))  # touching edge
    assert not overlaps(a, Box("d", 0.5, 99.5, 10, 10))  # within tolerance
    assert not overlaps(a, Box("e", 200, 200, 10, 10))


def test_find_overlaps_pairs():
    boxes = [Box("a", 0, 0, 10, 10), Box("b", 5, 5, 10, 10), Box("c", 50, 50, 5, 5)]
    assert find_overlaps(boxes) == [("a", "b")]


def test_outside_slide_and_overflow():
    assert outside_slide(Box("x", 900, 0, 100, 10), 960, 540)
    assert not outside_slide(Box("y", 0, 0, 960, 540), 960, 540)
    assert text_overflows(50, 20)
    assert not text_overflows(21, 20)
