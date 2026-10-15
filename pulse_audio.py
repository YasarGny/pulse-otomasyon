"""Generate PULSE narration from today's Notion bulletin for public GitHub Pages."""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

import asyncio
import edge_tts
import requests

API = "https://api.notion.com/v1"
PAGE = "3f922115ab848156bb1fc0649973c0b5"
HEAD = {"Authorization": "Bearer " + os.environ["NOTION_TOKEN"], "Notion-Version": "2022-06-28"}
OUT = Path("web-player")
MONTHS = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()


def req(path, **params):
    r = requests.get(API + path, headers=HEAD, params=params or None, timeout=60)
    r.raise_for_status()
    return r.json()


def rich(block):
    data = block.get(block.get("type"), {})
    return "".join(item.get("plain_text", "") for item in data.get("rich_text", []))


def normalized(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


def children(block_id):
    results = []
    cursor = None
    while True:
        args = {"page_size": 100}
        if cursor:
            args["start_cursor"] = cursor
        response = req(f"/blocks/{block_id}/children", **args)
        results.extend(response["results"])
        if not response.get("has_more"):
            return results
        cursor = response["next_cursor"]


def voice(s):
    for word, spoken in {"PULSE": "Pals", "AI": "yapay zeka", "DeepMind": "Diip Maynd", "AlphaFold": "Alfa Fold", "Google": "Gugıl", "Cloud": "Klaud"}.items():
        s = re.sub(r"\b" + re.escape(word) + r"\b", spoken, s, flags=re.I)
    return s


def main():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
    date = f"{today.day} {MONTHS[today.month - 1]} {today.year}"
    blocks = children(PAGE)
    intro = " ".join(rich(b) + " " + (" ".join(rich(c) for c in children(b["id"])) if b.get("has_children") and b["type"] == "callout" else "") for b in blocks[:5])
    if normalized(date) not in normalized(intro) and today.strftime("%d.%m.%Y") not in intro:
        raise RuntimeError("Bugünün bülteni Notion'da henüz hazır değil; eski haberi seslendirmiyorum.")

    # Read only today's news section; ignore archive and testing headings.
    in_news = False
    stories = []
    for i, block in enumerate(blocks):
        typ, title = block["type"], rich(block)
        if typ == "heading_1":
            if "Bugünün haberleri" in title:
                in_news = True
            elif in_news:
                break
        if in_news and typ == "heading_3":
            summary = next((rich(b) for b in blocks[i + 1:i + 4] if b["type"] == "paragraph" and rich(b)), "")
            if summary:
                stories.append(title + ". " + summary)
    if len(stories) < 3:
        raise RuntimeError("En az üç güncel haber bulunamadı; yayın yapılmadı.")

    # Prepare a concise, fact-grounded single-narrator script with Gemini.
    # The Notion issue is the only factual source; the model may not invent news.
    source = "\n".join(f"{i+1}. {item}" for i, item in enumerate(stories))
    model = os.getenv("PULSE_SUMMARY_SCRIPT_MODEL", "gemini-3.8-flash")
    prompt = (
        "Sen PULSE Türkçe teknoloji bülteni editörüsün. Aşağıdaki doğrulanmış "
        "haber notlarından, doğal ve akıcı, haber sayısına göre yaklaşık 3-7 dakikalık tek sunuculu "
        "sesli özet metni oluştur. Önce en önemli gelişmeyle gir, haberleri "
        "önemine göre işle, her birinin neden önemli olduğunu açıkla. "
        "Her haberi mutlaka ayrı ve anlaşılır biçimde ele al, hiçbirini atlama; her haberin ne olduğunu ve neden önemli olduğunu açıkla. Gereksiz açılış kalıpları ve mekanik sıra numaraları kullanma. "
        "Kaynakta olmayan tarih, rakam, alıntı veya iddia ekleme. "
        "Yalnızca seslendirilecek düz metni döndür. Tarih: " + date
        + "\nHaberler:\n" + source
    )
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.35, "maxOutputTokens": 3000}},
        timeout=120,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini did not return a narration script")
    script = "".join(p.get("text", "") for p in candidates[0]["content"]["parts"]).strip()
    if not 450 <= len(script) <= 11000:
        raise RuntimeError("Narration script failed length validation")

    # Use the established Turkish Edge TTS narrator for the daily audio brief.
    # Gemini is only used to edit the script, not to synthesize this audio.
    OUT.mkdir(exist_ok=True)
    asyncio.run(edge_tts.Communicate(
        text=voice(script),
        voice="tr-TR-EmelNeural",
        rate="+0%",
    ).save(str(OUT / "latest.mp3")))
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(OUT / "latest.mp3")], text=True).strip())
    if duration < 20 or (OUT / "latest.mp3").stat().st_size < 15000:
        raise RuntimeError("Generated audio failed validation")
    (OUT / "latest.json").write_text(json.dumps({"date": date, "audio": "latest.mp3", "version": hashlib.sha256((OUT / "latest.mp3").read_bytes()).hexdigest()[:16], "title": "Günün Sesli Özeti", "duration": round(duration)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PULSE ready:", date, "stories:", len(stories), "duration:", round(duration), "seconds")


if __name__ == "__main__":
    main()
