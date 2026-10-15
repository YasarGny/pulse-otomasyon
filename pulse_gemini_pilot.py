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

NOTION_PAGE = "3f922115ab848156bb1fc0649973c0b5"
VOICES = {"Yaşar": "Puck", "Necdet": "Algenib"}
MODEL = "gemini-2.5-flash-preview-tts"
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

def script(stories):
    """Short, distinct conversational turns instead of repetitive Q&A."""
    lines = [
        ("Yaşar", "PULSE sunar: Yeni Sekme. Selam! Ben Yaşar."),
        ("Necdet", "Ben de Necdet. Bugün yine teknoloji gündemi dolu. Kahveler hazırsa başlayalım."),
        ("Yaşar", "Hazır. Ama bugün başlıkları okuyup kaçmak yok; ne işe yarıyor, onu da konuşacağız."),
    ]
    reactions = [
        ("Necdet", "İlginç. Ama duyurulan şeyle gerçek hayatta çalışması aynı şey değil, değil mi?"),
        ("Yaşar", "Aynen öyle. İşin güzel tarafı var; bir de henüz cevaplanmamış sorular var."),
        ("Yaşar", "Dur, burada asıl dikkatimi çeken şey şu: Bu gelişme sadece şirketleri değil, kullanıcıları da etkileyebilir."),
        ("Necdet", "Kesinlikle. Ama etkisinin ne kadar büyük olacağını görmek için biraz zaman lazım."),
        ("Necdet", "Peki bu gelişme gerçekten oyunu değiştirir mi, yoksa şimdilik beklenti mi?"),
        ("Yaşar", "Bence hemen kesin konuşmayalım. Önce uygulamada ne olduğuna bakmak lazım."),
        ("Yaşar", "Bir saniye, burada güvenlik ve kontrol meselesini atlamayalım."),
        ("Necdet", "Haklısın. Teknoloji ne kadar güçlü olursa olsun, denetim kısmı da önemli."),
        ("Necdet", "Şimdi bunun bir de maliyet tarafı var. Heyecan tamam ama faturayı kim ödeyecek?"),
        ("Yaşar", "İşte o soru önemli. Teknoloji kadar sürdürülebilir olması da gerekiyor."),
    ]
    for i, (title, summary) in enumerate(stories):
        lead = "Yaşar" if i % 2 == 0 else "Necdet"
        lines.append((lead, ("Şöyle bir gelişme var: " if i else "İlk konu dikkat çekici: ") + title + ". " + summary))
        lines.extend(reactions[i * 2:i * 2 + 2])
        if i < len(stories) - 1:
            lines.append(("Necdet" if lead == "Yaşar" else "Yaşar", ["Neyse, bir diğer habere bakalım.", "Peki, şimdi başka bir konuya geçelim.", "Güzel, sırada ne var?", "Tamam, bir de şuna bakalım."][i]))
    lines.extend([
        ("Yaşar", "Bugünlük bizden bu kadar. Haberlerin kaynakları PULSE bülteninde."),
        ("Necdet", "Bir sonraki Yeni Sekme'de görüşürüz. Kendinize iyi bakın."),
    ])
    return "\\n".join(name + ": " + text for name, text in lines)

def main():
    dialogue = script(read_news())
    payload = {
        "contents": [{"parts": [{"text": "İki farklı erkek sunucunun samimi Türkçe teknoloji podcast sohbeti. Yaşar genç, sıcak, canlı; Necdet daha tok, olgun, sakin ve hafif esprili. Sesler belirgin şekilde ayrı duyulsun. İkisi de acele etmeden, orta-yavaş doğal konuşma temposuyla, cümle aralarında nefes alıp kısa duraklamalar yaparak konuşsun. Haber spikeri gibi okuma; arkadaş sohbeti gibi sıcak, yer yer gülümseyerek konuş. Konuşma etiketlerini seslendirme. Metne yeni olgusal iddia ekleme.\n\n" + dialogue}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": [
                        {"speaker": name, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
                        for name, voice in VOICES.items()
                    ]
                }
            }
        }
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
