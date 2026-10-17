"""Verify the actual Pages response after a push, not just the Git commit."""

import argparse
import datetime as dt
import hashlib
import time
from pathlib import Path
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests

from pulse.publication import SECTIONS, expected_date, not_before, read_json

BASE = "https://yasargny.github.io/"


def check_site(session, base, expected):
    response = session.get(
        urljoin(base, "data/publication.json"),
        params={"pulse_check": time.time_ns()},
        timeout=30,
    )
    response.raise_for_status()
    if response.json() != expected:
        raise ValueError("Pages is still serving another manifest")
    routes = ("", "teknoloji/", "oyun/", "haberler/", "podcastler/")
    if expected["status"] == "ready":
        routes += ("teknoloji/dinle/", "oyun/dinle/")
    for route in routes:
        page = session.get(
            urljoin(base, route), params={"pulse_check": time.time_ns()}, timeout=30
        )
        page.raise_for_status()
        if (
            "assets/publication.js" not in page.text
            or 'data-design="editor-desk-v1"' not in page.text
        ):
            raise ValueError("Pages HTML has not updated")
        if (
            expected["status"] == "ready"
            and ('data-release="' + expected["release_id"] + '"') not in page.text
        ):
            raise ValueError("Pages HTML belongs to another release")
    if expected["status"] != "ready":
        return
    server = parsedate_to_datetime(response.headers["Date"]) + dt.timedelta(
        seconds=int(response.headers.get("Age", 0))
    )
    if expected_date(server) != expected["publish_date"] or server < not_before(
        expected["publish_date"]
    ):
        raise ValueError("Deployed issue does not match the server publication window")
    release = urljoin(base, "releases/" + expected["release_id"] + "/")
    for section in SECTIONS:
        entry = expected["editions"][section]
        result = session.get(urljoin(release, entry["file"]), timeout=30)
        result.raise_for_status()
        if hashlib.sha256(result.content).hexdigest() != entry["sha256"]:
            raise ValueError("Deployed edition hash mismatch")
        data = result.json()
        for kind in ("summary", "podcast"):
            asset = data[kind]
            with session.get(
                urljoin(release, asset["file"]), stream=True, timeout=60
            ) as audio:
                audio.raise_for_status()
                if not audio.headers.get("Content-Type", "").startswith("audio/"):
                    raise ValueError("Deployed MP3 content type invalid")
                checksum, size = hashlib.sha256(), 0
                for chunk in audio.iter_content(128 * 1024):
                    size += len(chunk)
                    if size > asset["bytes"]:
                        raise ValueError(
                            "Deployed MP3 is larger than the verified file"
                        )
                    checksum.update(chunk)
                if size != asset["bytes"] or checksum.hexdigest() != asset["sha256"]:
                    raise ValueError("Deployed MP3 hash/size mismatch")


def check_assets(session, base, tree):
    """A layout-only rollout keeps the release ID, so verify its assets separately."""
    tree = Path(tree)
    paths = [tree / "manifest.webmanifest", tree / "sw.js"]
    paths.extend(sorted((tree / "assets").rglob("*")))
    for path in paths:
        if not path.is_file():
            continue
        response = session.get(
            urljoin(base, path.relative_to(tree).as_posix()),
            params={"pulse_check": time.time_ns()},
            timeout=30,
        )
        response.raise_for_status()
        if (
            hashlib.sha256(response.content).digest()
            != hashlib.sha256(path.read_bytes()).digest()
        ):
            raise ValueError("Pages asset has not updated: " + path.name)
        if path.name == "sw.js" and "javascript" not in response.headers.get(
            "Content-Type", ""
        ):
            raise ValueError("Service worker MIME type invalid")


def wait_for_site(expected, timeout=900, tree=None):
    deadline = time.monotonic() + timeout
    with requests.Session() as session:
        while True:
            try:
                check_site(session, BASE, expected)
                if tree:
                    check_assets(session, BASE, tree)
                print(
                    "GitHub Pages verified:",
                    expected["status"],
                    expected.get("release_id", expected["publish_date"]),
                )
                return
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        "Pages did not serve the verified deployment before timeout: "
                        + type(exc).__name__
                    ) from None
                print("Waiting for the complete Pages deployment...", flush=True)
                time.sleep(min(15, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", default="dist/data/publication.json")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--tree", help="Verify deployed app and design assets against this public build"
    )
    args = parser.parse_args()
    wait_for_site(read_json(args.expected), args.timeout, args.tree)


if __name__ == "__main__":
    main()
