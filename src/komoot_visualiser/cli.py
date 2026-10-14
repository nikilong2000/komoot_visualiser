"""`uv run komoot-visualiser`: starts the app and opens it in the browser."""

import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli

APP = Path(__file__).with_name("app.py")

STREAMLIT_OPTIONS = [
    # Only reachable from this computer: the app shows your location history and takes your Komoot password.
    "--server.address=localhost",
    "--server.showEmailPrompt=false",
    "--browser.gatherUsageStats=false",
    # Reloading on source changes is only useful while developing (pass --server.fileWatcherType=auto then).
    "--server.fileWatcherType=none",
]


def main() -> None:
    """Extra arguments go to `streamlit run`, e.g. `uv run komoot-visualiser --server.port 8600`."""
    streamlit_cli.main(["run", str(APP), *STREAMLIT_OPTIONS, *sys.argv[1:]], prog_name="streamlit")
