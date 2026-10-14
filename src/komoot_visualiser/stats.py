"""Statistics from GPS points: step lengths, moving time, elevation change and an elevation profile."""

import re

import numpy as np

EARTH_RADIUS_KM = 6371.0088
#: Slower than this counts as standing still when adding up the moving time.
MOVING_MIN_SPEED_KMH = 1.0
#: A longer gap between two points means the recording was paused, which never counts as moving.
MOVING_MAX_STEP_SECONDS = 600
PROFILE_POINTS = 200

#: Komoot's figures in a GPX description, as written by komootgpx and by komoot.build_gpx.
_KOMOOT_ELEVATION = re.compile(r"Elevation up: ([\d.]+)m, Elevation down: ([\d.]+)m")


def step_lengths_km(lonlat: np.ndarray) -> np.ndarray:
    """Haversine length of each step between consecutive (lon, lat) points."""
    lon, lat = np.radians(lonlat[:, 0]), np.radians(lonlat[:, 1])
    a = np.sin(np.diff(lat) / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(np.diff(lon) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def moving_seconds(steps_km: np.ndarray, seconds: np.ndarray, min_speed_kmh: float = MOVING_MIN_SPEED_KMH) -> float:
    """Time spent on steps faster than min_speed_kmh; seconds are the point timestamps."""
    step_seconds = np.diff(seconds)
    moving = (step_seconds > 0) & (step_seconds <= MOVING_MAX_STEP_SECONDS)
    moving[moving] = steps_km[moving] / (step_seconds[moving] / 3600) >= min_speed_kmh
    return float(step_seconds[moving].sum())


def elevation_change(elevations: np.ndarray) -> tuple[float, float]:
    """Total ascent and descent in metres."""
    steps = np.diff(elevations)
    return float(steps[steps > 0].sum()), float(-steps[steps < 0].sum())


def profile(distance_km: np.ndarray, elevations: np.ndarray, points: int = PROFILE_POINTS) -> tuple[tuple[float, float], ...]:
    """At most `points` (km, m) pairs, spread evenly over the distance; distance_km is cumulative."""
    if len(distance_km) > points:
        picked = np.searchsorted(distance_km, np.linspace(0, distance_km[-1], points))
        distance_km, elevations = distance_km[picked], elevations[picked]
    return tuple((round(float(km), 2), round(float(m))) for km, m in zip(distance_km, elevations))


def komoot_elevation(description: str | None) -> tuple[float, float] | None:
    """Komoot's own ascent and descent (metres) from a GPX description, if it has them."""
    match = _KOMOOT_ELEVATION.search(description or "")
    return (float(match.group(1)), float(match.group(2))) if match else None
