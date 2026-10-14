from datetime import datetime, timedelta, timezone

import pytest
from streamlit.testing.v1 import AppTest

from komoot_visualiser import komoot, tracks
from komoot_visualiser.tracks import Tour
from komoot_visualiser.ui import FETCH_NOTICE, format_duration, format_speed, sport_label

HIKE = Tour(
    id="123456789",
    name="Lakeside loop",
    date="2024-05-12",
    distance_km=11.5,
    source="komoot/123456789.gpx",
    lines=(((8.0, 47.0), (8.0, 47.1)),),
    raw_points=2,
    start=datetime(2024, 5, 12, 7, 30, tzinfo=timezone(timedelta(hours=2))),
    duration_s=4800,
    moving_s=3600,
    elevation_gain_m=312,
    elevation_loss_m=298,
    profile=((0.0, 400), (5.7, 712), (11.5, 414)),
)


def fetch_form_page():
    from komoot_visualiser.ui import fetch_form

    fetch_form()


def details_page():
    import streamlit as st

    from komoot_visualiser.ui import tour_details

    tour_details(st.session_state["tour"], st.session_state["sport"])


def show_details(tour: Tour, sport: str | None) -> AppTest:
    app = AppTest.from_function(details_page)
    app.session_state["tour"] = tour
    app.session_state["sport"] = sport
    return app.run()


@pytest.fixture
def fetch_form(monkeypatch, tmp_path):
    monkeypatch.setattr(tracks, "GPX_DIR", tmp_path)
    return AppTest.from_function(fetch_form_page).run()


def submit(app: AppTest, email: str, password: str) -> AppTest:
    app.text_input[0].input(email)
    app.text_input[1].input(password)
    return app.button[0].click().run()


def test_successful_fetch_leaves_a_notice_and_reruns(fetch_form, monkeypatch, tmp_path):
    calls = []

    def sync(email, password, output_dir, *, on_progress=None):
        calls.append((email, password, output_dir))
        on_progress(1, 1)
        return komoot.SyncResult(display_name="Me", downloaded=1, unchanged=4)

    monkeypatch.setattr(komoot, "sync_recorded_tours", sync)
    app = submit(fetch_form, " me@example.com ", "secret")

    assert not app.exception
    assert calls == [("me@example.com", "secret", tmp_path / "komoot")]
    assert app.session_state[FETCH_NOTICE] == "1 tour downloaded, 4 unchanged"


def test_form_forgets_the_password_but_keeps_the_email(fetch_form, monkeypatch):
    monkeypatch.setattr(komoot, "sync_recorded_tours", lambda *args, **kwargs: komoot.SyncResult(display_name="Me"))

    app = submit(fetch_form, "me@example.com", "secret")

    assert app.text_input[0].value == "me@example.com"
    assert app.text_input[1].value == ""
    assert app.session_state["komoot_password"] == ""
    assert "pending_login" not in app.session_state


def test_failed_login_stays_in_the_dialog(fetch_form, monkeypatch):
    def reject(*args, **kwargs):
        raise komoot.KomootError("Komoot didn't accept the login. Check your email and password.")

    monkeypatch.setattr(komoot, "sync_recorded_tours", reject)
    app = submit(fetch_form, "me@example.com", "wrong")

    assert not app.exception
    assert app.status[0].label == "Fetching failed"
    assert app.error[0].value == "Komoot didn't accept the login. Check your email and password."
    assert FETCH_NOTICE not in app.session_state


def test_tours_that_failed_stay_in_the_dialog(fetch_form, monkeypatch):
    result = komoot.SyncResult(display_name="Me", downloaded=2, failed=["Broken tour: Komoot answered with HTTP 500."])
    monkeypatch.setattr(komoot, "sync_recorded_tours", lambda *args, **kwargs: result)

    app = submit(fetch_form, "me@example.com", "secret")

    assert app.status[0].label == "2 tours downloaded, 0 unchanged, 1 failed"
    assert app.warning[0].value == "Broken tour: Komoot answered with HTTP 500."
    assert FETCH_NOTICE not in app.session_state


def test_fetching_needs_email_and_password(fetch_form, monkeypatch):
    monkeypatch.setattr(komoot, "sync_recorded_tours", lambda *args, **kwargs: pytest.fail("should not fetch"))

    app = submit(fetch_form, "me@example.com", "")

    assert app.error[0].value == "Enter your Komoot email and password."


def test_details_show_the_chosen_facts():
    app = show_details(HIKE, "hike")

    assert not app.exception
    assert app.subheader[0].value == "Lakeside loop"
    assert app.caption[0].value == "Hiking · Sun 12 May 2024, 07:30"
    left, right = ([markdown.value for markdown in column.markdown] for column in app.columns)
    assert left == [
        ":gray[Distance]  \n**11.5 km**",
        ":gray[Average speed]  \n**8.6 km/h**",
        ":gray[Moving speed]  \n**11.5 km/h**",
    ]
    assert right == [
        ":gray[Duration]  \n**1 h 20 min**",
        ":gray[Moving time]  \n**1 h 00 min**",
        ":gray[Elevation]  \n**↑ 312 m  ↓ 298 m**",
    ]
    assert len(app.get("vega_lite_chart")) == 1
    assert app.get("link_button")[0].proto.url == "https://www.komoot.com/tour/123456789"


def test_details_ask_for_a_fetch_when_the_sport_is_unknown():
    app = show_details(HIKE, None)

    assert app.caption[0].value == "Sun 12 May 2024, 07:30"
    assert app.caption[-1].value == "Fetch from Komoot once to show the sport."


def test_details_of_a_manual_gpx_without_times_or_elevation():
    tour = Tour(id="manual/route", name="route", date=None, distance_km=1.4, source="manual/route.gpx", lines=(), raw_points=2)

    app = show_details(tour, None)

    assert app.caption[0].value == "No date in the GPX file"
    assert ":gray[Duration]  \n**–**" in [markdown.value for markdown in app.markdown]
    assert not app.get("vega_lite_chart")
    assert not app.get("link_button")


def test_formats():
    assert (format_duration(4800), format_duration(59 * 60), format_duration(None)) == ("1 h 20 min", "59 min", "–")
    assert (format_speed(10, 3600), format_speed(10, None)) == ("10.0 km/h", "–")
    assert (sport_label("touringbicycle"), sport_label("e_scooter"), sport_label(None)) == ("Bike touring", "E scooter", None)
