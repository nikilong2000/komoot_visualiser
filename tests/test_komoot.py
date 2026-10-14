from datetime import UTC, datetime, timedelta

import gpxpy
import pytest
import requests

from komoot_visualiser import komoot
from komoot_visualiser.tracks import parse_gpx

API = komoot.API_URL
LOGIN_URL = f"{API}/v006/account/email/me@example.com/"
TOURS_URL = f"{API}/v007/users/u1/tours/"
TOURS_PAGE_2_URL = f"{API}/v007/users/u1/tours/?page=1"
CHANGED_AT = "2024-05-12T12:00:00.000Z"


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload, self.status_code = payload, status_code

    def json(self):
        if self.payload is None:
            raise ValueError("no JSON")
        return self.payload


class FakeSession:
    """Answers like Komoot's API, by URL (detail requests are matched without their query string)."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def get(self, url, auth=None, timeout=None):
        self.requests.append((url, auth))
        response = self.routes.get(url) or self.routes.get(url.split("?")[0])
        if response is None:
            raise AssertionError(f"unexpected request: {url}")
        return response


def summary(tour_id, name, tour_type="tour_recorded", changed_at=CHANGED_AT, sport="touringbicycle"):
    return {"id": tour_id, "name": name, "type": tour_type, "changed_at": changed_at, "sport": sport}


def details(tour_id, name, items, **figures):
    return {
        "id": tour_id,
        "name": name,
        "date": "2024-05-12T07:30:00.000+02:00",
        "_embedded": {"coordinates": {"items": items}},
        **figures,
    }


RIDE_POINTS = [
    {"lat": 47.0, "lng": 8.0, "alt": 400.0, "t": 0},
    {"lat": 47.05, "lng": 8.02, "alt": 410.0, "t": 600_000},
    {"lat": 47.1, "lng": 8.0, "alt": 420.0, "t": 1_200_000},
]


def komoot_api(tours=None, **extra_routes):
    tours = tours or [
        summary(111, "Morning ride"),
        summary(222, "Planned trip", "tour_planned"),
        summary(333, "Evening hike", sport="hike"),
    ]
    return FakeSession({
        LOGIN_URL: FakeResponse({"username": "u1", "password": "token-1", "user": {"displayname": "Me"}}),
        TOURS_URL: FakeResponse({"_embedded": {"tours": tours[:2]}, "_links": {"next": {"href": TOURS_PAGE_2_URL}}}),
        TOURS_PAGE_2_URL: FakeResponse({"_embedded": {"tours": tours[2:]}, "_links": {}}),
        f"{API}/v007/tours/111": FakeResponse(details(111, "Morning ride", RIDE_POINTS)),
        f"{API}/v007/tours/333": FakeResponse(details(333, "Evening hike", RIDE_POINTS[:2])),
        **extra_routes,
    })


def test_saves_every_recorded_tour_as_gpx(tmp_path):
    session = komoot_api()

    result = komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=session)

    assert (result.display_name, result.downloaded, result.unchanged, result.failed) == ("Me", 2, 0, [])
    assert sorted(path.name for path in tmp_path.glob("*.gpx")) == ["111.gpx", "333.gpx"]
    assert session.requests[0] == (LOGIN_URL, ("me@example.com", "secret"))
    assert all(auth == ("u1", "token-1") for _, auth in session.requests[1:])

    tour = parse_gpx((tmp_path / "111.gpx").read_text(), "komoot/111.gpx")
    assert (tour.id, tour.name, tour.date) == ("111", "Morning ride", "2024-05-12")
    assert tour.lines == (((8.0, 47.0), (8.02, 47.05), (8.0, 47.1)),)


def test_remembers_the_sport_of_every_recorded_tour(tmp_path):
    komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=komoot_api())

    assert komoot.read_sports(tmp_path) == {"111": "touringbicycle", "333": "hike"}


def test_reading_sports_survives_a_missing_or_broken_file(tmp_path):
    assert komoot.read_sports(tmp_path) == {}
    (tmp_path / komoot.SPORTS_FILE).write_text("not json")
    assert komoot.read_sports(tmp_path) == {}


def test_gpx_carries_komoots_figures_and_the_sport():
    figures = {"distance": 11530.0, "duration": 4800, "elevation_up": 312.5, "elevation_down": 298.0, "sport": "hike"}

    tour = parse_gpx(komoot.build_gpx(details(1, "a", RIDE_POINTS, **figures)), "komoot/1.gpx")

    assert (tour.elevation_gain_m, tour.elevation_loss_m, tour.sport) == (312, 298, "hike")


def test_gpx_times_are_offsets_from_the_tour_start_or_unix_times_in_its_time_zone():
    relative = gpxpy.parse(komoot.build_gpx(details(1, "a", RIDE_POINTS)))
    absolute = gpxpy.parse(komoot.build_gpx(details(1, "a", [{"lat": 47, "lng": 8, "t": 1_715_500_000_000}])))

    assert relative.tracks[0].segments[0].points[1].time == datetime(2024, 5, 12, 5, 40, tzinfo=UTC)
    absolute_time = absolute.tracks[0].segments[0].points[0].time
    assert absolute_time == datetime(2024, 5, 12, 7, 46, 40, tzinfo=UTC)
    assert absolute_time.utcoffset() == timedelta(hours=2)  # reads 09:46 like on the day


def test_skips_tours_that_did_not_change_since_the_last_sync(tmp_path):
    komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=komoot_api())
    session = komoot_api()

    result = komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=session)

    assert (result.downloaded, result.unchanged) == (0, 2)
    assert not any("/v007/tours/" in url for url, _ in session.requests)


def test_downloads_tours_again_after_they_changed_on_komoot(tmp_path):
    komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=komoot_api())
    edited = [summary(111, "Morning ride", changed_at="2024-06-01T08:00:00.000Z"), summary(222, "Planned trip", "tour_planned"), summary(333, "Evening hike")]

    result = komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=komoot_api(edited))

    assert (result.downloaded, result.unchanged) == (1, 1)


def test_reports_progress(tmp_path):
    calls = []

    komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=komoot_api(), on_progress=lambda *args: calls.append(args))

    assert calls == [(0, 2), (1, 2), (2, 2)]


def test_a_failing_tour_does_not_stop_the_others(tmp_path):
    tours = [summary(111, "Morning ride"), summary(222, "Planned trip", "tour_planned"), summary(444, "Broken tour"), summary("../escape", "Odd id")]
    session = komoot_api(tours, **{f"{API}/v007/tours/444": FakeResponse(status_code=500)})

    result = komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=session)

    assert result.downloaded == 1
    assert result.failed == [
        "Broken tour: Komoot answered with HTTP 500.",
        "Odd id: unexpected answer from Komoot (ValueError(\"tour id '../escape'\"))",
    ]
    assert sorted(path.name for path in tmp_path.parent.iterdir() if path.suffix == ".gpx") == []
    assert [path.name for path in tmp_path.glob("*.gpx")] == ["111.gpx"]


def test_rejected_login_gives_a_readable_error(tmp_path):
    session = komoot_api(**{LOGIN_URL: FakeResponse({"error": "Unauthorized"}, status_code=401)})

    with pytest.raises(komoot.KomootError, match="didn't accept the login"):
        komoot.sync_recorded_tours("me@example.com", "wrong", tmp_path, session=session)
    assert list(tmp_path.iterdir()) == []


def test_email_is_escaped_in_the_login_url():
    session = FakeSession({f"{API}/v006/account/email/me%2Bkomoot@example.com/": FakeResponse({"username": "u1", "password": "t", "user": {"displayname": "Me"}})})

    assert komoot.login(session, "me+komoot@example.com", "secret").user_id == "u1"


def test_unreachable_komoot_gives_a_readable_error(tmp_path):
    class OfflineSession:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("no network")

    with pytest.raises(komoot.KomootError, match="Couldn't reach Komoot"):
        komoot.sync_recorded_tours("me@example.com", "secret", tmp_path, session=OfflineSession())
