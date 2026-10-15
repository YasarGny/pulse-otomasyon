"""Yeni Sekme: Gemini multi-speaker audio with persistent presenter voices."""
import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
import requests
from pulse_podcast_writer import generate
from pulse_podcast_audio import render

NOTION_PAGE = "3f922115ab848156bb1fc0649973c0b5"
VOICES = {"Yaşar": "Puck", "Necdet": "Algenib"}
MODEL = os.getenv("PULSE_TTS_MODEL", "gemini-3.8-flash-tts")
OUT = Path("web-player")

def plain(block):
    return "".join(item.get("plain_text", "") for item in block.get(block.get("type"), {}).get("rich_text", []))

def read_news():
    headers = {"Authorization": "Bearer " + os.environ["NOTION_TOKEN"], "Notion-Version": "2022-06-28"}
    blocks, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        response = requests.get("https://api.notion.com/v1/blocks/" + NOTION_PAGE + "/children", headers=headers, params=params, timeout=60)
        response.raise_for_status()
        result = response.json()
        blocks.extend(result["results"])
        cursor = result.get("next_cursor")
        if not cursor:
            break
    started, stories = False, []
    for index, block in enumerate(blocks):
        kind, title = block["type"], plain(block)
        if kind == "heading_1":
            if "Bugünün haberleri" in title:
                started = True
            elif started:
                break
        if started and kind == "heading_3":
            summary = next((plain(b) for b in blocks[index + 1:index + 4] if b["type"] == "paragraph" and plain(b)), "")
            if summary:
                stories.append((title, summary))
    if len(stories) < 3:
        raise RuntimeError("Notion'da en az üç güncel haber bulunamadı.")
    return stories[:5]


def main():
    stories = read_news()
    dialogue, turns = generate(stories)
    OUT.mkdir(exist_ok=True)
    (OUT / "pilot-duo-gemini-script.json").write_text(
        json.dumps({"turns": turns, "voices": VOICES, "stories": [
            {"title": title, "summary": summary} for title, summary in stories
        ]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = OUT / "pilot-duo-gemini.mp3"
    metadata = render(turns, target)
    metadata["version"] = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    (OUT / "pilot-duo-gemini.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Yeni Sekme pilot:", metadata["duration"], "seconds,",
          metadata["segments"], "segments")

if __name__ == "__main__":
    main()
