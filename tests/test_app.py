import json
from pathlib import Path

import pytest
import streamlit as st
from gpx_samples import KOMOOT_EXPORT
from streamlit.testing.v1 import AppTest

from komoot_visualiser import tracks
from komoot_visualiser.colors import color_for_tour

APP = Path(__file__).parents[1] / "app.py"


@pytest.fixture
def run_app(monkeypatch, tmp_path):
    # The app persists its cache in ~/.streamlit/cache; keep the tests' cache away from the real one.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def run(gpx_dir: Path) -> AppTest:
        monkeypatch.setattr(tracks, "GPX_DIR", gpx_dir)
        st.cache_data.clear()
        return AppTest.from_file(str(APP), default_timeout=30).run()

    return run


def test_draws_each_tour_as_a_coloured_line(tmp_path, run_app):
    (tmp_path / "komoot").mkdir()
    (tmp_path / "komoot" / "123456789.gpx").write_text(KOMOOT_EXPORT)

    app = run_app(tmp_path)

    assert not app.exception
    assert app.caption[0].value == "1 tour · 12 km"
    deck = json.loads(app.get("deck_gl_json_chart")[0].proto.json)
    assert deck["layers"][0]["@@type"] == "PathLayer"
    assert deck["layers"][0]["data"] == [
        {"path": [[8.0, 47.0], [8.02, 47.05], [8.0, 47.1]], "color": list(color_for_tour("123456789"))}
    ]


def test_explains_how_to_add_tours_when_there_are_none(tmp_path, run_app):
    app = run_app(tmp_path / "missing")

    assert not app.exception
    assert "uv run komoot-sync" in app.info[0].value


def test_lists_skipped_files(tmp_path, run_app):
    (tmp_path / "broken.gpx").write_text("<gpx><trk>")

    app = run_app(tmp_path)

    assert app.expander[0].label == "1 GPX file skipped"
