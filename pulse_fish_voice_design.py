"""Isolated Fish Audio voice-design auditions and two short podcast demos."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import requests

ROOT = Path("fish-auditions")
ROOT.mkdir(exist_ok=True)
API = "https://api.fish.audio"
HEADERS = {"Authorization": "Bearer " + os.environ["FISH_AUDIO_API_KEY"]}
PREVIEW = "Selam! Yeni Sekme'ye hoş geldiniz. Bugün teknoloji dünyasında neler olmuş, beraber bakalım."
PERSONAS = {
    "yasar": "A unique authentic native Turkish male voice, age 30-31, warm, friendly, youthful medium-low register, curious, lightly energetic, relaxed conversational rhythm, no announcer tone, no robotic emphasis.",
    "necdet": "A distinct authentic native Turkish male voice, age 30-31, youthful and calm, slightly deeper than his cohost, clear and naturally witty, relaxed conversational rhythm, no older-man character, no announcer tone.",
}
TURNS = [
    ("yasar", "PULSE sunar: Yeni Sekme! Selam Necdet, bugün yapay zekâ tarafında yeni gelişmeler var. Ama ben en çok bunun telefonlara nasıl yansıyacağını merak ediyorum."),
    ("necdet", "Ben de tam onu düşünüyordum Yaşar. Bir özellik çok etkileyici görünebilir, ama pil ömrünü azaltıyorsa günlük kullanımda aynı heyecanı vermiyor."),
    ("yasar", "Aynen öyle. Bir de her şey buluta gidince internet bağlantısı şart oluyor. Peki sence cihaz üzerinde çalışan yapay zekâ bu sorunu çözer mi?"),
    ("necdet", "Bir kısmını çözer. Ama bunun için güçlü çip, iyi soğutma ve verimli yazılım gerekiyor. Yani mesele sadece işlemci hızından ibaret değil."),
    ("yasar", "Güzel. Bugünkü kısa denememiz burada bitsin. Yeni Sekme'de görüşürüz!"),
]
def post(path, *, json_body=None, files=None, data=None, model=None):
    headers = dict(HEADERS)
    if model:
        headers["model"] = model
    response = requests.post(API + path, headers=headers, json=json_body, files=files, data=data, timeout=240)
    if not response.ok:
        raise RuntimeError(f"{path}: HTTP {response.status_code}: {response.text[:500]}")
    return response

def to_mp3(raw, path, sample_rate=None):
    if raw[:4] == b"RIFF" or raw[:3] == b"ID3" or raw[:2] == b"\\xff\\xfb":
        path.write_bytes(raw)
        return
    if not sample_rate:
        raise RuntimeError("Unknown preview audio format; cannot convert without sample rate")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pcm") as temp:
        temp.write(raw); temp.flush()
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
                        "-i", temp.name, "-codec:a", "libmp3lame", "-b:a", "128k", str(path)], check=True)

def voice_design(person):
    response = post("/v1/voice-design", json_body={
        "instruction": PERSONAS[person], "reference_text": PREVIEW,
        "language": "tr", "n": 2, "speed": 1, "num_step": 32,
        "guidance_scale": 2, "instruct_guidance_scale": 0,
    }, model="voice-design-1").json()
    candidates = response["candidates"]
    if len(candidates) != 2:
        raise RuntimeError("Expected two voice design candidates")
    return candidates

def create_private_voice(person, index, candidate):
    raw = base64.b64decode(candidate["audio_base64"])
    preview = ROOT / f"{person}-{index}-preview.mp3"
    # The API returns audio and a sample rate; WAV/MP3 is detected, PCM converted.
    to_mp3(raw, preview, candidate.get("sample_rate"))
    with preview.open("rb") as stream:
        form = {"type": "tts", "title": f"PULSE Yeni Sekme {person} aday {index}",
                "train_mode": "fast", "visibility": "private", "texts": PREVIEW}
        # Voice Design candidate ids may be signatures; keep model creation compatible without assuming it.
        result = post("/model", data=form,
                      files={"voices": (preview.name, stream, "audio/mpeg")}).json()
    voice_id = result.get("_id") or result.get("id")
    if not voice_id:
        raise RuntimeError("Model created but no id returned")
    return voice_id

def synthesize(text, voice_id, path):
    response = post("/v1/tts", json_body={
        "text": text, "reference_id": voice_id, "format": "mp3",
        "temperature": 0.45, "top_p": 0.7
    }, model="s2.1-pro-free")
    path.write_bytes(response.content)
    if path.stat().st_size < 1000:
        raise RuntimeError(f"Empty or suspicious output: {path}")

def merge(paths, output):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        wavs = []
        for i, path in enumerate(paths):
            wav = td / f"{i:02}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path),
                            "-ar", "44100", "-ac", "1", str(wav)], check=True)
            wavs.append(wav)
        listing = td / "concat.txt"
        listing.write_text("".join(f"file '{p}'\\n" for p in wavs))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-af", "loudnorm=I=-18:TP=-2:LRA=11",
                        "-b:a", "128k", str(output)], check=True)

def main():
    profiles = {}
    for person in PERSONAS:
        print("Designing", person, flush=True)
        profiles[person] = []
        for index, candidate in enumerate(voice_design(person), start=1):
            voice_id = create_private_voice(person, index, candidate)
            profiles[person].append(voice_id)
            print(f"{person} candidate {index}: {voice_id}", flush=True)
    for variant in (1, 2):
        paths = []
        for i, (person, text) in enumerate(TURNS):
            path = ROOT / f"v{variant}-turn-{i:02}.mp3"
            synthesize(text, profiles[person][variant - 1], path)
            paths.append(path)
        merge(paths, ROOT / f"yeni-sekme-deneme-{variant}.mp3")
    (ROOT / "voice-ids.json").write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    print("Finished. Compare four preview voices and two short podcasts in the workflow artifact.")
if __name__ == "__main__":
    main()
