# PULSE · Günlük Sesli Teknoloji Bülteni

Notion'daki günlük PULSE haberleri, GitHub Actions ile Türkçe seslendirilir ve GitHub Pages üzerinden Notion sayfasında gömülü olarak dinlenir.

## Kullanılan dosyalar
- `pulse_audio.py` — Güncel Notion haberlerinden Türkçe MP3 ve `latest.json` üretir.
- `.github/workflows/pulse-audio.yml` — Her gün Türkiye saatiyle yaklaşık 09.20'de ses oluşturur ve yayımlar. Manuel tetiklenebilir.
- `web-player/index.html` — Notion içinde çalışan ses oynatıcı.
- `web-player/latest.mp3` ve `latest.json` — Son ses kaydı ve bilgileri.
- `index.html` — GitHub Pages giriş yönlendirmesi.

Oynatıcı: https://yasargny.github.io/pulse-otomasyon/web-player/

**Gizlilik:** GitHub Pages üzerinde yayımlanan ses kaydı ve bu deponun kodları herkese açıktır. `NOTION_TOKEN` yalnızca GitHub Actions secret olarak tutulmalıdır. Notion sayfası public yapılmak zorunda değildir.

**Not:** Ses oluşturma işi yalnızca Notion'da o günün haberleri mevcutsa çalışır. Haber metninin hazırlanması bu ses iş akışının kapsamı dışındadır.
