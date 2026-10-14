from gpx_samples import KOMOOT_EXPORT, gpx_file, track, trkpt

from komoot_visualiser.tracks import Tour, bounds, collect, find_gpx_files, load_tours, parse_gpx


def test_reads_a_komootgpx_export():
    tour = parse_gpx(KOMOOT_EXPORT, "komoot/123456789.gpx")

    assert tour == Tour(
        id="123456789",
        name="Lakeside loop",
        date="2024-05-12",
        distance_km=11.5,
        source="komoot/123456789.gpx",
        lines=(((8.0, 47.0), (8.02, 47.05), (8.0, 47.1)),),
        raw_points=3,
    )


def test_reads_raw_file_bytes():
    assert parse_gpx(KOMOOT_EXPORT.encode(), "komoot/123456789.gpx") == parse_gpx(KOMOOT_EXPORT, "komoot/123456789.gpx")


def test_finds_the_tour_id_in_localised_komoot_links():
    xml = gpx_file(f'<metadata><link href="https://www.komoot.com/de-de/tour/987654321"/></metadata>{track(trkpt(47, 8), trkpt(47.01, 8))}')

    assert parse_gpx(xml, "manual/whatever.gpx").id == "987654321"


def test_keeps_segments_and_tracks_as_separate_lines():
    xml = gpx_file(f"""
      <trk>
        <name>Two days</name>
        <trkseg>{trkpt(47, 8)}{trkpt(47.01, 8)}</trkseg>
        <trkseg>{trkpt(47.02, 8)}{trkpt(47.03, 8)}</trkseg>
      </trk>
      {track(trkpt(47.04, 8), trkpt(47.05, 8))}""")

    tour = parse_gpx(xml, "manual/two-days.gpx")

    assert len(tour.lines) == 3
    assert (tour.id, tour.name) == ("manual/two-days", "Two days")


def test_supports_routes_and_files_without_timestamps():
    xml = gpx_file("""
      <rte>
        <name>Planned route</name>
        <rtept lat="47" lon="8"/><rtept lat="47.01" lon="8.01"/><rtept lat="47.02" lon="8"/>
      </rte>""")

    tour = parse_gpx(xml, "manual/route.gpx")

    assert (tour.name, tour.date, len(tour.lines)) == ("Planned route", None, 1)


def test_falls_back_to_the_metadata_name_then_the_file_name():
    line = track(trkpt(47, 8), trkpt(47.01, 8))

    assert parse_gpx(gpx_file(f"<metadata><name>From metadata</name></metadata>{line}"), "a.gpx").name == "From metadata"
    assert parse_gpx(gpx_file(line), "manual/morning-ride.gpx").name == "morning-ride"


def test_simplifies_points_on_a_straight_line_away():
    points = [trkpt(47 + i * 0.0001, 8) for i in range(100)]

    tour = parse_gpx(gpx_file(track(*points)), "straight.gpx")

    assert tour.raw_points == 100
    assert tour.lines == (((8.0, 47.0), (8.0, 47.0099)),)


def test_returns_none_for_broken_xml_and_files_without_a_track():
    assert parse_gpx("<gpx><trk><trkseg>", "broken.gpx") is None
    assert parse_gpx("not xml at all", "garbage.gpx") is None
    assert parse_gpx(gpx_file('<wpt lat="47" lon="8"><name>Only a waypoint</name></wpt>'), "waypoint.gpx") is None
    assert parse_gpx(gpx_file(track(trkpt(47, 8))), "single-point.gpx") is None


def test_collect_skips_unreadable_files_and_repeated_tours_and_sorts_by_date():
    older = parse_gpx(gpx_file(track(trkpt(47, 8, "2020-01-01T10:00:00Z"), trkpt(47.01, 8))), "older.gpx")
    newer = parse_gpx(KOMOOT_EXPORT, "komoot/123456789.gpx")
    same_as_newer = parse_gpx(KOMOOT_EXPORT, "manual/lakeside.gpx")

    tours, warnings = collect([("komoot/123456789.gpx", newer), ("manual/lakeside.gpx", same_as_newer), ("broken.gpx", None), ("older.gpx", older)])

    assert tours == [older, newer]
    assert warnings == [
        "manual/lakeside.gpx: same tour (123456789) as komoot/123456789.gpx",
        "broken.gpx: invalid GPX or no track",
    ]


def test_finds_gpx_files_in_subfolders(tmp_path):
    (tmp_path / "komoot").mkdir()
    (tmp_path / "komoot" / "1.gpx").write_text(KOMOOT_EXPORT)
    (tmp_path / "Manual.GPX").write_text(KOMOOT_EXPORT)
    (tmp_path / "notes.txt").write_text("not a track")

    assert [path.relative_to(tmp_path).as_posix() for path in find_gpx_files(tmp_path)] == ["Manual.GPX", "komoot/1.gpx"]
    assert find_gpx_files(tmp_path / "missing") == []


def test_load_tours_reads_a_whole_folder(tmp_path):
    (tmp_path / "komoot").mkdir()
    (tmp_path / "komoot" / "123456789.gpx").write_text(KOMOOT_EXPORT)
    (tmp_path / "broken.gpx").write_text("<gpx><trk>")

    tours, warnings = load_tours(tmp_path)

    assert [tour.source for tour in tours] == ["komoot/123456789.gpx"]
    assert warnings == ["broken.gpx: invalid GPX or no track"]


def test_bounds_cover_all_tours():
    tour = parse_gpx(KOMOOT_EXPORT, "komoot/123456789.gpx")

    assert bounds([tour]) == (8.0, 47.0, 8.02, 47.1)
    assert bounds([]) is None
