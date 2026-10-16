# Doğrulama kaydı — 16 Ekim 2026

Bu kayıt yerel bulut makinesi ve PR üzerindeki gerçek GitHub Actions kalite
çalışmalarını kapsar. Canlıya geçiş veya Pages dağıtımı yapıldığı iddiası değildir.

| Kontrol | Sonuç |
|---|---|
| Python 3.12 / FFmpeg / ffprobe / bağımlılıklar | Hazır; pip check başarılı. |
| Python unittest | **45 geçti**, başarısız/atlanan test yok. |
| Node yayın kapısı testleri | **14 geçti**, başarısız/atlanan test yok. |
| Chromium işlevsel tarayıcı senaryoları | **19 geçti**. |
| axe erişilebilirlik | Ana sayfa, teknoloji (1440/820/390/320 px), oyun ve matbaa üzerinde ihlal yok. |
| Canlı Edge TTS | Sistem CA güveni ve mevcut HTTPS proxy ile Türkçe Emel ses listesi ve yeni bir kısa deneme MP3'ü üretildi; TLS doğrulaması açık kaldı. |
| Gerçek MP3 oynatma (sentetik test sesi) | Oynatma süresi ilerledi, süre metadatası okundu. |
| JSON + dört MP3 bütünlüğü | Dosya/hash/süre/tam çözümleme; eksik, kısa, değişmiş ve yanlış bölüm engellendi. |
| Saat ve sayı | 07.30 öncesi kapalı; tamamlanınca otomatik açık; ertesi 06.00 açık sekme kapanır; yerel saat atlatmaz. |
| Tekrar çalıştırma | Aynı günlük sürüm/numara, model ve ses çağrılarını tekrarlamadan kullanılabiliyor; artifact silinirse yayın deposundan geri alınır. Önceki gün yayımlanmış kaynak URL’leri tekrar seçilmez. |
| İlk oyun sayısı | Başarısız ilk gün sayıyı tüketmiyor; ilk başarılı gün 001; başlangıç hazırlık manifestinde korunuyor. |
| İki depo arasındaki aktarım | Yerel Git deposunda atomik commit, aynı çıktıyla temiz ikinci eşitleme, bare remote'a push ve yeniden clone sonrası sürüm doğrulaması başarılı. |
| GitHub Actions kalite koşuları | PR ve push koşuları başarılı: [PR CI](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38897975490), [push CI](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38897933764). |
| Runner kararlılığı | Yeni akışlar Ubuntu 24.04 üzerinde sabitlenir; duyurulan ubuntu-latest → 26 geçişine bağımlı değildir. |
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
- GitHub Git/PR/Actions okuma erişimi çalışıyor; [PR #1](https://github.com/YasarGny/pulse-otomasyon/pull/1) oluşturuldu ve gerçek CI geçti. Yedi RSS kaynağı uygun User-Agent ile HTTP 200 döndürdü ve her kaynaktan taze haber ayrıştırıldı.
- GitHub Secrets/Variables listeleme ve `pulse-production` environment oluşturma
  çağrıları `Resource not accessible by integration` (HTTP 403) döndü. Mevcut
  erişim bu yönetim işlemlerini yapamıyor; kullanıcı hesabından gerekli kurulum
  tamamlanmalı. Gereksiz yeni token veya anahtar oluşturulduğu varsayılmıyor.
- Hedef deponun Pages ayarı okundu: ana adres mevcut ve `build_type=legacy`.
  Canlı ayarı değiştirilmedi. GitHub Actions kaynaklı dağıtıma geçiş ancak son
  onaydan sonra yapılmalı.
- Canlı RSS toplama 40 teknoloji ve 24 oyun adayıyla tamamlandı. Bir RSS
  kaynağı geçici hata verdi; diğer kaynaklarla iki bölüm de yeterli haberi buldu.
- İlk anahtarlı `dry_run`, yayın deposundaki Pages workflow
  sonucu, ana alan adı HTTP/ses kontrolleri ve bir sonraki gerçek sabah döngüsü
  tamamlanmadan sistem "tamamen canlı ve doğrulandı" sayılmaz.
- Yeni cron varsayılan olarak kapalı; ayrıca `pulse/deployment.json` içindeki
  `live_enabled=false` kod kapısı eski hesap değişkenlerinden bağımsız koruma
  sağlıyor. Canlı geçiş ve Notion kapatma onayı
  verilmediği için eski üretim korunuyor.

Hesapta yapılması gereken işlemler ve son onay sırası
[OPERATIONS.md](OPERATIONS.md) içinde adım adım açıklanmıştır.
