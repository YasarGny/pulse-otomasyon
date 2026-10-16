"""Resumable, date-scoped generation. No Git writes, no Notion calls."""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from pulse.editorial import create_edition, research, summary_script
from pulse.publication import (
    SECTIONS,
    TZ,
    audio_info,
    issue_number,
    now,
    read_json,
    seal_release,
    validate_content,
    verify_manifest,
    write_json,
)


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
    # Same established Edge TTS narrator and pronunciation rules as pulse_audio.py.
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
    if not turns_path.exists():
        _, turns = pulse_podcast_writer.generate(
            [(s["title"], s["summary"] + " " + s["why"]) for s in data["stories"]],
            section=section,
            date=data["date"],
            issue=data["issue"],
        )
        write_json(turns_path, {"turns": turns})
    turns = pulse_podcast_writer._validate(read_json(turns_path))
    if turns[0]["speaker"] != "Yaşar":
        raise ValueError("The main host must open the episode")
    podcast = folder / "podcast.mp3"
    if not valid_audio(podcast, 40):
        temp = folder / "podcast.partial.mp3"
        pulse_podcast_audio.render(
            turns, temp
        )  # Existing Gemini Interactions API and custom voices.
        audio_info(temp, 40)
        temp.replace(podcast)
    data["podcast"] = {
        "file": f"{section}/podcast.mp3",
        "title": "Yeni Sekme" if section == "teknoloji" else "Moradon FM",
        "hosts": ["Yaşar", "Necdet"],
        "episode": data["issue"],
        **audio_info(podcast, 40),
    }
    data["ready"] = True
    return data


def valid_audio(path, minimum):
    if not path.exists():
        return False
    try:
        audio_info(path, minimum)
        return True
    except (ValueError, KeyError, subprocess.CalledProcessError):
        return False


def run(work, date, game_start, scheduled=False):
    work = Path(work)
    root = work / date
    root.mkdir(parents=True, exist_ok=True)
    settings = root / "settings.json"
    expected = {"publish_date": date, "game_start": game_start}
    if settings.exists() and read_json(settings) != expected:
        raise ValueError("Cannot renumber an existing daily workspace")
    write_json(settings, expected)
    if (root / "release.json").exists():
        return verify_manifest(root, read_json(root / "release.json"))
    if scheduled:
        wait_for(date, "06:15")
    sources = root / "research.json"
    if not sources.exists():
        research(date, sources)
    research_data = read_json(sources)
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
            )
            write_json(path, data)
    if scheduled:
        wait_for(date, "06:45")
    for section in SECTIONS:
        path = root / (section + ".json")
        data = read_json(path)
        # Checkpoint each successful section; failed runs resume without regenerating it.
        write_json(path, generate_audio(root, data))
    if scheduled:
        wait_for(date, "07:15")
    return seal_release(root, date, game_start)


def main():
    configure_transport()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default=".pulse-work")
    parser.add_argument("--date", default=now().date().isoformat())
    parser.add_argument(
        "--game-start", required=True, help="Immutable date of first game issue"
    )
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args()
    result = run(args.work, args.date, args.game_start, args.scheduled)
    print("Both editions validated:", result["release_id"])


if __name__ == "__main__":
    main()
