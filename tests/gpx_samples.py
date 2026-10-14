"""Synthetic GPX snippets for the tests (made-up coordinates, no personal data)."""


def gpx_file(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="test">{body}</gpx>'
    )


def trkpt(lat: float, lon: float, time: str | None = None) -> str:
    return f'<trkpt lat="{lat}" lon="{lon}"><ele>400</ele>{f"<time>{time}</time>" if time else ""}</trkpt>'


def track(*points: str, name: str | None = None) -> str:
    return f"<trk>{f'<name>{name}</name>' if name else ''}<trkseg>{''.join(points)}</trkseg></trk>"


KOMOOT_LINK = '<link href="https://www.komoot.de/tour/123456789"><text>View tour on Komoot</text></link>'

#: Shaped like a komootgpx export of a recorded tour.
KOMOOT_EXPORT = gpx_file(f"""
  <metadata><name>Lakeside loop (Completed)</name>{KOMOOT_LINK}</metadata>
  <trk>
    <name>Lakeside loop (Completed)</name>{KOMOOT_LINK}
    <trkseg>
      {trkpt(47.0000001, 8.0000001, "2024-05-12T07:30:00")}
      {trkpt(47.0500004, 8.0200004, "2024-05-12T08:10:00")}
      {trkpt(47.1000004, 8.0000004, "2024-05-12T08:50:00")}
    </trkseg>
  </trk>""")
