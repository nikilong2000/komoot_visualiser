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


def deck_of(app: AppTest) -> dict:
    return json.loads(app.get("deck_gl_json_chart")[0].proto.json)


def test_draws_each_tour_as_a_coloured_line(tmp_path, run_app):
    (tmp_path / "komoot").mkdir()
    (tmp_path / "komoot" / "123456789.gpx").write_text(KOMOOT_EXPORT)

    app = run_app(tmp_path)

    assert not app.exception
    assert app.main.caption[0].value == "1 tour · 12 km"
    layer = deck_of(app)["layers"][0]
    assert layer["@@type"] == "PathLayer"
    assert layer["data"] == [{"path": [[8.0, 47.0], [8.02, 47.05], [8.0, 47.1]], "color": list(color_for_tour("123456789"))}]


def test_routes_are_clicked_through_a_wider_invisible_copy(tmp_path, run_app):
    (tmp_path / "123456789.gpx").write_text(KOMOOT_EXPORT)

    layers = {layer["id"]: layer for layer in deck_of(run_app(tmp_path))["layers"]}

    assert list(layers) == ["tours", "click-targets"]
    assert layers["tours"]["widthUnits"] == "meters"  # a plain string, not a pydeck expression ("@@=...")
    click_targets = layers["click-targets"]
    assert (click_targets["pickable"], click_targets["opacity"], click_targets["widthUnits"]) == (True, 0, "pixels")
    assert [row["tour"] for row in click_targets["data"]] == ["123456789"]


def test_sidebar_has_the_fetch_button_and_explains_clicking(tmp_path, run_app):
    (tmp_path / "123456789.gpx").write_text(KOMOOT_EXPORT)

    app = run_app(tmp_path)

    assert app.sidebar.button[0].label == "Fetch from Komoot"
    assert app.sidebar.caption[0].value == "Click a route on the map to see its details."


def test_explains_how_to_add_tours_when_there_are_none(tmp_path, run_app):
    app = run_app(tmp_path / "missing")

    assert not app.exception
    assert "Fetch them from Komoot with the button in the sidebar" in app.main.info[0].value
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
