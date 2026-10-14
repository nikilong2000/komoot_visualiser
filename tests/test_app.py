import json
from pathlib import Path

import pytest
import streamlit as st
from gpx_samples import KOMOOT_EXPORT, gpx_file, track, trkpt
from streamlit.testing.v1 import AppTest

from komoot_visualiser import komoot, tracks
from komoot_visualiser.colors import color_for_tour

APP = Path(komoot.__file__).with_name("app.py")
SHORT_WALK = gpx_file(track(trkpt(46.0, 7.0, "2023-01-01T10:00:00Z"), trkpt(46.01, 7.0), name="Short walk"))


@pytest.fixture
def run_app(monkeypatch, tmp_path):
    # The app persists its cache in ~/.streamlit/cache; keep the tests' cache away from the real one.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def run(gpx_dir: Path) -> AppTest:
        monkeypatch.setattr(tracks, "GPX_DIR", gpx_dir)
        st.cache_data.clear()
        return AppTest.from_file(str(APP), default_timeout=30).run()

    return run


@pytest.fixture
def fake_sync(monkeypatch):
    """Replaces the Komoot download with one that 'downloads' KOMOOT_EXPORT."""
    calls = []

    def sync(email, password, output_dir, *, on_progress=None):
        calls.append((email, password, output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "123456789.gpx").write_text(KOMOOT_EXPORT)
        on_progress(1, 1)
        return komoot.SyncResult(display_name="Me", downloaded=1)

    monkeypatch.setattr(komoot, "sync_recorded_tours", sync)
    return calls


def deck_of(app: AppTest) -> dict:
    return json.loads(app.get("deck_gl_json_chart")[0].proto.json)


def log_in(app: AppTest, email: str, password: str) -> AppTest:
    app.sidebar.text_input[0].input(email)
    app.sidebar.text_input[1].input(password)
    return app.sidebar.button[0].click().run()


def test_draws_each_tour_as_a_coloured_line(tmp_path, run_app):
    (tmp_path / "komoot").mkdir()
    (tmp_path / "komoot" / "123456789.gpx").write_text(KOMOOT_EXPORT)

    app = run_app(tmp_path)

    assert not app.exception
    assert app.main.caption[0].value == "1 tour · 12 km"
    layer = deck_of(app)["layers"][0]
    assert layer["@@type"] == "PathLayer"
    assert layer["data"] == [{"path": [[8.0, 47.0], [8.02, 47.05], [8.0, 47.1]], "color": list(color_for_tour("123456789"))}]


def test_explains_how_to_add_tours_when_there_are_none(tmp_path, run_app):
    app = run_app(tmp_path / "missing")

    assert not app.exception
    assert "Fetch them from Komoot in the sidebar" in app.main.info[0].value
    assert not app.sidebar.slider


def test_lists_skipped_files(tmp_path, run_app):
    (tmp_path / "broken.gpx").write_text("<gpx><trk>")

    app = run_app(tmp_path)

    assert app.expander[0].label == "1 GPX file skipped"


def test_distance_slider_filters_tours_without_moving_the_map(tmp_path, run_app):
    (tmp_path / "lakeside.gpx").write_text(KOMOOT_EXPORT)  # 11.5 km
    (tmp_path / "short.gpx").write_text(SHORT_WALK)  # 1.1 km
    app = run_app(tmp_path)
    view = deck_of(app)["initialViewState"]

    assert app.sidebar.slider[0].value == (0, 12)
    app = app.sidebar.slider[0].set_value((0, 5)).run()

    assert app.main.caption[0].value == "1 of 2 tours · 1 km"
    deck = deck_of(app)
    assert [row["path"] for row in deck["layers"][0]["data"]] == [[[7.0, 46.0], [7.0, 46.01]]]
    assert deck["initialViewState"] == view


def test_fetch_button_downloads_tours_onto_the_map(tmp_path, run_app, fake_sync):
    app = log_in(run_app(tmp_path), " me@example.com ", "secret")

    assert not app.exception
    assert fake_sync == [("me@example.com", "secret", tmp_path / "komoot")]
    assert app.sidebar.status[0].label == "1 tour downloaded, 0 unchanged"
    assert app.main.caption[0].value == "1 tour · 12 km"


def test_form_forgets_the_password_but_keeps_the_email(tmp_path, run_app, fake_sync):
    app = log_in(run_app(tmp_path), "me@example.com", "secret")

    assert app.sidebar.text_input[0].value == "me@example.com"
    assert app.sidebar.text_input[1].value == ""
    assert app.session_state["komoot_password"] == ""
    assert "pending_login" not in app.session_state


def test_shows_why_fetching_failed(tmp_path, run_app, monkeypatch):
    def reject(*args, **kwargs):
        raise komoot.KomootError("Komoot didn't accept the login. Check your email and password.")

    monkeypatch.setattr(komoot, "sync_recorded_tours", reject)
    app = log_in(run_app(tmp_path), "me@example.com", "wrong")

    assert not app.exception
    assert app.sidebar.status[0].label == "Fetching failed"
    assert app.sidebar.error[0].value == "Komoot didn't accept the login. Check your email and password."


def test_fetching_needs_email_and_password(tmp_path, run_app, fake_sync):
    app = log_in(run_app(tmp_path), "me@example.com", "")

    assert fake_sync == []
    assert app.sidebar.error[0].value == "Enter your Komoot email and password."
