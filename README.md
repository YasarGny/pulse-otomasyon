# PULSE — Günlük gündemimiz

Teknoloji ve oyun dünyasında ilgimizi çeken haberler; her sabah 07.30'da sesli
özetler ve dinlemelik sohbetler. Kişisel, bağımsız bir yayın projesi.

- **PULSE Teknoloji:** yapay zekâ, bilim, uzay, yazılım ve dijital dünya.
  Podcast: **Yeni Sekme**, Yaşar ve Necdet.
- **PULSE Oyun:** PC, konsol, duyurular, güncellemeler ve oyun kültürü.
  Podcast: **Moradon FM**, Yaşar ve Necdet.

Yayın adresi: **https://yasargny.github.io/**. Kaynak depo private tutulabilir; yayın deposu yalnız herkese açık statik çıktıyı içerir.
Eski proje Pages adresi kullanım dışıdır; eski oynatıcı ve ses dosyaları kaldırılmıştır.

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

**Canlı yayın ve günlük zamanlama kullanıcı onayıyla açılmıştır.**
`PULSE_AUTOMATION_ENABLED=false` zamanlamayı durdurur. Manuel çalıştırmalar
varsayılan olarak denemedir. Notion bağlantıları ve eski üretim iş akışları kaldırılmıştır.
GitHub App, Secrets, doğrulama ve geri alma adımları: **[İşletim rehberi](docs/OPERATIONS.md)**.

## Ses ve arayüz

Özet, her haberin kısa ve yorumsuz `brief` alanını Edge TTS ile seslendirir; başlığı
ve `why` analizini okumaz. Podcast Yaşar'ın yönettiği tematik sohbet olarak üretilir,
ayrı editör ve kaynak denetçisi onaylamadan seslendirilmez. Özel Gemini sesleri
korunur. Manuel `refresh_audio` aynı tarih ve sayıda yeni, değişmez bir ses sürümü
üretir; normal tekrarlar eski ses sürümüne dönmez.

Mobil arayüzde kırpılmayan responsive WebP kapaklar ve hız/ses/zaman kontrolü
olan erişilebilir özel oynatıcılar vardır. Yeni sayfa açılışında matbaa parlamaz;
önce sunucu durumu doğrulanır. Tasarım ve sınırlar: [DESIGN.md](docs/DESIGN.md).
