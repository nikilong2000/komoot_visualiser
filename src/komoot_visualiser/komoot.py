"""Downloads recorded Komoot tours as GPX files.

Komoot has no public API. This makes the same requests as the komootgpx CLI 1.6.2
(https://github.com/timschneeb/KomootGPX), so it breaks whenever Komoot changes its private API.
The password is only sent to Komoot to log in; it is never stored.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import gpxpy.gpx
import requests

API_URL = "https://api.komoot.de"
#: Same query as komootgpx; the coordinates come back as items with lat, lng, alt and t.
TOUR_QUERY = (
    "_embedded=coordinates,way_types,surfaces,directions,participants,timeline&hl=en&directions=v2"
    "&fields=timeline&format=coordinate_array&timeline_highlights_fields=tips,recommenders"
)
TIMEOUT_SECONDS = 30


class KomootError(Exception):
    """Komoot couldn't be reached or refused a request. The message is meant for the user."""


@dataclass(frozen=True)
class Account:
    user_id: str
    token: str
    display_name: str


@dataclass
class SyncResult:
    display_name: str
    downloaded: int = 0
    unchanged: int = 0
    failed: list[str] = field(default_factory=list)


def sync_recorded_tours(
    email: str,
    password: str,
    output_dir: Path,
    *,
    session: requests.Session | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> SyncResult:
    """Saves every recorded tour as output_dir/{tour id}.gpx, skipping tours unchanged since the last sync.

    A saved file's modification time is set to the tour's last change on Komoot (like komootgpx does),
    so that is all it takes to tell whether a tour changed.
    """
    session = session or requests.Session()
    account = login(session, email, password)
    tours = recorded_tours(session, account)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = SyncResult(display_name=account.display_name)
    for done, tour in enumerate(tours):
        if on_progress:
            on_progress(done, len(tours))
        try:
            if _save_tour(session, account, tour, output_dir):
                result.downloaded += 1
            else:
                result.unchanged += 1
        except (KomootError, KeyError, TypeError, ValueError) as error:
            reason = error if isinstance(error, KomootError) else f"unexpected answer from Komoot ({error!r})"
            result.failed.append(f"{tour.get('name', tour.get('id'))}: {reason}")

    if on_progress:
        on_progress(len(tours), len(tours))
    return result


def login(session: requests.Session, email: str, password: str) -> Account:
    data = _get(session, f"{API_URL}/v006/account/email/{quote(email, safe='@')}/", (email, password))
    try:
        return Account(user_id=data["username"], token=data["password"], display_name=data["user"]["displayname"])
    except (KeyError, TypeError) as error:
        raise KomootError("Komoot's login answer looks different than expected.") from error


def recorded_tours(session: requests.Session, account: Account) -> list[dict]:
    """All recorded (not planned) tours of the account, following Komoot's pagination."""
    tours: list[dict] = []
    url: str | None = f"{API_URL}/v007/users/{account.user_id}/tours/"
    while url:
        page = _get(session, url, (account.user_id, account.token))
        tours += [tour for tour in page.get("_embedded", {}).get("tours", []) if tour.get("type") == "tour_recorded"]
        url = page.get("_links", {}).get("next", {}).get("href")
    return tours


def tour_gpx(session: requests.Session, account: Account, tour_id: str) -> str:
    tour = _get(session, f"{API_URL}/v007/tours/{tour_id}?{TOUR_QUERY}", (account.user_id, account.token))
    return build_gpx(tour)


def build_gpx(tour: dict) -> str:
    """GPX for a Komoot tour with embedded coordinates."""
    points = tour["_embedded"]["coordinates"]["items"]
    start = datetime.fromisoformat(tour["date"])
    # Like komootgpx: times starting at 0 are milliseconds since the tour start, otherwise Unix time in ms.
    relative = bool(points) and points[0].get("t") == 0

    segment = gpxpy.gpx.GPXTrackSegment()
    for point in points:
        time = None
        if "t" in point:
            time = start + timedelta(milliseconds=point["t"]) if relative else datetime.fromtimestamp(point["t"] / 1000, UTC)
        segment.points.append(gpxpy.gpx.GPXTrackPoint(point["lat"], point["lng"], elevation=point.get("alt"), time=time))

    gpx = gpxpy.gpx.GPX()
    gpx.name = tour["name"]
    gpx.link = f"https://www.komoot.com/tour/{tour['id']}"
    gpx.link_text = "View tour on Komoot"
    gpx.creator = "komoot-visualiser"
    track = gpxpy.gpx.GPXTrack(name=tour["name"])
    track.segments.append(segment)
    gpx.tracks.append(track)
    return gpx.to_xml()


def _save_tour(session: requests.Session, account: Account, tour: dict, output_dir: Path) -> bool:
    """Downloads one tour unless the saved copy is current. Returns whether it downloaded."""
    tour_id = str(tour["id"])
    if not tour_id.isdigit():  # it becomes a file name
        raise ValueError(f"tour id {tour_id!r}")
    path = output_dir / f"{tour_id}.gpx"
    changed_at = datetime.fromisoformat(tour["changed_at"]).timestamp()
    if path.exists() and abs(path.stat().st_mtime - changed_at) < 1:
        return False

    gpx = tour_gpx(session, account, tour_id)
    # Written next to the target and then renamed, so an interrupted sync never leaves half a GPX file.
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text(gpx, encoding="utf-8")
    os.utime(partial, (changed_at, changed_at))
    partial.replace(path)
    return True


def _get(session: requests.Session, url: str, auth: tuple[str, str]) -> dict:
    try:
        response = session.get(url, auth=auth, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise KomootError(f"Couldn't reach Komoot ({type(error).__name__}).") from error
    if response.status_code in (401, 403):
        raise KomootError("Komoot didn't accept the login. Check your email and password.")
    if response.status_code != 200:
        raise KomootError(f"Komoot answered with HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as error:
        raise KomootError("Komoot sent an answer that isn't JSON.") from error
