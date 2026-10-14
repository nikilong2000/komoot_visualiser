import math

import pytest

from komoot_visualiser.viewport import WORLD_SIZE_PX, fit_bounds

WIDTH, HEIGHT, PADDING = 900, 680, 40
EUROPE = (-5.18, 39.56, 16.35, 61.14)


def to_pixels(longitude, latitude, view):
    """Where a point lands on the map for a (longitude, latitude, zoom) view."""
    center_longitude, center_latitude, zoom = view
    scale = WORLD_SIZE_PX * 2**zoom / (2 * math.pi)

    def mercator_y(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    x = WIDTH / 2 + math.radians(longitude - center_longitude) * scale
    y = HEIGHT / 2 - (mercator_y(latitude) - mercator_y(center_latitude)) * scale
    return x, y


def box_in_pixels(bounds):
    west, south, east, north = bounds
    view = fit_bounds(bounds, WIDTH, HEIGHT, PADDING)
    (left, top), (right, bottom) = to_pixels(west, north, view), to_pixels(east, south, view)
    return left, top, right, bottom


@pytest.mark.parametrize("bounds", [EUROPE, (8.0, 47.0, 8.02, 47.1), (-120.0, -40.0, 150.0, 65.0)])
def test_whole_box_fits_inside_the_padding(bounds):
    left, top, right, bottom = box_in_pixels(bounds)

    assert PADDING - 1e-6 <= left < right <= WIDTH - PADDING + 1e-6
    assert PADDING - 1e-6 <= top < bottom <= HEIGHT - PADDING + 1e-6


def test_zooms_in_until_the_box_touches_the_padding():
    left, top, _, _ = box_in_pixels(EUROPE)

    assert math.isclose(top, PADDING) or math.isclose(left, PADDING)


def test_stops_at_max_zoom_for_tiny_boxes():
    assert fit_bounds((8.0, 47.0, 8.0, 47.0), WIDTH, HEIGHT, PADDING, max_zoom=12)[2] == 12
