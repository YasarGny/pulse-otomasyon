"""Isolated synthetic publication server. Never part of a deployment artifact."""

import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import DATE, ready_release, tone

from pulse.build import build
from pulse.publication import not_before

root = Path("test-results")
root.mkdir(exist_ok=True)
audio = tone(root / "test-tone.mp3")
release = root / "fixture-release"
ready_release(release, audio)
build("site", root / "site", release=release, at=not_before(DATE))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root / "site"), **kwargs)

    def date_time_string(self, timestamp=None):
        return "Fri, 16 Oct 2026 05:30:00 GMT"

    def log_message(self, *args):
        pass


print("Fixture server ready", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
