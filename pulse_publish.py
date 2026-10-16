"""Publish PULSE daily brief and Yeni Sekme from the same verified Notion issue."""
import datetime as dt
import json
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pulse_audio
import pulse_podcast_audio
import pulse_podcast_writer

OUT = Path("web-player")
TZ = ZoneInfo("Europe/Istanbul")


def issue_stories():
    blocks = pulse_audio.children(pulse_audio.PAGE)
    today = dt.datetime.now(TZ)
    expected = f"{today.day} {pulse_audio.MONTHS[today.month - 1]} {today.year}"
    header = " ".join(pulse_audio.rich(b) + " " + (
        " ".join(pulse_audio.rich(c) for c in pulse_audio.children(b["id"]))
        if b.get("has_children") and b["type"] == "callout" else ""
    ) for b in blocks[:5])
    if pulse_audio.normalized(expected) not in pulse_audio.normalized(header) and today.strftime("%d.%m.%Y") not in header:
        raise RuntimeError("Notion issue is not dated today")
    in_news, stories = False, []
    for i, block in enumerate(blocks):
        typ, title = block["type"], pulse_audio.rich(block)
        if typ == "heading_1":
            if "Bugünün haberleri" in title:
                in_news = True
            elif in_news:
                break
        if in_news and typ == "heading_3":
            summary = next((pulse_audio.rich(b) for b in blocks[i+1:i+4]
                            if b["type"] == "paragraph" and pulse_audio.rich(b)), "")
            if summary:
                stories.append((title, summary))
    if len(stories) < 3:
        raise RuntimeError("Insufficient current stories in Notion")
    return today, stories


def main():
    # Wait for the 07:00 Notion editorial task; never publish yesterday's content.
    deadline = time.monotonic() + 12 * 60
    while True:
        try:
            today, stories = issue_stories()
            break
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("Today's verified Notion issue not ready") from exc
            print("Waiting for today's Notion issue:", exc, flush=True)
            time.sleep(40)

    # Stage both audio assets before any publication commit.
    pulse_audio.main()  # Edge TTS only for narration, Gemini for its script.
    _, turns = pulse_podcast_writer.generate(stories)
    OUT.mkdir(exist_ok=True)
    info = pulse_podcast_audio.render(turns, OUT / "podcast-latest.mp3")
    if info["duration"] < 40 or (OUT / "podcast-latest.mp3").stat().st_size < 25000:
        raise RuntimeError("Podcast failed validation")
    number = (today.date() - dt.date(2026, 10, 16)).days + 1
    if number < 1:
        raise RuntimeError("Issue numbering not started")
    import hashlib
    version = hashlib.sha256((OUT / "podcast-latest.mp3").read_bytes()).hexdigest()[:16]
    metadata = {"date": f"{today.day} {pulse_audio.MONTHS[today.month-1]} {today.year}",
                "issue": number, "episode": number, "audio": "podcast-latest.mp3",
                "version": version, "title": "Yeni Sekme",
                "hosts": ["Yaşar", "Necdet"], "duration": info["duration"]}
    (OUT / "podcast-latest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Ready to publish both audio tracks:", json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
