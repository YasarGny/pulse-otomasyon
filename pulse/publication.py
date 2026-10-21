"""Fail-closed release contract shared by generation, validation and deployment."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
SECTIONS = ("teknoloji", "oyun")
MONTHS = (
    "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()
)
TECH_START = dt.date(2026, 10, 16)


def now():
    return dt.datetime.now(TZ)


def issue_number(date: str, section: str, game_start: str) -> int:
    if section not in SECTIONS:
        raise ValueError("Unknown section")
    start = TECH_START if section == "teknoloji" else dt.date.fromisoformat(game_start)
    number = (dt.date.fromisoformat(date) - start).days + 1
    if number < 1:
        raise ValueError("Publication predates first issue")
    return number


def turkish_date(date):
    d = dt.date.fromisoformat(date)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def expected_date(at: dt.datetime) -> str:
    at = at.astimezone(TZ)
    return (at.date() - dt.timedelta(days=at.hour < 6)).isoformat()


def not_before(date):
    return dt.datetime.combine(dt.date.fromisoformat(date), dt.time(7, 30), TZ)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def https_url(value):
    if not isinstance(value, str):
        return False
    p = urlparse(value)
    return (
        p.scheme == "https"
        and bool(p.hostname)
        and not p.username
        and not p.password
        and not any(c.isspace() for c in value)
    )


def category_allowed(section, category):
    words = set(re.findall(r"[a-zçğıöşü]+", str(category).casefold()))
    return not (section == "teknoloji" and words.intersection({"oyun", "gaming", "konsol"}))


def validate_content(data, section, date, game_start):
    if data.get("section") != section or data.get("publish_date") != date:
        raise ValueError("Edition identity/date mismatch")
    if type(data.get("issue")) is not int or data["issue"] != issue_number(
        date, section, game_start
    ):
        raise ValueError("Incorrect issue number")
    if data.get("date") != turkish_date(date):
        raise ValueError("Incorrect Turkish date")
    stories = data.get("stories")
    from pulse.profile import minimum_stories, expanded, shared_policy
    minimum = minimum_stories(data)
    if shared_policy(data):
        from pulse.profile import POLICY_START
        if date < POLICY_START:
            raise ValueError('Shared editorial policy is not active before ' + POLICY_START)
    if not isinstance(stories, list) or not minimum <= len(stories) <= 24:
        count = len(stories) if isinstance(stories, list) else 'invalid list'
        raise ValueError(f"{section}: edition has {count} stories; required {minimum}–24 distinct sourced stories")
    ids, urls, events = set(), set(), set()
    if data.get("content_revision", 1) >= 3:
        from pulse.source_media import trusted_hosts
        approved_hosts = trusted_hosts(section)
    else:
        approved_hosts = None
    for story in stories:
        if shared_policy(data):
            from pulse.news_priority import validate_priority
            validate_priority(story)
        if expanded(data):
            event = story.get('event_key')
            if not isinstance(event, str) or not 4 <= len(event) <= 120 or event.casefold() in events:
                raise ValueError('Missing or duplicate event identity')
            events.add(event.casefold())
            body = story.get('body')
            if not isinstance(body, list) or not 2 <= len(body) <= 6 or any(not isinstance(p, str) or not 30 <= len(p) <= 4000 for p in body):
                raise ValueError('Expanded stories require complete source-grounded articles')
            if story.get('body_reviewed') is not True or story.get('body_sha256') != hashlib.sha256(json.dumps(body, ensure_ascii=False).encode()).hexdigest():
                raise ValueError('Full article differs from reviewed text')
        if data.get("content_revision", 1) >= 2 and not category_allowed(section, story.get("category")):
            raise ValueError("Gaming story cannot appear in the technology edition")
        if "brief" in story and (
            not isinstance(story["brief"], str)
            or not 20 <= len(story["brief"].strip()) <= 500
        ):
            raise ValueError("Invalid factual audio brief")
        for field in ("id", "category", "title", "summary", "why", "source_name"):
            if (
                not isinstance(story.get(field), str)
                or not story[field].strip()
                or len(story[field]) > 4000
            ):
                raise ValueError("Missing/invalid story field: " + field)
        if story["id"] in ids or story.get("source_url") in urls:
            raise ValueError("Duplicate story/source")
        if not https_url(story.get("source_url")):
            raise ValueError("A verifiable HTTPS source is required")
        if approved_hosts is not None and urlparse(story["source_url"]).hostname not in approved_hosts:
            raise ValueError("Unapproved news publisher")
        if story.get("image_url") and not https_url(story["image_url"]):
            raise ValueError("Unsafe image URL")
        published = dt.datetime.fromisoformat(story["source_published_at"])
        if not published.tzinfo:
            raise ValueError("Source needs timezone")
        age = not_before(date) - published.astimezone(TZ)
        if not dt.timedelta(hours=-2) <= age <= dt.timedelta(hours=40):
            raise ValueError("Stale/future source")
        ids.add(story["id"])
        urls.add(story["source_url"])
    if shared_policy(data):
        from pulse.news_priority import rank_key
        if stories != sorted(stories, key=rank_key):
            raise ValueError('Stories must follow their reviewed editorial priority')
    return data


def safe_file(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Invalid local asset")
    path = Path(relative)
    if path.is_absolute() or any(p in (".", "..") for p in path.parts):
        raise ValueError("Asset must be release-relative")
    result = (Path(root) / path).resolve()
    if not result.is_relative_to(Path(root).resolve()) or not result.is_file():
        raise ValueError("Missing/escaping release asset")
    return result


def audio_info(path, minimum):
    path = Path(path)
    if path.stat().st_size < 25000:
        raise ValueError("Audio too small")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)["format"]
    seconds = float(info["duration"])
    if (
        "mp3" not in info.get("format_name", "").split(",")
        or not math.isfinite(seconds)
        or seconds < minimum
    ):
        raise ValueError("Invalid/short MP3")
    # Probe alone accepts truncated streams. Decode the entire file with errors fatal.
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    return {
        "duration": round(seconds, 1),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def validate_release(root, date, game_start):
    root = Path(root)
    entries = {}
    for section in SECTIONS:
        path = root / (section + ".json")
        data = validate_content(read_json(path), section, date, game_start)
        if data.get("ready") is not True:
            raise ValueError("Edition not ready")
        from pulse.profile import podcast_minimum, podcast_maximum
        for kind, minimum in [("summary", 20), ("podcast", podcast_minimum(data))]:
            asset = data.get(kind, {})
            if asset.get("file") != section + "/" + kind + ".mp3":
                raise ValueError("Unexpected audio path")
            actual = audio_info(safe_file(root, asset["file"]), minimum)
            if kind == "podcast" and podcast_maximum(data) is not None and actual["duration"] > podcast_maximum(data):
                raise ValueError("Podcast exceeds the expanded issue duration budget")
            if any(asset.get(k) != v for k, v in actual.items()):
                raise ValueError("Audio hash/size/duration mismatch")
            if asset.get("episode") != data["issue"] or not isinstance(
                asset.get("title"), str
            ):
                raise ValueError("Invalid episode metadata")
            if kind == "podcast" and (
                asset["title"]
                != ("Yeni Sekme" if section == "teknoloji" else "Moradon FM")
                or asset.get("hosts") != ["Yaşar", "Necdet"]
            ):
                raise ValueError("Invalid podcast identity")
        entries[section] = {
            "file": path.name,
            "sha256": digest(path),
            "issue": data["issue"],
        }
    return entries


def seal_release(root, date, game_start):
    entries = validate_release(root, date, game_start)
    fingerprint = hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode()
    ).hexdigest()[:16]
    manifest = {
        "schema_version": 1,
        "status": "ready",
        "publish_date": date,
        "release_id": date + "-" + fingerprint,
        "not_before": not_before(date).isoformat(),
        "validated_at": now().isoformat(),
        "game_start": game_start,
        "validation": "full-mp3-decode+sha256+content-v1",
        "editions": entries,
    }
    write_json(Path(root) / "release.json", manifest)
    return manifest


def verify_manifest(root, manifest):
    date = manifest["publish_date"]
    # Never accept an arbitrary status flag as a release attestation.
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "ready"
        or manifest.get("validation") != "full-mp3-decode+sha256+content-v1"
    ):
        raise ValueError("Unverified manifest")
    entries = validate_release(root, date, manifest["game_start"])
    fingerprint = hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode()
    ).hexdigest()[:16]
    if (
        entries != manifest["editions"]
        or manifest["release_id"] != date + "-" + fingerprint
        or manifest["not_before"] != not_before(date).isoformat()
    ):
        raise ValueError("Manifest does not match release")
    return manifest


def game_start_from_site(root, date):
    """Latch the game epoch only after its first successful publication."""
    root = Path(root)
    path = root / "data/publication.json"
    manifest = read_json(path) if path.exists() else {}
    start = manifest.get("game_start")
    if start:
        if dt.date.fromisoformat(start) > dt.date.fromisoformat(date):
            raise ValueError("Game launch is after the requested issue")
        return start
    if (root / "releases").exists() and any((root / "releases").glob("*/release.json")):
        raise ValueError("Published history exists but its numbering epoch is missing")
    return date
