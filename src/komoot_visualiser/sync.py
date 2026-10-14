"""`uv run komoot-sync`: downloads all recorded Komoot tours as GPX into data/gpx/komoot/.

Uses the unofficial komootgpx CLI (Komoot's private API, may break) in its own uvx environment.
It asks for your Komoot email and password and caches the login token in ~/Library/Caches/komootgpx.
Extra arguments are passed through, e.g. `uv run komoot-sync --mail you@example.com`.
"""

import subprocess
import sys

from komoot_visualiser.tracks import GPX_DIR

KOMOOTGPX = "komootgpx@1.6.2"
OUTPUT_DIR = GPX_DIR / "komoot"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        "uvx",
        KOMOOTGPX,
        "--make-all",
        "--tour-type=recorded",
        # Re-download only tours changed on Komoot; id-only file names stay stable when a tour is renamed.
        "--skip-unchanged",
        "--id-filename",
        "--no-poi",
        f"--output={OUTPUT_DIR}",
        *sys.argv[1:],
    ]
    sys.exit(subprocess.call(command))
