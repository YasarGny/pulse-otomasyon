# PULSE — Günlük Teknoloji Yayını

Teknoloji, yapay zekâ, yazılım ve otomobil haberlerinin günlük Türkçe yayını.

- [Günlük Notion bülteni](https://app.notion.com/p/3f922115ab848156bb1fc0649973c0b5)
- [Günün sesli özeti (Edge TTS)](https://yasargny.github.io/pulse-otomasyon/web-player/)
- [Yeni Sekme podcast — Yaşar ve Necdet (Gemini TTS)](https://yasargny.github.io/pulse-otomasyon/web-player/podcast/)

## Günlük yayın akışı

- Türkiye saati 07.00: PULSE zamanlanmış görevi güncel haberleri doğrular ve aynı Notion sayfasını yeniler.
- 07.12: [PULSE Daily Publication](https://github.com/YasarGny/pulse-otomasyon/actions/workflows/pulse-audio.yml) Notion'daki bugünün haberlerini kontrol eder, Edge TTS sesli özeti ve Gemini ile iki sunuculu podcast'i üretir.
- İki ses dosyası da doğrulanmadan yayın commit'i oluşturulmaz. GitHub Actions ve Gemini gecikmeleri nedeniyle 07.30 hedefi garanti değildir.
- 16 Ekim 2026 ilk gerçek Sayı 001, sonraki günler tarih farkıyla numaralandırılır.

## Gizli değişkenler

GitHub Actions secrets: `NOTION_TOKEN`, `GEMINI_API_KEY`.
Özel sesler: Yaşar `voice_glt4mz1jtaeh`, Necdet `voice_8nqcoox86z5q`.
Günlük sesli özetin **ses üretimi** Edge TTS ile yapılır; Gemini yalnızca anlatım metnini yazar.

## Elle çalıştırma

GitHub Actions > PULSE Daily Publication > Run workflow. İşlem, bugünün Notion bülteni hazırlanmadıysa bir süre bekler; eski günü yayınlamaz.
