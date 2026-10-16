"""Build only public files; a release is promoted as one immutable unit."""

import argparse
import datetime as dt
import os
import re
import shutil
from pathlib import Path

from pulse.pipeline import wait_for
from pulse.publication import (
    SECTIONS,
    not_before,
    now,
    read_json,
    verify_manifest,
    write_json,
)

PUBLIC_ROOTS = (
    "index.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    ".nojekyll",
    "assets",
    "teknoloji",
    "oyun",
)


def build(source, output, *, release=None, preparing=None, previous=None, at=None):
    source, output = Path(source), Path(output)
    at = at or now()
    if output.exists():
        if output.resolve() == source.resolve() or source.resolve().is_relative_to(
            output.resolve()
        ):
            raise ValueError("Output would overwrite source")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in PUBLIC_ROOTS:
        origin = source / name
        if origin.is_symlink() or any(p.is_symlink() for p in origin.rglob("*")):
            raise ValueError("Public source must not contain symlinks")
        if origin.is_dir():
            shutil.copytree(origin, output / name)
        else:
            shutil.copyfile(origin, output / name)
    if release:
        release = Path(release)
        manifest = verify_manifest(release, read_json(release / "release.json"))
        if at.astimezone(
            not_before(manifest["publish_date"]).tzinfo
        ).date().isoformat() != manifest["publish_date"] or at < not_before(
            manifest["publish_date"]
        ):
            raise ValueError("Release is stale or before 07:30 Istanbul")
        target = output / "releases" / manifest["release_id"]
        target.mkdir(parents=True)
        for section in SECTIONS:
            shutil.copyfile(release / (section + ".json"), target / (section + ".json"))
            (target / section).mkdir()
            for kind in ("summary", "podcast"):
                shutil.copyfile(
                    release / section / (kind + ".mp3"),
                    target / section / (kind + ".mp3"),
                )
        shutil.copyfile(release / "release.json", target / "release.json")
    else:
        if not preparing:
            raise ValueError("Choose a verified release or a preparation date")
        dt.date.fromisoformat(preparing)
        manifest = {
            "schema_version": 1,
            "status": "preparing",
            "publish_date": preparing,
            "editions": {},
        }
        if previous and (Path(previous) / "data/publication.json").exists():
            current = read_json(Path(previous) / "data/publication.json")
            if current.get("game_start"):
                manifest["game_start"] = current["game_start"]
            if (
                current.get("publish_date") == preparing
                and current.get("status") == "ready"
            ):
                # A delayed/retried 06:00 job must never close today's completed issue.
                folder = Path(previous) / "releases" / current["release_id"]
                verify_manifest(folder, current)
                manifest = current
                shutil.copytree(folder, output / "releases" / current["release_id"])
    write_json(output / "data/publication.json", manifest)
    assert_public_tree(output)
    return manifest


def assert_public_tree(root):
    root = Path(root)
    allowed = {
        ".html",
        ".css",
        ".js",
        ".json",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".mp3",
        ".ico",
        ".xml",
        ".txt",
    }
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink in site")
        if not path.is_file():
            continue
        if path.name != ".nojekyll" and path.suffix not in allowed:
            raise ValueError("Non-public file: " + str(path))
        if path.suffix in (".html", ".css", ".js", ".json", ".txt"):
            text = path.read_text(encoding="utf-8")
            # Prevent common credential formats and current secrets from entering artifacts.
            if re.search(
                r"AIza[\w-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{30,}",
                text,
            ):
                raise ValueError("Credential pattern found in public artifact")
            for name in (
                "GEMINI_API_KEY",
                "NOTION_TOKEN",
                "PULSE_DEPLOY_APP_PRIVATE_KEY",
                "GH_TOKEN",
                "GITHUB_TOKEN",
            ):
                value = os.environ.get(name)
                if value and len(value) > 12 and value in text:
                    raise ValueError("Secret value found in public artifact")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="site")
    p.add_argument("--output", default="dist")
    p.add_argument("--release")
    p.add_argument("--preparing")
    p.add_argument("--previous")
    p.add_argument("--wait", action="store_true")
    a = p.parse_args()
    if a.wait and a.release:
        wait_for(read_json(Path(a.release) / "release.json")["publish_date"], "07:30")
    m = build(
        a.source,
        a.output,
        release=a.release,
        preparing=a.preparing,
        previous=a.previous,
    )
    print("Public build:", m["status"], m["publish_date"])


if __name__ == "__main__":
    main()
