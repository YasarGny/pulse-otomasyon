"""Generate an editorially grounded Turkish two-host podcast dialogue using Gemini."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import re
import requests

MODEL = os.getenv("PULSE_SCRIPT_MODEL", "gemini-3.8-flash")

SYSTEM = """Sen Yeni Sekme adlı Türkçe teknoloji podcast'inin deneyimli editörü ve senaristisin.
Hedef: Haber okumayan, haberleri anlayıp değerlendiren iki samimi teknoloji meraklısının gerçekçi sohbeti.
Yaşar: yazılım, yapay zekâ ve kullanıcı deneyimine meraklı; zeki, sıcak, meraklı.
Necdet: donanım, otomotiv, maliyet ve uygulanabilirliğe meraklı; nüktedan, sakin, sorgulayıcı.
İkisi de her konuyu konuşabilir. Kişilikleri karikatürleştirme. Birbirlerinin söylediklerine somut cevap versinler.
Haberlerin doğrulanmış olgularını değiştirme, sayı, tarih, alıntı, şirket beyanı, deneyim veya kaynak UYDURMA.
Kaynaklarda olmayan bir bilgiyi kesin gerçek gibi sunma. Yorum ve olasılıkları açıkça ayır.
Görüş ayrılığı ZORUNLU DEĞİL; yalnızca yoruma açık, gerçekten tartışılabilir konularda olsun.
Her haberde aynı soru-cevap düzenini, kalıp geçişleri, boş övgüleri ve tekrarlanan "haklısın"ları KULLANMA.
Gerçek sohbet hissi için kısa ve uzun konuşma sıraları, yerinde mizah, doğal merak, somut gerekçeler ve konu bağlantıları kur.
Rol yaparak yaşanmış kişisel anı veya sahte deneyim anlatma. Gerçek kişilerden ses taklidi yapma.
Abartılı heyecan, gereksiz çatışma, yapay kahkaha, aşırı argo ve sunucu etiketlerini konuşma metnine katma.
Her konuşma satırı yaklaşık 1-4 cümle olsun. Bir konuşmacı en fazla 100 kelime aralıksız konuşsun.
Haberlerin önemine göre konuşma süresini kendiliğinden belirle. Süre hedefi, minimum kelime sayısı veya dakika doldurma zorunluluğu yok. Önemli haberleri yeterince değerlendir, kısa haberleri kısa geç; konu bitince doğal biçimde kapanış yap.
Açılış mutlaka PULSE sunar: Yeni Sekme program adıyla başlasın; Yaşar ve Necdet isimlerini doğal biçimde söylesin. Yayın tarihini doğru ve Türkçe biçimde bir kez belirt. Ardından bugünün en dikkat çekici konularından kısa bir merak uyandırıcı giriş yap. Kapanışta günün önemli çıkarımını kısaca bağla, PULSE bültenindeki kaynaklara yönlendir ve samimi bir vedayla bitir. Her gün aynı giriş-kapanış cümlelerini ezberden tekrarlama.\nKonuşma metnini sesli okunabilir yaz: uzun virgül zincirleri ve kısaltmalar yerine kısa nefeslik cümleler, anlamlı noktalama ve doğal duraklar kullan. Yapay kahkaha, [duraklama] gibi sahne yönergeleri ve gereksiz ünlemler ekleme.
YALNIZCA geçerli JSON döndür: {"turns":[{"speaker":"Yaşar","text":"..."},{"speaker":"Necdet","text":"..."}]}.
Başka anahtar veya markdown döndürme."""

def generate(stories):
    source = [{"id": i + 1, "headline": title, "verified_summary": summary} for i, (title, summary) in enumerate(stories)]
    today = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "Yayın tarihi (Türkiye): " + today + ". Bu doğrulanmış haber notlarıyla süre sınırı olmadan, haberlerin gerçekten gerektirdiği uzunlukta özgün bir Türkçe sohbet hazırla. Haberler arasında anlamlı bağlantılar kur. Her haberde gerçek yorum, gerekçe ve somut çıkarım olsun. Haber dışı olgusal iddia ekleme. JSON haberler: " + json.dumps(source, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.85, "maxOutputTokens": 8192},
    }
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
        json=payload, timeout=180,
    )
    if not response.ok:
        raise RuntimeError("Podcast script generation failed HTTP " + str(response.status_code) + ": " + response.text[:300])
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise RuntimeError("No script candidates returned")
    raw = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
    result = json.loads(raw)
    turns = result.get("turns", [])
    if not 14 <= len(turns) <= 150:
        raise RuntimeError("Invalid number of dialogue turns")
    if any(t.get("speaker") not in ("Yaşar", "Necdet") or not isinstance(t.get("text"), str) or not t["text"].strip() or len(t["text"]) > 1000 for t in turns):
        raise RuntimeError("Invalid dialogue speaker or text")
    if len({t["speaker"] for t in turns}) != 2:
        raise RuntimeError("Both presenters must participate")
    dialogue = "\n".join(t["speaker"] + ": " + re.sub(r"\\s+", " ", t["text"]).strip() for t in turns)
    return dialogue, turns
