"""Manual Fish Audio voice auditions; never modifies the live podcast."""
import json
import os
from pathlib import Path
from fishaudio import FishAudio

OUT = Path("fish-auditions")
OUT.mkdir(exist_ok=True)
client = FishAudio(api_key=os.environ["FISH_AUDIO_API_KEY"])
voices = {
    "yasar": os.environ["YASAR_REFERENCE_ID"].strip(),
    "necdet": os.environ["NECDET_REFERENCE_ID"].strip(),
}
if not all(voices.values()):
    raise SystemExit("Both YASAR_REFERENCE_ID and NECDET_REFERENCE_ID are required. Create original voice profiles in Fish Audio first.")
samples = {
    "yasar": "Selam! Yeni Sekme'ye hoş geldiniz. Ben Yaşar. Bugün yapay zekâ tarafında ilginç gelişmeler var. Ama önce Necdet'e sorayım, sence asıl önemli haber hangisi?",
    "necdet": "Selam Yaşar. Bence donanım tarafındaki gelişme daha ilginç. Çünkü yeni işlemcilerin sadece hızı değil, enerji tüketimi de ciddi şekilde değişiyor. Gel, birlikte bakalım.",
}
# Low variation favors stable identity. Compare same voice at two temperatures.
variants = {"stable": 0.3, "natural": 0.55, "expressive": 0.7}
manifest = []
for person, ref in voices.items():
    for label, temperature in variants.items():
        filename = f"{person}-{label}.mp3"
        print(f"Generating {filename}", flush=True)
        stream = client.tts.stream_websocket(
            iter([samples[person]]),
            reference_id=ref,
            temperature=temperature,
            top_p=0.7,
            latency="normal",
        )
        with (OUT / filename).open("wb") as f:
            for chunk in stream:
                f.write(chunk)
        if (OUT / filename).stat().st_size < 1000:
            raise RuntimeError(f"Suspiciously small output: {filename}")
        manifest.append({"file": filename, "speaker": person, "variant": label,
                         "temperature": temperature, "reference_id": ref})
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("Six samples ready in GitHub Actions artifacts.")
