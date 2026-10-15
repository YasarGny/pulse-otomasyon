"""Chunked Gemini 3.8 multi-speaker synthesis and transparent podcast mastering."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import requests

MODEL = os.getenv("PULSE_TTS_MODEL", "gemini-3.8-flash-tts")
VOICES = {"Yaşar": "Puck", "Necdet": "Algenib"}
API = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"

def run(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout

def duration(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(path)).strip())

def chunks(turns, max_chars=3500, max_turns=24):
    groups, current, chars = [], [], 0
    for turn in turns:
        size = len(turn["text"])
        if current and (chars + size > max_chars or len(current) >= max_turns):
            groups.append(current)
            current, chars = [], 0
        current.append(turn)
        chars += size
    if current:
        groups.append(current)
    return groups

def make_parts(turns):
    parts = []
    for turn in turns:
        speaker = turn["speaker"]
        style = ("Turkish male podcast presenter. Keep exactly the same vocal identity, timbre, accent, and pitch throughout. Speak naturally at a measured pace; vary emphasis without changing voice."\n                 if speaker == "Yaşar" else\n                 "Turkish male podcast co-host. Keep exactly the same vocal identity, timbre, accent, and pitch throughout. Speak calmly and naturally.")
        parts.append({"text": turn["text"], "speechMetadata": {"speaker": speaker, "style": style}})
    return parts

def synthesize(group, destination, number):
    payload = {
        "contents": [{"role": "user", "parts": make_parts(group)}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": [
                    {"speaker": name, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
                    for name, voice in VOICES.items()
                ]
            }}
        }
    }
    for attempt in range(3):
        try:
            result = requests.post(API, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"],
                                    "Content-Type": "application/json"}, json=payload, timeout=300)
            if result.status_code == 429:
                raise RuntimeError("Gemini TTS quota exceeded (429). Stopping immediately; check billing and limits before rerunning. " + result.text[:300])
            if not result.ok:
                raise RuntimeError("TTS segment " + str(number) + " HTTP " +
                                   str(result.status_code) + ": " + result.text[:350])
            parts = result.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            audio = next((p["inlineData"] for p in parts if p.get("inlineData", {}).get("data")), None)
            if not audio:
                raise RuntimeError("No audio returned for segment " + str(number))
            raw = destination.with_suffix(".raw")
            raw.write_bytes(base64.b64decode(audio["data"]))
            input_args = ["-i", str(raw)] if raw.read_bytes()[:4] == b"RIFF" else [
                "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw)]
            run("ffmpeg", "-v", "error", "-y", *input_args, "-ar", "44100",
                "-ac", "1", "-c:a", "pcm_s16le", str(destination))
            if duration(destination) < 2:
                raise RuntimeError("Suspiciously short TTS segment " + str(number))
            raw.unlink(missing_ok=True)
            return
        except (requests.RequestException, RuntimeError, subprocess.CalledProcessError) as exc:
            if "quota exceeded (429)" in str(exc) or attempt == 2:
                raise
            time.sleep(2 ** attempt * 2)

def render(turns, target):
    # Show ident is kept in the same synthesis call to minimize voice drift and quota usage.
    ident = [{"speaker": "Yaşar", "text": "PULSE sunar. Yeni Sekme."}]
    # One synthesis request keeps voice identity within a single generation.\n    # Never silently split the dialogue: that can change the perceived speaker.\n    groups = [ident + turns]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        paths = []
        for index, group in enumerate(groups):
            path = root / ("part_%03d.wav" % index)
            synthesize(group, path, index)
            paths.append(path)
        # Short intentional pause after ident; small section gaps avoid rushed edits.
        manifest = root / "concat.txt"
        with manifest.open("w", encoding="utf-8") as file:
            for index, path in enumerate(paths):
                file.write("file '" + str(path) + "'\n")
                if index < len(paths) - 1:
                    gap = 0.75 if index == 0 else 0.25
                    silence = root / ("silence_%03d.wav" % index)
                    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "anullsrc=r=44100:cl=mono", "-t", str(gap),
                        "-c:a", "pcm_s16le", str(silence))
                    file.write("file '" + str(silence) + "'\n")
        merged = root / "merged.wav"
        run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(manifest), "-c:a", "pcm_s16le", str(merged))
        # Loudness consistency without altering pitch or speed.
        run("ffmpeg", "-v", "error", "-y", "-i", str(merged), "-af",
            "loudnorm=I=-18:TP=-2:LRA=11", "-ar", "44100", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "128k", str(target))
    seconds = duration(target)
    if seconds < 30:
        raise RuntimeError("Rendered podcast unexpectedly short")
    return {"duration": round(seconds, 1), "segments": len(groups), "model": MODEL,
            "voices": VOICES, "mastering": "loudnorm -18 LUFS, -2 dBTP"}
