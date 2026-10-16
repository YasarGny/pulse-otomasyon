"""Restore today's last checkpoint from this workflow's trusted main-branch artifacts."""

import argparse
import io
import os
import re
import stat
import zipfile
from pathlib import Path

import requests


def unpack(raw, target, date):
    target = Path(target).resolve()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(m.file_size for m in members) > 500_000_000:
            raise ValueError("Oversized checkpoint")
        for member in members:
            path = Path(member.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != date
                or "\\" in member.filename
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise ValueError("Unsafe checkpoint path")
            cached_wav = re.fullmatch(re.escape(date) + r"/(?:(?:expanded-v\d+|audio-v\d+)/)?(?:teknoloji|oyun)/tts-parts/[a-f0-9]{64}/part_\d{3}\.wav", path.as_posix())
            if not member.is_dir() and path.suffix not in (".json", ".mp3", ".txt") and not cached_wav:
                raise ValueError("Unexpected checkpoint file")
        for member in members:
            dest = target / member.filename
            if not dest.resolve().is_relative_to(target):
                raise ValueError("Checkpoint escape")
            if member.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(member))


def restore(repo, date, target):
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    endpoint = "https://api.github.com/repos/" + repo + "/actions/artifacts"
    # Name filtering keeps a long-lived project's pagination bounded.
    response = session.get(endpoint, params={"per_page": 100}, timeout=40)
    response.raise_for_status()
    matches = [
        a
        for a in response.json()["artifacts"]
        if a["name"].startswith("pulse-state-" + date + "-")
        and not a["expired"]
        and a.get("workflow_run", {}).get("head_branch") == "main"
    ]
    if not matches:
        print("No checkpoint today; starting a fresh issue")
        return
    artifact = max(matches, key=lambda a: a["created_at"])
    run = session.get(
        "https://api.github.com/repos/"
        + repo
        + "/actions/runs/"
        + str(artifact["workflow_run"]["id"]),
        timeout=30,
    )
    run.raise_for_status()
    if run.json()["path"] != ".github/workflows/daily-publish.yml" or run.json()[
        "event"
    ] not in ("schedule", "workflow_dispatch"):
        raise ValueError("Checkpoint from untrusted workflow")
    archive = session.get(artifact["archive_download_url"], timeout=120)
    archive.raise_for_status()
    unpack(archive.content, target, date)
    print("Restored verified workflow checkpoint for", date)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--target", default=".pulse-work")
    a = p.parse_args()
    restore(a.repo, a.date, a.target)
