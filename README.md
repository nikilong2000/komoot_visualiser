# Komoot Visualiser

All your recorded Komoot tours as coloured lines on one world map. A Streamlit app, managed with [uv](https://docs.astral.sh/uv/).

## Quick start

```sh
uv run komoot-sync            # download all recorded tours as GPX into data/gpx/komoot/
uv run streamlit run app.py   # open the map at http://localhost:8501
```

## Getting tours

- **Sync:** `uv run komoot-sync` uses the unofficial [komootgpx](https://github.com/timschneeb/KomootGPX) CLI.
  - It asks for your Komoot email and password and caches the login token in `~/Library/Caches/komootgpx`.
  - The first run downloads every recorded tour; later runs only re-download tours that changed.
  - It talks to Komoot's private API, so it can break without notice.
  - If you sign in to Komoot with Google or Apple, set a password in your Komoot account first.
  - Extra options are passed through, e.g. `uv run komoot-sync --mail you@example.com`.
- **Manual:** download the GPX of a tour on komoot.com (or from any other source) into any folder under `data/gpx/`, e.g. `data/gpx/manual/`.

Then reload the page. The app reads every `.gpx` file under `data/gpx/` and simplifies each track to about 5 m precision. Broken files and tours that appear twice are skipped and listed below the map.

## Development

```sh
uv run pytest
```

| File | What it does |
| --- | --- |
| `app.py` | The Streamlit page |
| `src/komoot_visualiser/tracks.py` | GPX files → simplified tour lines |
| `src/komoot_visualiser/colors.py` | A stable colour per tour |
| `src/komoot_visualiser/viewport.py` | Initial map view that fits all tours |
| `src/komoot_visualiser/sync.py` | The `komoot-sync` command |

Parsed tours are cached per file in `~/.streamlit/cache`, so after the first start only new or changed files are parsed.

## Privacy

GPX files are your location history, and the start and end points often reveal where you live.

- `data/` is git-ignored. Keep it that way.
- Don't deploy this app publicly without hiding those areas first.
- Streamlit's usage telemetry is switched off in `.streamlit/config.toml`.
