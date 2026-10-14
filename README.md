# Komoot Visualiser

All your recorded Komoot tours as coloured lines on one world map. A Streamlit app, managed with [uv](https://docs.astral.sh/uv/).

## Start

```sh
uv run komoot-visualiser
```

This opens the map in your browser at <http://localhost:8501>. Stop it with `Ctrl+C`. Extra arguments go to `streamlit run`, e.g. `uv run komoot-visualiser --server.port 8600`.

## Using the map

- **Filter:** the distance slider in the sidebar has two handles, for the shortest and longest tour to show.
- **Fetch from Komoot:** enter your Komoot email and password in the sidebar and click **Fetch tours**.
  - All recorded tours are saved as GPX files in `data/gpx/komoot/`. Later fetches only download tours that changed on Komoot since.
  - The password is only sent to Komoot and never stored. The password field is blanked after every attempt.
  - This uses Komoot's private API (the same requests as the [komootgpx](https://github.com/timschneeb/KomootGPX) CLI), so it can break without notice.
  - If you sign in to Komoot with Google or Apple, set a password in your Komoot account first.
- **Manual GPX files:** put them into any folder under `data/gpx/`, e.g. `data/gpx/manual/`, then reload the page.

The app reads every `.gpx` file under `data/gpx/` and simplifies each track to about 5 m precision. Broken files and tours that appear twice are skipped and listed below the map.

## Development

```sh
uv run pytest
```

| File | What it does |
| --- | --- |
| `src/komoot_visualiser/app.py` | The Streamlit page |
| `src/komoot_visualiser/cli.py` | The `komoot-visualiser` command |
| `src/komoot_visualiser/komoot.py` | Downloads tours from Komoot as GPX |
| `src/komoot_visualiser/tracks.py` | GPX files → simplified tour lines |
| `src/komoot_visualiser/colors.py` | A stable colour per tour |
| `src/komoot_visualiser/viewport.py` | Initial map view that fits all tours |

Parsed tours are cached per file in `~/.streamlit/cache`, so after the first start only new or changed files are parsed. The command turns Streamlit's reload-on-save off; add `--server.fileWatcherType=auto` while working on the code.

## Privacy

GPX files are your location history, and the start and end points often reveal where you live.

- The app only accepts connections from this computer, not from your network.
- `data/` is git-ignored. Keep it that way.
- Don't deploy this app publicly without hiding those areas first.
- Streamlit's usage telemetry is switched off.
