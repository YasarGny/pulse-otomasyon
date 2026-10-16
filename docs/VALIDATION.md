# Doğrulama kaydı — 16 Ekim 2026

Bu kayıt yerel bulut makinesindeki doğrulamadır; canlıya geçiş, GitHub Actions
çalışması veya Pages dağıtımı yapıldığı iddiası değildir.

| Kontrol | Sonuç |
|---|---|
| Python 3.12 / FFmpeg / ffprobe / bağımlılıklar | Hazır; pip check başarılı. |
| Python unittest | **42 geçti**, başarısız/atlanan test yok. |
| Node yayın kapısı testleri | **14 geçti**, başarısız/atlanan test yok. |
| Chromium işlevsel tarayıcı senaryoları | **19 geçti**. |
| axe erişilebilirlik | Ana sayfa, teknoloji (1440/820/390/320 px), oyun ve matbaa üzerinde ihlal yok. |
| Gerçek MP3 oynatma (sentetik test sesi) | Oynatma süresi ilerledi, süre metadatası okundu. |
| JSON + dört MP3 bütünlüğü | Dosya/hash/süre/tam çözümleme; eksik, kısa, değişmiş ve yanlış bölüm engellendi. |
| Saat ve sayı | 07.30 öncesi kapalı; tamamlanınca otomatik açık; ertesi 06.00 açık sekme kapanır; yerel saat atlatmaz. |
| Tekrar çalıştırma | Aynı günlük sürüm/numara, model ve ses çağrılarını tekrarlamadan kullanılabiliyor. |
| İlk oyun sayısı | Başarısız ilk gün sayıyı tüketmiyor; ilk başarılı gün 001; başlangıç hazırlık manifestinde korunuyor. |
| İki depo arasındaki aktarım | Yerel Git deposunda atomik commit, aynı çıktıyla temiz ikinci eşitleme, bare remote'a push ve yeniden clone sonrası sürüm doğrulaması başarılı. |
| Actions YAML | Yeni iki workflow actionlint v1.7.7 ile başarılı; dağıtım composite ve bütün shell blokları ayrıca sözdizimi kontrolünden geçti. |
| Mevcut Gemini yöntemi | Mock sağlayıcı + gerçek FFmpeg ile başarılı WAV yolu ve iki özel ses ID'si doğrulandı; ses dışı yanıt reddedildi. Gerçek API çağrısı yapılmadı. |
| Eski akış uyumluluğu | Senaryo üreticisinin eski çağrı biçimi ve varsayılan Yeni Sekme prompt'u test edildi. Eski giriş noktaları, Notion workflow'ları, oynatıcılar ve yayımlanmış sesler korunuyor. |
| Public artifact / sırlar | Build yalnız web varlıklarını kopyalıyor; ham araştırma/senaryo/kaynak Python'ları dışarıda. Anahtar desenleri ve mevcut secret değerleri için engelleme test edildi. |
| Build tekrarı | Hazırlık build'i aynı komutla iki kez başarıyla çalıştı. |

Tarayıcı ekran görüntüleri `test-results/` altındadır; CI bu klasörü artifact
olarak yükler. Bunlar sentetik haber içeren tasarım/işlev testleridir, gerçek
haber yayını değildir.

## Gerçek entegrasyonlarda kalan doğrulamalar

- Bulut makinesinde `GEMINI_API_KEY` bağlı değil. Bu nedenle güncel Gemini model ve
  özel ses erişimi ile iki podcast üretimi canlı olarak doğrulanamadı.
- GitHub API ve NASA RSS denemeleri proxy'nin `CONNECT ... 403` cevabıyla
  durdu. GitHub Git HTTPS üzerinden iki depo okunabildi. Gerekli ağ alanları
  ortam taslağına, mevcut izinler korunarak kaydedildi; taslağın kaydı çalışan
  makineye uygulandığı anlamına gelmez.
- GitHub Secrets/Variables, GitHub App kurulumu, PR ve Pages API ayarları bu
  API engeli nedeniyle bu aşamada doğrulanamıyor.
- Gerçek RSS araştırması, ilk anahtarlı `dry_run`, yayın deposundaki Pages workflow
  sonucu, ana alan adı HTTP/ses kontrolleri ve bir sonraki gerçek sabah döngüsü
  tamamlanmadan sistem "tamamen canlı ve doğrulandı" sayılmaz.
- Yeni cron varsayılan olarak kapalı; canlı geçiş ve Notion kapatma onayı
  verilmediği için eski üretim korunuyor.

Hesapta yapılması gereken işlemler ve son onay sırası
[OPERATIONS.md](OPERATIONS.md) içinde adım adım açıklanmıştır.
