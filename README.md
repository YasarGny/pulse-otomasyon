# PULSE — Günlük gündemimiz

Teknoloji ve oyun dünyasında ilgimizi çeken haberler; her sabah 07.30'da sesli
özetler ve dinlemelik sohbetler. Kişisel, bağımsız bir yayın projesi.

- **PULSE Teknoloji:** yapay zekâ, bilim, uzay, yazılım ve dijital dünya.
  Podcast: **Yeni Sekme**, Yaşar ve Necdet.
- **PULSE Oyun:** PC, konsol, duyurular, güncellemeler ve oyun kültürü.
  Podcast: **Moradon FM**, Yaşar ve Necdet.

Hedef adres: **https://yasargny.github.io/**. Mevcut
[sesli yayın](https://yasargny.github.io/pulse-otomasyon/web-player/) geçiş
onaylanana kadar korunur.

## Yapı

`site/` tek web kaynağıdır. `pulse/` Notion bağımsız RSS → Gemini metin →
Edge TTS özet + mevcut Gemini podcast → tam MP3/JSON doğrulama → atomik sürüm
hattıdır. Yalnız doğrulanmış statik çıktı `YasarGny/YasarGny.github.io` deposuna
aktarılır. İki yayın birlikte hazır olmadan günlük yayın açılmaz.

## Hızlı doğrulama

Python 3.12, Node 22+ ve FFmpeg/ffprobe ile:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
python -m unittest discover -s tests -p 'test_*.py' -v
npm test
npx playwright install --with-deps chromium
npm run test:browser
```

Tarayıcı testleri yalnız sentetik içerik kullanır; `test-results/` altında
masaüstü/mobil görseller üretir. Gerçek Gemini ve Edge TTS entegrasyonları için
ayrı, anahtarlı deneme gerekir. Anahtarsız testler API başarısını kanıtlamaz.

**Yeni canlı otomasyon varsayılan olarak kapalıdır.** Eski Notion iş akışları ve
oynatıcı dosyaları korunur. GitHub App, Secrets, deneme, son onay, geçiş ve geri
alma adımları: **[İşletim rehberi](docs/OPERATIONS.md)**.
