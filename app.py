"""Komoot Visualiser: every recorded Komoot tour as a coloured line on one world map.

Run with `uv run streamlit run app.py`.
"""

from pathlib import Path

import pydeck as pdk
import streamlit as st

from komoot_visualiser import tracks
from komoot_visualiser.colors import color_for_tour
from komoot_visualiser.viewport import fit_bounds

MAP_HEIGHT = 620
#: The map's real width depends on the browser window; fit the tours into at least this much.
MIN_MAP_WIDTH = 900
WORLD_VIEW = pdk.ViewState(latitude=30, longitude=10, zoom=1.5)
#: Changes whenever the parsing code is edited, so the disk cache never returns tours parsed by older code.
PARSER_VERSION = Path(tracks.__file__).stat().st_mtime_ns


@st.cache_data(persist="disk", show_spinner=False)
def read_tour(path: str, modified_ns: int, parser_version: int) -> tracks.Tour | None:
    """Parsing takes ~0.1 s per tour, so each file is parsed once and the result kept in ~/.streamlit/cache.

    The file's modification time is part of the cache key, so changed files are parsed again.
    """
    return tracks.read_tour(Path(path), tracks.GPX_DIR)


def tour_layer(tours: list[tracks.Tour]) -> pdk.Layer:
    rows = [{"path": line, "color": color_for_tour(tour.id)} for tour in tours for line in tour.lines]
    return pdk.Layer(
        "PathLayer",
        rows,
        get_path="path",
        get_color="color",
        # 60 m wide, but at least 1.5 px when zoomed out and at most 5 px at street level
        get_width=60,
        width_units="meters",
        width_min_pixels=1.5,
        width_max_pixels=5,
        cap_rounded=True,
        joint_rounded=True,
    )


def initial_view(tours: list[tracks.Tour]) -> pdk.ViewState:
    box = tracks.bounds(tours)
    if box is None:
        return WORLD_VIEW
    longitude, latitude, zoom = fit_bounds(box, width=MIN_MAP_WIDTH, height=MAP_HEIGHT)
    return pdk.ViewState(longitude=longitude, latitude=latitude, zoom=zoom)


st.set_page_config(page_title="Komoot Visualiser", page_icon=":material/route:", layout="wide")

files = tracks.find_gpx_files(tracks.GPX_DIR)
with st.spinner(f"Reading {len(files)} GPX files…"):
    results = [
        (file.relative_to(tracks.GPX_DIR).as_posix(), read_tour(str(file), file.stat().st_mtime_ns, PARSER_VERSION))
        for file in files
    ]
tours, warnings = tracks.collect(results)

st.subheader("Komoot Visualiser")
if tours:
    km = sum(tour.distance_km for tour in tours)
    st.caption(f"{len(tours):,} {'tour' if len(tours) == 1 else 'tours'} · {km:,.0f} km")
else:
    st.info("No tours yet. Run `uv run komoot-sync` or copy .gpx files into `data/gpx/`, then reload this page.")

st.pydeck_chart(
    pdk.Deck(
        layers=[tour_layer(tours)],
        initial_view_state=initial_view(tours),
        # repeat: keep drawing the tours when panning past the date line
        views=[pdk.View(type="MapView", controller=True, repeat=True)],
        map_provider="carto",
        map_style=pdk.map_styles.CARTO_LIGHT,
        tooltip=False,
    ),
    height=MAP_HEIGHT,
)

if warnings:
    with st.expander(f"{len(warnings)} GPX {'file' if len(warnings) == 1 else 'files'} skipped"):
        st.markdown("\n".join(f"- {warning}" for warning in warnings))
