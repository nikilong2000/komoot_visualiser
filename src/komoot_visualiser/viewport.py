"""Initial map view that fits a bounding box (deck.gl's Web Mercator: the world is 512 px wide at zoom 0)."""

import math

WORLD_SIZE_PX = 512


def fit_bounds(
    bounds: tuple[float, float, float, float], width: int, height: int, padding: int = 40, max_zoom: float = 12
) -> tuple[float, float, float]:
    """(longitude, latitude, zoom) showing the (west, south, east, north) box inside a width x height map."""
    west, south, east, north = bounds
    x_span = math.radians(east - west)
    y_span = _mercator_y(north) - _mercator_y(south)
    zoom = max_zoom
    if x_span > 0:
        zoom = min(zoom, math.log2((width - 2 * padding) * 2 * math.pi / (WORLD_SIZE_PX * x_span)))
    if y_span > 0:
        zoom = min(zoom, math.log2((height - 2 * padding) * 2 * math.pi / (WORLD_SIZE_PX * y_span)))
    latitude = math.degrees(2 * math.atan(math.exp((_mercator_y(north) + _mercator_y(south)) / 2)) - math.pi / 2)
    return (west + east) / 2, latitude, max(zoom, 0)


def _mercator_y(latitude: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))
