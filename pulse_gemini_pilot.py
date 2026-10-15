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
    dialogue, turns = generate(read_news())
    OUT.mkdir(exist_ok=True)
    (OUT / 'pilot-duo-gemini-script.json').write_text(json.dumps({'turns': turns, 'voices': VOICES}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Gemini 3.8 requires each utterance as a separate part with speaker metadata.
    speech_parts = []
    for turn in turns:
        speaker = turn["speaker"]
        speech_parts.append({
            "text": turn["text"],
            "speechMetadata": {
                "speaker": speaker,
                "style": (
                    "Natural Turkish podcast host, relaxed conversational pacing, "
                    "slightly slower than everyday speech, varied intonation, "
                    "audible sentence-final pauses, never rush or sound like a newsreader."
                    if speaker == "Yaşar" else
                    "Natural Turkish podcast co-host, steady lower-register voice, "
                    "slightly slower than everyday speech, thoughtful phrasing, "
                    "audible pauses after complete thoughts, no rushed robotic delivery."
                ),
            },
        })
    payload = {
        "contents": [{"role": "user", "parts": speech_parts}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": [
                        {"speaker": name, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
                        for name, voice in VOICES.items()
                    ]
                }
            },
        },
    }
    result = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
        json=payload, timeout=300
    )
    if not result.ok:
        raise RuntimeError("Gemini TTS returned HTTP " + str(result.status_code) + ": " + result.text[:400])
    parts = result.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    audio = next((part["inlineData"] for part in parts if part.get("inlineData", {}).get("data")), None)
    if audio is None:
        raise RuntimeError("Gemini returned no audio data")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "audio.raw"
        raw.write_bytes(base64.b64decode(audio["data"]))
        target = OUT / "pilot-duo-gemini.mp3"
        args = ["-i", str(raw)] if raw.read_bytes()[:4] == b"RIFF" else ["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw)]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", str(target)], check=True)
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(target)], text=True))
        if duration < 30:
            raise RuntimeError("Audio duration too short")
        (OUT / "pilot-duo-gemini.json").write_text(json.dumps({"duration": round(duration), "voices": VOICES, "model": MODEL, "version": hashlib.sha256(target.read_bytes()).hexdigest()[:16]}, ensure_ascii=False, indent=2) + "\n")
        print("Gemini Yeni Sekme pilot:", round(duration), "seconds")

if __name__ == "__main__":
    main()
