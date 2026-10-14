"""Komoot Visualiser: every recorded Komoot tour as a coloured line on one world map.

Started by `uv run komoot-visualiser` (see cli.py).
"""

import math
from pathlib import Path

import pydeck as pdk
import streamlit as st

from komoot_visualiser import komoot, tracks
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


def plural(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def take_login() -> None:
    """Submit callback: hands the login over to this run only and blanks the password field right away.

    Streamlit keeps widget values in the session, so without this the password would stay in memory.
    """
    st.session_state["pending_login"] = (st.session_state["komoot_email"].strip(), st.session_state["komoot_password"])
    st.session_state["komoot_password"] = ""


def fetch_form() -> None:
    """Form that downloads the recorded tours of a Komoot account into data/gpx/komoot/."""
    st.subheader("Fetch from Komoot")
    with st.form("komoot"):
        st.text_input("Email", key="komoot_email", autocomplete="email")
        st.text_input("Password", key="komoot_password", type="password", autocomplete="current-password")
        st.form_submit_button("Fetch tours", type="primary", width="stretch", on_click=take_login)
    st.caption("Uses Komoot's unofficial API. Your password is only sent to Komoot and never stored.")
    login = st.session_state.pop("pending_login", None)
    if login is None:
        return

    email, password = login
    if not email or not password:
        st.error("Enter your Komoot email and password.")
        return

    with st.status("Logging in to Komoot…", expanded=True) as status:
        progress = st.progress(0.0)

        def on_progress(done: int, total: int) -> None:
            status.update(label=f"Fetching tours… {done} of {total}")
            progress.progress(done / total if total else 1.0)

        try:
            result = komoot.sync_recorded_tours(email, password, tracks.GPX_DIR / "komoot", on_progress=on_progress)
        except (komoot.KomootError, OSError) as error:
            status.update(label="Fetching failed", state="error")
            st.error(str(error))
            return

        status.update(
            label=f"{plural(result.downloaded, 'tour')} downloaded, {result.unchanged:,} unchanged",
            state="complete",
            expanded=bool(result.failed),
        )
        for failure in result.failed:
            st.warning(failure)


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

with st.sidebar:
    # Filled in once the tours are loaded, but shown above the form. Fetching comes first so that
    # tours it downloads are already on the map in this run.
    filter_box = st.container()
    fetch_form()

files = tracks.find_gpx_files(tracks.GPX_DIR)
with st.spinner(f"Reading {len(files)} GPX files…"):
    results = [
        (file.relative_to(tracks.GPX_DIR).as_posix(), read_tour(str(file), file.stat().st_mtime_ns, PARSER_VERSION))
        for file in files
    ]
tours, warnings = tracks.collect(results)

shown = tours
if tours:
    with filter_box:
        st.subheader("Filter")
        longest = max(1, math.ceil(max(tour.distance_km for tour in tours)))
        low, high = st.slider("Distance", min_value=0, max_value=longest, value=(0, longest), format="%d km")
        shown = [tour for tour in tours if low <= tour.distance_km <= high]

st.subheader("Komoot Visualiser")
if tours:
    count = plural(len(tours), "tour") if len(shown) == len(tours) else f"{len(shown):,} of {plural(len(tours), 'tour')}"
    st.caption(f"{count} · {sum(tour.distance_km for tour in shown):,.0f} km")
else:
    st.info("No tours yet. Fetch them from Komoot in the sidebar, or copy .gpx files into `data/gpx/`.")

st.pydeck_chart(
    pdk.Deck(
        layers=[tour_layer(shown)],
        # Fitted to all tours, not just the filtered ones, so filtering doesn't move the map.
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
    with st.expander(f"{plural(len(warnings), 'GPX file')} skipped"):
        st.markdown("\n".join(f"- {warning}" for warning in warnings))
