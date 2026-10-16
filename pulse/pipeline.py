"""Resumable, date-scoped generation. No Git writes, no Notion calls."""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from pulse.editorial import create_edition, research, summary_script
from pulse.history import exclude_published, restore_published
from pulse.publication import (
    SECTIONS,
    TZ,
    audio_info,
    category_allowed,
    issue_number,
    now,
    read_json,
    seal_release,
    validate_content,
    verify_manifest,
    write_json,
)

AUDIO_REVISION = 4


def configure_transport():
    """Use platform/system roots without disabling TLS or replacing the voice engine."""
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE"):
        import truststore

        truststore.inject_into_ssl()


def tts_proxy():
    # aiohttp's WSS lookup does not inherit HTTPS_PROXY automatically.
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


def wait_for(date, clock):
    target = dt.datetime.fromisoformat(date + "T" + clock).replace(tzinfo=TZ)
    while (delay := (target - now()).total_seconds()) > 0:
        time.sleep(min(delay, 30))
    if now().date().isoformat() != date:
        raise RuntimeError(
            "Publication date expired; refusing to publish yesterday as today"
        )


def pronunciation(text):
    # Established Edge TTS narrator and pronunciation rules, retained after migration.
    for word, spoken in {
        "PULSE": "Pals",
        "AI": "yapay zeka",
        "DeepMind": "Diip Maynd",
        "AlphaFold": "Alfa Fold",
        "Google": "Gugıl",
        "Cloud": "Klaud",
    }.items():
        text = re.sub(r"\b" + re.escape(word) + r"\b", spoken, text, flags=re.I)
    return text


def generate_audio(root, data):
    import edge_tts

    import pulse_podcast_audio
    import pulse_podcast_writer

    from pulse.profile import expanded, podcast_minimum, PODCAST_SECONDS
    minimum_podcast = podcast_minimum(data)
    section = data["section"]
    folder = root / section
    folder.mkdir(exist_ok=True)
    identity = hashlib.sha256(
        json.dumps(
            {
                "section": section,
                "date": data["publish_date"],
                "issue": data["issue"],
                "stories": data["stories"],
                "audio_revision": AUDIO_REVISION,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    checkpoint = folder / "input.json"
    if checkpoint.exists() and read_json(checkpoint) != {"sha256": identity}:
        raise ValueError("Cached audio belongs to different editorial input")
    write_json(checkpoint, {"sha256": identity})
    script = summary_script(data)
    (folder / "summary.txt").write_text(script, encoding="utf-8")
    summary = folder / "summary.mp3"
    if not valid_audio(summary, 20):
        temp = folder / "summary.partial.mp3"
        asyncio.run(
            edge_tts.Communicate(
                text=pronunciation(script),
                voice="tr-TR-EmelNeural",
                rate="+0%",
                proxy=tts_proxy(),
            ).save(str(temp))
        )
        audio_info(temp, 20)
        temp.replace(summary)
    data["summary"] = {
        "file": f"{section}/summary.mp3",
        "title": "Günün sesli özeti",
        "episode": data["issue"],
        **audio_info(summary, 20),
    }
    turns_path = folder / "turns.json"
    review_path = folder / "podcast-review.json"
    if not turns_path.exists() or not review_path.exists():
        evidence = []
        research_path = root / "research.json"
        if not research_path.exists():
            research_path = root.parent / "research.json"
        raw = {}
        if research_path.exists():
            raw = {s["id"]: s for s in read_json(research_path)["sections"][section]}
        for story in data["stories"]:
            evidence.append({
                "source_url": story["source_url"],
                "headline": story["title"],
                "excerpt": raw.get(story["id"], {}).get("source_full_text") or raw.get(story["id"], {}).get("source_excerpt", story["summary"]),
            })
        _, turns = pulse_podcast_writer.generate(
            [(s["title"], s["summary"]) for s in data["stories"]],
            section=section,
            date=data["date"],
            issue=data["issue"],
            evidence=evidence,
            audit_path=review_path,
            **({"long_form": True} if expanded(data) else {}),
        )
        write_json(turns_path, {"turns": turns})
    review = read_json(review_path)
    if not pulse_podcast_writer._approved(review.get("review", {})):
        raise ValueError("Podcast requires an approved evidence/conversation review")
    turns = pulse_podcast_writer._validate(read_json(turns_path))
    if review.get("turns_sha256") != pulse_podcast_writer.dialogue_digest(turns):
        raise ValueError("Podcast dialogue differs from its approved review")
    if turns[0]["speaker"] != "Yaşar":
        raise ValueError("The main host must open the episode")
    podcast = folder / "podcast.mp3"
    if not valid_audio(podcast, minimum_podcast):
        temp = folder / "podcast.partial.mp3"
        pulse_podcast_audio.render(
            turns, temp, strict_audio=True,
            **({"checkpoint_dir": folder / "tts-parts"} if expanded(data) else {})
        )  # Existing Gemini Interactions API and custom voices.
        audio_info(temp, minimum_podcast)
        temp.replace(podcast)
    data["podcast"] = {
        "file": f"{section}/podcast.mp3",
        "title": "Yeni Sekme" if section == "teknoloji" else "Moradon FM",
        "hosts": ["Yaşar", "Necdet"],
        "episode": data["issue"],
        **audio_info(podcast, minimum_podcast),
    }
    if expanded(data) and data["podcast"]["duration"] > PODCAST_SECONDS[section][1]:
        raise ValueError("Podcast exceeds expanded duration budget")
    data["ready"] = True
    data["audio_revision"] = AUDIO_REVISION
    return data


def valid_audio(path, minimum):
    if not path.exists():
        return False
    try:
        audio_info(path, minimum)
        return True
    except (ValueError, KeyError, subprocess.CalledProcessError):
        return False


def refresh_audio_release(work, date, game_start, previous):
    """Revise today's audio as a new immutable release, keeping date/news/issue."""
    if previous is None or now().date().isoformat() != date:
        raise ValueError("Audio refresh requires today's published issue")
    previous = Path(previous)
    manifest = read_json(previous / "data/publication.json")
    if manifest.get("status") != "ready" or manifest.get("publish_date") != date or manifest.get("game_start") != game_start:
        raise ValueError("Only a complete current-day publication can be revised")
    source = previous / "releases" / manifest["release_id"]
    verify_manifest(source, manifest)
    root = Path(work) / date / ("audio-v" + str(AUDIO_REVISION))
    root.mkdir(parents=True, exist_ok=True)
    def finish(result):
        # A later ordinary rerun must not roll back to a pre-revision checkpoint.
        names = ["release.json"]
        for section in SECTIONS:
            names.append(section + ".json")
            names.extend(section + "/" + name for name in (
                "summary.mp3", "podcast.mp3", "input.json", "turns.json", "podcast-review.json", "summary.txt"
            ))
        for name in names:
            origin, destination = root / name, root.parent / name
            if origin.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, destination)
        return result
    if (root / "release.json").exists():
        return finish(verify_manifest(root, read_json(root / "release.json")))
    editions = {section: read_json(source / (section + ".json")) for section in SECTIONS}
    if all(data.get("audio_revision") == AUDIO_REVISION for data in editions.values()):
        restore_published(root, previous, date, game_start)
        return finish(verify_manifest(root, read_json(root / "release.json")))
    for section, data in editions.items():
        data["stories"] = [s for s in data["stories"] if category_allowed(section, s["category"])]
        data["content_revision"] = 2
        validate_content(data, section, date, game_start)
        path = root / (section + ".json")
        if not path.exists():
            data = {k: v for k, v in data.items() if k not in ("summary", "podcast")}
            data["ready"] = False
            write_json(path, data)
        write_json(path, generate_audio(root, read_json(path)))
    return finish(seal_release(root, date, game_start))


def run(work, date, game_start, scheduled=False, previous=None, refresh_audio=False, expanded_issue=False):
    if refresh_audio:
        return refresh_audio_release(work, date, game_start, previous)
    work = Path(work)
    regular = work / date
    root = regular / "expanded-v1" if expanded_issue else regular
    root.mkdir(parents=True, exist_ok=True)
    settings = root / "settings.json"
    expected = {"publish_date": date, "game_start": game_start}
    if settings.exists() and read_json(settings) != expected:
        raise ValueError("Cannot renumber an existing daily workspace")
    write_json(settings, expected)
    if (root / "release.json").exists():
        return verify_manifest(root, read_json(root / "release.json"))
    if not expanded_issue and restore_published(root, previous, date, game_start):
        return verify_manifest(root, read_json(root / "release.json"))
    if scheduled:
        wait_for(date, "06:15")
    sources = root / "research.json"
    if not sources.exists():
        research(date, sources)
    research_data = exclude_published(read_json(sources), previous, date)
    if scheduled:
        wait_for(date, "06:30")
    for section in SECTIONS:
        path = root / (section + ".json")
        if path.exists():
            validate_content(read_json(path), section, date, game_start)
        else:
            data = create_edition(
                research_data,
                section,
                date,
                issue_number(date, section, game_start),
                game_start,
                article_cache=root / section / "articles",
            )
            write_json(path, data)
            write_json(sources, research_data)
    if scheduled:
        wait_for(date, "06:45")
    for section in SECTIONS:
        path = root / (section + ".json")
        data = read_json(path)
        # Checkpoint each successful section; failed runs resume without regenerating it.
        write_json(path, generate_audio(root, data))
    if scheduled:
        wait_for(date, "07:15")
    manifest = seal_release(root, date, game_start)
    if expanded_issue:
        for name in ('release.json', 'teknoloji.json', 'oyun.json', 'research.json'):
            if (root / name).exists():
                shutil.copyfile(root / name, regular / name)
        for section in SECTIONS:
            (regular / section).mkdir(exist_ok=True)
            for name in ('summary.mp3', 'podcast.mp3', 'input.json', 'turns.json', 'podcast-review.json', 'summary.txt'):
                if (root / section / name).exists():
                    shutil.copyfile(root / section / name, regular / section / name)
    return manifest


def main():
    configure_transport()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default=".pulse-work")
    parser.add_argument("--date", default=now().date().isoformat())
    parser.add_argument(
        "--game-start", required=True, help="Immutable date of first game issue"
    )
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--expanded", action="store_true", help="Produce a full current-day revision without restoring the short legacy issue")
    parser.add_argument("--refresh-audio", action="store_true", help="Revise only today's audio, preserving news and issue numbers")
    parser.add_argument(
        "--previous",
        help="Published site checkout for deduplication and durable recovery",
    )
    args = parser.parse_args()
    result = run(args.work, args.date, args.game_start, args.scheduled, args.previous, args.refresh_audio, args.expanded)
    print("Both editions validated:", result["release_id"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Safe check annotations remain readable even if hosted log storage is down.
        # Never include provider URLs, headers, response bodies or credential values.
        message = re.sub(r"(?:https?|wss?)://\S+", "[service URL]", str(exc))
        for name in ("GEMINI_API_KEY", "PULSE_DEPLOY_APP_PRIVATE_KEY", "GITHUB_TOKEN"):
            secret = os.environ.get(name)
            if secret:
                message = message.replace(secret, "[redacted]")
        message = message[:300].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::error title=PULSE production check::" + type(exc).__name__ + ": " + message, flush=True)
        raise
