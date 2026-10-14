"""Komoot Visualiser: every recorded Komoot tour as a coloured line on one world map.

Started by `uv run komoot-visualiser` (see cli.py).
"""

import math
from pathlib import Path

import pydeck as pdk
import streamlit as st

from komoot_visualiser import komoot, tracks
from komoot_visualiser.colors import color_for_tour
from komoot_visualiser.ui import FETCH_NOTICE, fetch_form, plural, tour_details
from komoot_visualiser.viewport import fit_bounds

SIDEBAR_WIDTH = 400
#: The map's size depends on the browser window; the first view fits the tours into at least this much.
FIT_WIDTH, FIT_HEIGHT = 800, 600
WORLD_VIEW = pdk.ViewState(latitude=30, longitude=10, zoom=1.5)
#: Routes are drawn thin when zoomed out, so clicks go to an invisible copy this many pixels wide.
#: (deck.gl's own pickingRadius would do this, but Streamlit doesn't pass it on.)
CLICK_WIDTH = 14
#: Changes whenever the parsing code is edited, so the disk cache never returns tours parsed by older code.
PARSER_VERSION = Path(tracks.__file__).stat().st_mtime_ns

# Streamlit can only give elements a fixed height in pixels. This lets the map's container (key "map_area")
# take all the height left below the title, so the map always reaches the bottom of the window.
# It also centres dialogs vertically ("safe" keeps a dialog taller than the window scrollable).
LAYOUT_CSS = """
<style>
[data-testid="stMainBlockContainer"] { height: 100dvh; padding-bottom: 1rem; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stLayoutWrapper"]:has(> .st-key-map_area) { flex: 1 1 0; min-height: 400px; }
.st-key-map_area { height: 100%; }
[data-testid="stDialog"] { align-items: safe center; }
</style>
"""

fetch_dialog = st.dialog("Fetch from Komoot", on_dismiss="rerun")(fetch_form)


@st.cache_data(persist="disk", show_spinner=False)
def read_tour(path: str, modified_ns: int, parser_version: int) -> tracks.Tour | None:
    """Parsing takes ~0.1 s per tour, so each file is parsed once and the result kept in ~/.streamlit/cache.

    The file's modification time is part of the cache key, so changed files are parsed again.
    """
    return tracks.read_tour(Path(path), tracks.GPX_DIR)


def path_rows(tours: list[tracks.Tour]) -> list[dict]:
    return [{"path": line, "color": color_for_tour(tour.id)} for tour in tours for line in tour.lines]


def tour_layers(tours: list[tracks.Tour], selected: tracks.Tour | None) -> list[pdk.Layer]:
    """All tours, the selected one drawn wider with a dark outline, and on top the invisible click targets."""
    # pydeck turns plain strings into per-object expressions ("color" reads each row's color);
    # only quoted strings reach deck.gl as text.
    meters, pixels = "'meters'", "'pixels'"
    line_style = {"get_path": "path", "cap_rounded": True, "joint_rounded": True}
    layers = [
        pdk.Layer(
            "PathLayer",
            path_rows(tours),
            id="tours",
            get_color="color",
            # 60 m wide, but at least 3 px when zoomed out and at most 5 px at street level
            get_width=60,
            width_units=meters,
            width_min_pixels=3,
            width_max_pixels=5,
            **line_style,
        )
    ]
    if selected:
        rows = path_rows([selected])
        layers += [
            pdk.Layer("PathLayer", rows, id="selected-outline", get_color=[20, 20, 20, 200], get_width=9, width_units=pixels, **line_style),
            pdk.Layer("PathLayer", rows, id="selected", get_color="color", get_width=5, width_units=pixels, **line_style),
        ]
    layers.append(
        pdk.Layer(
            "PathLayer",
            [{"tour": tour.id, "path": line} for tour in tours for line in tour.lines],
            id="click-targets",
            get_width=CLICK_WIDTH,
            width_units=pixels,
            pickable=True,
            # Invisible but still clickable. A transparent colour doesn't work: Streamlit recolours
            # the objects of clickable layers once something is selected.
            opacity=0,
            **line_style,
        )
    )
    return layers


def selected_tour_id(map_state) -> str | None:
    """Id of the route last clicked on the map, from the chart's selection state."""
    picked = (map_state or {}).get("selection", {}).get("objects", {}).get("click-targets", [])
    return picked[0].get("tour") if picked else None


def initial_view(tours: list[tracks.Tour]) -> pdk.ViewState:
    box = tracks.bounds(tours)
    if box is None:
        return WORLD_VIEW
    longitude, latitude, zoom = fit_bounds(box, width=FIT_WIDTH, height=FIT_HEIGHT)
    return pdk.ViewState(longitude=longitude, latitude=latitude, zoom=zoom)


st.set_page_config(
    page_title="Komoot Visualiser", page_icon=":material/route:", layout="wide", initial_sidebar_state=SIDEBAR_WIDTH
)
st.html(LAYOUT_CSS)
if notice := st.session_state.pop(FETCH_NOTICE, None):
    st.toast(notice, icon=":material/check_circle:")

files = tracks.find_gpx_files(tracks.GPX_DIR)
with st.spinner(f"Reading {len(files)} GPX files…"):
    results = [
        (file.relative_to(tracks.GPX_DIR).as_posix(), read_tour(str(file), file.stat().st_mtime_ns, PARSER_VERSION))
        for file in files
    ]
tours, warnings = tracks.collect(results)

with st.sidebar:
    open_fetch_dialog = st.button("Fetch from Komoot", icon=":material/download:", width="stretch")
    shown = tours
    if tours:
        st.subheader("Filter")
        longest = max(1, math.ceil(max(tour.distance_km for tour in tours)))
        low, high = st.slider("Distance", min_value=0, max_value=longest, value=(0, longest), format="%d km")
        shown = [tour for tour in tours if low <= tour.distance_km <= high]

    # A route hidden by the filter counts as not selected.
    selected = next((tour for tour in shown if tour.id == selected_tour_id(st.session_state.get("map"))), None)
    st.divider()
    if selected:
        tour_details(selected, komoot.read_sports(tracks.GPX_DIR / "komoot").get(selected.id) or selected.sport)
    elif tours:
        st.caption("Click a route on the map to see its details.")

if open_fetch_dialog:
    fetch_dialog()

st.subheader("Komoot Visualiser")
if tours:
    count = plural(len(tours), "tour") if len(shown) == len(tours) else f"{len(shown):,} of {plural(len(tours), 'tour')}"
    st.caption(f"{count} · {sum(tour.distance_km for tour in shown):,.0f} km")
else:
    st.info("No tours yet. Fetch them from Komoot with the button in the sidebar, or copy .gpx files into `data/gpx/`.")

deck = pdk.Deck(
    layers=tour_layers(shown, selected),
    # Fitted to all tours, not just the filtered ones, so filtering and clicking don't move the map.
    initial_view_state=initial_view(tours),
    # repeat: keep drawing the tours when panning past the date line
    views=[pdk.View(type="MapView", controller=True, repeat=True)],
    map_provider="carto",
    map_style=pdk.map_styles.CARTO_LIGHT,
    tooltip=False,
)
with st.container(key="map_area"):
    st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="map", height="stretch")

if warnings:
    with st.expander(f"{plural(len(warnings), 'GPX file')} skipped"):
        st.markdown("\n".join(f"- {warning}" for warning in warnings))
