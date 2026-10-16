from nexvara.app.main import MIN_SIZE, WANTED_SIZE, window_geometry


def test_small_laptop_screen_fits():
    # 1920x1080 at 125%: 1536x816 usable above the taskbar.
    g = window_geometry((0, 0, 1536, 816))
    assert g["y"] + g["height"] <= 816 and g["x"] + g["width"] <= 1536
    assert g["height"] < WANTED_SIZE[1]


def test_big_screen_keeps_wanted_size_centered():
    g = window_geometry((0, 0, 2560, 1400))
    assert (g["width"], g["height"]) == WANTED_SIZE
    assert g["x"] == (2560 - WANTED_SIZE[0]) // 2


def test_never_below_minimum_and_unknown_screen():
    g = window_geometry((0, 0, 800, 500))
    assert (g["width"], g["height"]) == MIN_SIZE
    assert window_geometry(None) == {"width": WANTED_SIZE[0], "height": WANTED_SIZE[1]}
