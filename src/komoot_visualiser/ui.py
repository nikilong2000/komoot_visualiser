"""Streamlit pieces of the app that tests can run on their own: the Komoot fetch form and the tour details."""

import streamlit as st

from komoot_visualiser import komoot, tracks
from komoot_visualiser.colors import hex_color_for_tour

#: Session key for the fetch summary that the app shows as a toast once the dialog has closed.
FETCH_NOTICE = "fetch_notice"

#: Komoot's sport ids. Unknown ones are shown with underscores as spaces.
SPORT_LABELS = {
    "hike": "Hiking",
    "jogging": "Running",
    "mountaineering": "Mountaineering",
    "climbing": "Climbing",
    "touringbicycle": "Bike touring",
    "e_touringbicycle": "E-bike touring",
    "citybike": "City cycling",
    "racebike": "Road cycling",
    "e_racebike": "E-road cycling",
    "mtb_easy": "Gravel riding",
    "e_mtb_easy": "E-gravel riding",
    "mtb": "Mountain biking",
    "e_mtb": "E-mountain biking",
    "mtb_advanced": "Enduro mountain biking",
    "e_mtb_advanced": "E-enduro mountain biking",
    "downhillbike": "Downhill biking",
    "skitour": "Ski touring",
    "nordic": "Cross-country skiing",
    "skaten": "Inline skating",
    "snowshoe": "Snowshoeing",
}


def plural(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def sport_label(sport: str | None) -> str | None:
    if not sport:
        return None
    return SPORT_LABELS.get(sport, sport.replace("_", " ").capitalize())


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    minutes = round(seconds / 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def format_speed(distance_km: float, seconds: float | None) -> str:
    return f"{distance_km / (seconds / 3600):.1f} km/h" if seconds else "–"


def take_login() -> None:
    """Submit callback: hands the login over to the next run only and blanks the password field right away.

    Streamlit keeps widget values in the session, so without this the password would stay in memory.
    """
    email = st.session_state["komoot_email"].strip()
    st.session_state["remembered_email"] = email
    st.session_state["pending_login"] = (email, st.session_state["komoot_password"])
    st.session_state["komoot_password"] = ""


def fetch_form() -> None:
    """Body of the "Fetch from Komoot" dialog: downloads the recorded tours of a Komoot account.

    On success it closes the dialog by rerunning the app, which also puts the new tours on the map.
    Errors and tours that failed stay in the dialog until it is closed.
    """
    with st.form("komoot"):
        st.text_input("Email", key="komoot_email", value=st.session_state.get("remembered_email", ""), autocomplete="email")
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

        summary = f"{plural(result.downloaded, 'tour')} downloaded, {result.unchanged:,} unchanged"
        if not result.failed:
            st.session_state[FETCH_NOTICE] = summary
            st.rerun()
        status.update(label=f"{summary}, {len(result.failed):,} failed", state="error")
        for failure in result.failed:
            st.warning(failure)


def tour_details(tour: tracks.Tour, sport: str | None) -> None:
    """Side panel for the route clicked on the map."""
    st.subheader(tour.name)
    when = f"{tour.start:%a %-d %b %Y, %H:%M}" if tour.start else None
    st.caption(" · ".join(part for part in (sport_label(sport), when) if part) or "No date in the GPX file")

    elevation = (
        f"↑ {tour.elevation_gain_m:,.0f} m  ↓ {tour.elevation_loss_m:,.0f} m"
        if tour.elevation_gain_m is not None and tour.elevation_loss_m is not None
        else "–"
    )
    facts = [
        ("Distance", f"{tour.distance_km:,.1f} km"),
        ("Duration", format_duration(tour.duration_s)),
        ("Average speed", format_speed(tour.distance_km, tour.duration_s)),
        ("Moving time", format_duration(tour.moving_s)),
        ("Moving speed", format_speed(tour.distance_km, tour.moving_s)),
        ("Elevation", elevation),
    ]
    columns = st.columns(2)
    for index, (label, value) in enumerate(facts):
        columns[index % 2].markdown(f":gray[{label}]  \n**{value}**")

    if tour.profile:
        st.area_chart(
            {"km": [km for km, _ in tour.profile], "m": [m for _, m in tour.profile]},
            x="km",
            y="m",
            x_label="km",
            y_label="m",
            color=hex_color_for_tour(tour.id),
            height=170,
        )
    if tour.id.isdigit():
        st.link_button(
            "Open on Komoot", f"https://www.komoot.com/tour/{tour.id}", icon=":material/open_in_new:", width="stretch"
        )
        if sport is None:
            st.caption("Fetch from Komoot once to show the sport.")
