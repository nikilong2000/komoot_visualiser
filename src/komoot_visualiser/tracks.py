"""Turns GPX files into simplified tour lines for the map."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import gpxpy
import gpxpy.gpx
import numpy as np
import shapely

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GPX_DIR = PROJECT_ROOT / "data" / "gpx"

#: Douglas-Peucker tolerance in degrees (~5 m). Raise it if the map gets slow with many tours.
SIMPLIFY_TOLERANCE = 0.00005
#: 5 decimals is ~1 m, plenty for drawing.
COORD_DECIMALS = 5
EARTH_RADIUS_KM = 6371.0088

_KOMOOT_TOUR_URL = re.compile(r"komoot\.[a-z]+/(?:[a-z-]+/)?tour/(\d+)", re.IGNORECASE)
#: komootgpx appends this to the name of recorded tours.
_COMPLETED_SUFFIX = " (Completed)"

type Line = tuple[tuple[float, float], ...]
"""(longitude, latitude) points."""


@dataclass(frozen=True)
class Tour:
    id: str
    """Komoot tour id when the GPX links to the tour, otherwise the GPX path without extension."""
    name: str
    date: str | None
    """Start date (YYYY-MM-DD) as written in the GPX, or None when it has no timestamps."""
    distance_km: float
    source: str
    """GPX file path relative to the GPX folder."""
    lines: tuple[Line, ...]
    """Simplified lines; more than one when the GPX has several segments or tracks."""
    raw_points: int
    """Point count before simplification."""


def parse_gpx(data: str | bytes, source: str) -> Tour | None:
    """Converts one GPX document into a tour. Returns None for invalid GPX or a file without track or route."""
    try:
        gpx = gpxpy.parse(data)
    except (gpxpy.gpx.GPXException, ValueError):
        return None

    point_lists = [segment.points for track in gpx.tracks for segment in track.segments]
    point_lists += [route.points for route in gpx.routes]
    point_lists = [points for points in point_lists if len(points) >= 2]
    if not point_lists:
        return None

    raw_lines = [np.array([(point.longitude, point.latitude) for point in points]) for points in point_lists]
    first_time = next((point.time for points in point_lists for point in points if point.time), None)
    stem = re.sub(r"\.gpx$", "", source, flags=re.IGNORECASE)
    return Tour(
        id=_komoot_tour_id(gpx) or stem,
        name=_name(gpx) or PurePosixPath(stem).name,
        date=first_time.date().isoformat() if first_time else None,
        distance_km=round(sum(_length_km(line) for line in raw_lines), 1),
        source=source,
        lines=tuple(_simplify(line) for line in raw_lines),
        raw_points=sum(len(line) for line in raw_lines),
    )


def find_gpx_files(gpx_dir: Path) -> list[Path]:
    """All .gpx files below gpx_dir, in any subfolder."""
    if not gpx_dir.is_dir():
        return []
    return sorted(path for path in gpx_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".gpx")


def read_tour(path: Path, gpx_dir: Path) -> Tour | None:
    return parse_gpx(path.read_bytes(), path.relative_to(gpx_dir).as_posix())


def collect(results: Iterable[tuple[str, Tour | None]]) -> tuple[list[Tour], list[str]]:
    """Drops unreadable files and repeated tours, oldest first so newer tours are drawn on top.

    Takes (source, tour) pairs and returns the tours plus one warning per skipped file.
    """
    tours: dict[str, Tour] = {}
    warnings: list[str] = []
    for source, tour in results:
        if tour is None:
            warnings.append(f"{source}: invalid GPX or no track")
        elif existing := tours.get(tour.id):
            warnings.append(f"{source}: same tour ({tour.id}) as {existing.source}")
        else:
            tours[tour.id] = tour
    return sorted(tours.values(), key=lambda tour: tour.date or ""), warnings


def load_tours(gpx_dir: Path = GPX_DIR) -> tuple[list[Tour], list[str]]:
    return collect((path.relative_to(gpx_dir).as_posix(), read_tour(path, gpx_dir)) for path in find_gpx_files(gpx_dir))


def bounds(tours: Iterable[Tour]) -> tuple[float, float, float, float] | None:
    """(west, south, east, north) around all tours, or None without tours."""
    points = np.array([point for tour in tours for line in tour.lines for point in line])
    if points.size == 0:
        return None
    (west, south), (east, north) = points.min(axis=0), points.max(axis=0)
    return float(west), float(south), float(east), float(north)


def _komoot_tour_id(gpx: gpxpy.gpx.GPX) -> str | None:
    links = [gpx.link, *(track.link for track in gpx.tracks), *(route.link for route in gpx.routes)]
    for link in links:
        if link and (match := _KOMOOT_TOUR_URL.search(link)):
            return match.group(1)
    return None


def _name(gpx: gpxpy.gpx.GPX) -> str | None:
    names = [*(track.name for track in gpx.tracks), *(route.name for route in gpx.routes), gpx.name]
    name = next((name.strip() for name in names if name and name.strip()), None)
    return name.removesuffix(_COMPLETED_SUFFIX).strip() if name else None


def _length_km(line: np.ndarray) -> float:
    """Haversine length of a (lon, lat) line."""
    lon, lat = np.radians(line[:, 0]), np.radians(line[:, 1])
    a = np.sin(np.diff(lat) / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(np.diff(lon) / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)).sum())


def _simplify(line: np.ndarray) -> Line:
    simplified = shapely.simplify(shapely.LineString(line), SIMPLIFY_TOLERANCE, preserve_topology=False)
    coords = simplified.coords if len(simplified.coords) >= 2 else line[[0, -1]]
    return tuple((round(float(lon), COORD_DECIMALS), round(float(lat), COORD_DECIMALS)) for lon, lat in coords)
