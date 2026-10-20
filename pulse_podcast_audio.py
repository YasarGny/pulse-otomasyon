"""Chunked Gemini 3.8 multi-speaker synthesis and transparent podcast mastering."""
import base64
import hashlib
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import requests
from pulse.audio_quality import assert_no_long_silence

MODEL = os.getenv("PULSE_TTS_MODEL", "gemini-3.8-flash-tts")
VOICES = {"Yaşar": os.getenv("PULSE_YASAR_VOICE_ID", "voice_glt4mz1jtaeh"), "Necdet": os.getenv("PULSE_NECDET_VOICE_ID", "voice_8nqcoox86z5q")}
API = "https://generativelanguage.googleapis.com/v1beta/interactions"

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
        if speaker not in VOICES:
            raise ValueError("Unknown podcast speaker: " + str(speaker))
        parts.append({
            "type": "text",
            "text": turn["text"],
            "annotations": [{"type": "speech_metadata", "speaker": speaker}],
        })
    return parts


def _provider_audio(payload, number, *, strict_audio):
    # Retry network/server failures only. Never re-bill TTS because ffmpeg fails.
    for attempt in range(3):
        try:
            result = requests.post(
                API,
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"],
                         "Content-Type": "application/json"},
                json=payload, timeout=300,
            )
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt * 2)
            continue
        if result.status_code in (400, 401, 402, 403, 429):
            raise RuntimeError(
                "Gemini TTS HTTP " + str(result.status_code)
            )
        if not result.ok:
            if attempt == 2:
                raise RuntimeError(
                    "TTS segment " + str(number) + " HTTP "
                    + str(result.status_code)
                )
            time.sleep(2 ** attempt * 2)
            continue
        break
    response = result.json()
    from pulse.usage import record
    record("podcast-tts", MODEL, response, sum(len(part.get("text", "")) for item in payload["input"] for part in item["content"]))
    encoded = None
    for step in response.get("steps", []):
        for content in step.get("content", []):
            if content.get("data") and (
                content.get("type") in ("audio", "output_audio")
                or content.get("mime_type", "").startswith("audio/")
            ):
                encoded = content["data"]
                break
        if encoded:
            break
    # Preserve the legacy producer's response handling until cutover. The new
    # pipeline explicitly requires typed audio; it never treats arbitrary data as PCM.
    if not encoded and not strict_audio:
        for step in response.get("steps", []):
            for content in step.get("content", []):
                if content.get("data"):
                    encoded = content["data"]
                    break
            if encoded:
                break
    if not encoded:
        raise RuntimeError("No audio returned for segment " + str(number))
    return base64.b64decode(encoded)



def synthesize(group, destination, number, *, strict_audio=False):
    # Gemini 3.8 uses the Interactions API, not legacy generateContent.
    # Existing prebuilt voices remain defaults until persistent voice IDs are chosen.
    payload = {
        "model": MODEL,
        "input": [{"type": "user_input", "content": make_parts(group)}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {
            "speech_config": {
                "mode": "conversational",
                "speakers": [
                    {"speaker": speaker, "voice": voice}
                    for speaker, voice in VOICES.items()
                ],
            }
        },
    }
    raw = destination.with_suffix(".raw")
    receipt = raw.with_name(raw.name + '.json')
    identity = hashlib.sha256(json.dumps({'payload': payload, 'strict_audio': strict_audio}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cached = False
    if raw.is_file() and receipt.is_file():
        try:
            saved = json.loads(receipt.read_text())
            cached = saved.get('input_sha256') == identity and saved.get('audio_sha256') == hashlib.sha256(raw.read_bytes()).hexdigest()
        except (ValueError, OSError):
            pass
    if not cached:
        content = _provider_audio(payload, number, strict_audio=strict_audio)
        raw.write_bytes(content)
        receipt.write_text(json.dumps({'input_sha256': identity, 'audio_sha256': hashlib.sha256(content).hexdigest()}))
    input_args = ["-i", str(raw)] if raw.read_bytes()[:4] == b"RIFF" else [
        "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw)]
    run("ffmpeg", "-v", "error", "-y", *input_args, "-ar", "44100",
        "-ac", "1", "-c:a", "pcm_s16le", str(destination))
    if duration(destination) < 2:
        raise RuntimeError("Suspiciously short TTS segment " + str(number))
    raw.unlink(missing_ok=True)
    receipt.unlink(missing_ok=True)


def render(turns, target, *, strict_audio=False, checkpoint_dir=None):
    # Keep custom voices consistent; no fixed station ident or style instructions.
    groups = chunks(turns, max_chars=3500, max_turns=24)
    identity = hashlib.sha256(json.dumps({'turns': turns, 'voices': VOICES, 'model': MODEL}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    persistent = Path(checkpoint_dir) / identity if checkpoint_dir else None
    if persistent:
        persistent.mkdir(parents=True, exist_ok=True)
    with (nullcontext(str(persistent)) if persistent else tempfile.TemporaryDirectory()) as folder, tempfile.TemporaryDirectory() as assembly_folder:
        root = Path(folder).resolve()
        assembly = Path(assembly_folder)
        paths = []
        for index, group in enumerate(groups):
            path = root / ("part_%03d.wav" % index)
            valid = False
            if persistent and path.exists():
                try:
                    assert_no_long_silence(path)
                    valid = duration(path) >= max(2, sum(len(t['text'].split()) for t in group) / 220 * 60)
                except (ValueError, subprocess.CalledProcessError):
                    valid = False
            if not valid:
                path.unlink(missing_ok=True)
                partial = path.with_name(path.stem + '.partial.wav')
                try:
                    for attempt in range(2):
                        synthesize(group, partial, index, strict_audio=strict_audio)
                        try:
                            if duration(partial) < max(2, sum(len(t['text'].split()) for t in group) / 220 * 60):
                                raise ValueError('TTS segment shorter than its dialogue')
                            assert_no_long_silence(partial)
                        except (ValueError, subprocess.CalledProcessError):
                            partial.unlink(missing_ok=True)
                            if attempt: raise
                            continue
                        partial.replace(path)
                        break
                finally:
                    partial.unlink(missing_ok=True)
            paths.append(path)
        # Short intentional pause after ident; small section gaps avoid rushed edits.
        manifest = assembly / "concat.txt"
        with manifest.open("w", encoding="utf-8") as file:
            for index, path in enumerate(paths):
                file.write("file '" + str(path) + "'\n")
                if index < len(paths) - 1:
                    gap = 0.75 if index == 0 else 0.25
                    silence = assembly / ("silence_%03d.wav" % index)
                    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "anullsrc=r=44100:cl=mono", "-t", str(gap),
                        "-c:a", "pcm_s16le", str(silence))
                    file.write("file '" + str(silence) + "'\n")
        merged = assembly / "merged.wav"
        run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(manifest), "-c:a", "pcm_s16le", str(merged))
        # Loudness consistency without altering pitch or speed.
        run("ffmpeg", "-v", "error", "-y", "-i", str(merged), "-af",
            "loudnorm=I=-18:TP=-2:LRA=11", "-ar", "44100", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "128k", str(target))
    if persistent:
        (persistent / 'merged.wav').unlink(missing_ok=True)
        for gap in persistent.glob('silence_*.wav'):
            gap.unlink()
    assert_no_long_silence(target)
    seconds = duration(target)
    if seconds < 2:
        raise RuntimeError("Rendered podcast unexpectedly short")
    return {"duration": round(seconds, 1), "segments": len(groups), "model": MODEL,
            "voices": VOICES, "mastering": "loudnorm -18 LUFS, -2 dBTP"}
