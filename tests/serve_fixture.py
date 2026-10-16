"""Isolated synthetic publication server. Never part of a deployment artifact."""

import sys
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import DATE, ready_release, tone

from pulse.build import build
from pulse.archive import package
import zipfile
from pulse.publication import not_before, read_json, write_json, seal_release
import copy

root = Path("test-results")
root.mkdir(exist_ok=True)
audio = tone(root / "test-tone.mp3")
release = root / "fixture-release"
ready_release(release, audio)
build("site", root / "site", release=release, at=not_before(DATE))

package(root / "site", root / "offline.zip", fetch=lambda url: (Path("site/assets/covers/teknoloji-768.webp").read_bytes(), "image/webp"))
with zipfile.ZipFile(root / "offline.zip") as archive:
    archive.extractall(root / "offline")

large_release = root / 'large-release'
ready_release(large_release, audio)
for section in ('teknoloji', 'oyun'):
    data = read_json(large_release / (section + '.json'))
    original = copy.deepcopy(data['stories'])
    data['stories'] = [dict(original[i % 3], id=f'{section}{i}', source_url=f'https://example.com/{section}/{i}', category='BİLİM' if i % 2 else 'YAZILIM') for i in range(20)]
    write_json(large_release / (section + '.json'), data)
seal_release(large_release, DATE, DATE)
build('site', root / 'site' / 'expanded', release=large_release, at=not_before(DATE))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root / "site"), **kwargs)

    def date_time_string(self, timestamp=None):
        return "Fri, 16 Oct 2026 05:30:00 GMT"

    def do_GET(self):
        # Pages supports byte ranges; the fixture must model it for seek controls.
        requested = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
        path = Path(self.translate_path(self.path))
        if match and path.suffix == ".mp3" and path.is_file():
            size = path.stat().st_size
            start = int(match[1])
            end = min(int(match[2]) if match[2] else size - 1, size - 1)
            if start > end:
                self.send_error(416)
                return
            self.send_response(206)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with path.open("rb") as source:
                source.seek(start)
                self.wfile.write(source.read(end - start + 1))
            return
        super().do_GET()

    def log_message(self, *args):
        pass


print("Fixture server ready", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
