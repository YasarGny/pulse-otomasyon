# Üretim ve maliyet incelemesi — 18.10.2026

## Canlı doğrulama

PR #35 birleştirildi. Website-only dağıtımı: Actions 39168654393 başarılı.
Yayın deposunun Pages işi 39168819835 başarılı. Aktif sürüm değişmedi:
`2026-10-18-ab5c40cea89406f9`; haber JSON'ları ve dört MP3 aynı kaldı.
Yayında yalnız bu release var. Dağıtım işi önce tam Drive ZIP geri okumasını,
sonra Pages HTML/varlık/JSON/MP3 hash doğrulamasını tamamladı.

Ek gerçek tarayıcı denemesi: 320/390/768/1440 pikselde ana sayfa, iki kategori ve
podcast sayfası; iki programda gerçek kayıttan konuya atlama ve gezinirken oynatma.
18 kontrol geçti, JavaScript çalışma hatası/yatay taşma görülmedi. Telefonun fiziksel
kilit ekranı davranışı masaüstü Chromium ile kesin doğrulanamaz; Media Session
entegrasyonu otomatik testte kontrol edilir. Tüm olası cihaz/senaryolar için
hatasızlık iddiası değildir.

## Düzeltilen maliyet ve tekrar riskleri

| Alan | Değişiklik | Sınır |
|---|---|---|
| İlk haber seçimi | Görsel URL'leri, tekrar eden URL ve tam gövde gönderilmez; alıntı 2200 karakterle sınırlanır. | Başlık/kaynak/tarih/ID korunur. Tam metin üretimi ve bağımsız denetim aynı tam kaynakları kullanır. |
| Ücretli TTS yanıtı | Dönüştürme başarısızsa alınmış ses baytları ve giriş/içerik hash'leri özel checkpoint'te korunur. | Aynı girdiyle tekrar yerel dönüştürme API'yi çağırmaz. Girdi/model/ses/strict modu değişirse eski yanıt kullanılmaz. |
| Bölüm işaretleri | Yalnız eksik program çözümlenir; kayıtlı döküm varsa Whisper modeli yüklenmez. | Bir programın çözümleme hatası diğerinin hazır dökümünün incelenmesini engellemez. |
| Kullanım görünürlüğü | `api-usage.jsonl` yalnız model, aşama, giriş karakteri ve sağlayıcının bildirdiği token sayaçlarını tutar. | Özel Actions checkpoint'inde; prompt, yanıt, API anahtarı siteye/Drive ZIP'ine yazılmaz. Sayaç yoksa tahmin uydurulmaz. |

Ses yöntemleri, Gemini özel sunucu kimlikleri ve Edge TTS sesi değiştirilmedi.
Mevcut kayıtlar yeniden üretilmedi. Yeni kod sonraki onaylı günlük üretimde kullanılır.
Bölüm işaretleri, canlı geçiş onayı sonrası günlük akışta varsayılan açık;
`PULSE_CHAPTERS_ENABLED=false` kapatır. Son kontrol penceresi ve 25 dakikalık
üst sınır korunur. Doğrulanamayan işaretler atlanır; ses yayını engellenmez.

## Korunan doğruluk kontrolleri

Günün Özeti yalnız haber brief alanlarını okur; why/yorum alanı okunmaz. PULSE→Pals
ortak telaffuz katmanı kullanılır. Bilinmeyen özel adların doğru okunacağı garanti
edilemez; günlük telaffuz raporu gözden geçirilerek sözlük geliştirilebilir.
Podcast taslak → sohbet düzenlemesi → bağımsız olgu/üslup denetiminden geçer;
en çok bir olgusal düzeltme/tekrar denetim vardır. Bu adımlar maliyet düşürmek için
kaldırılmadı. Model denetimi insan doğrulamasının yerini tutmaz.

## Kalan iyileştirme alanları

- Podcast senaryosunun ara taslak/edit aşamaları ayrı checkpoint değil. Son inceleme
  sırasında servis kesilirse sonraki deneme bazı metin çağrılarını tekrarlayabilir.
  Aşamaya ve kaynak/model/prompt hash'ine bağlı bir senaryo önbelleği sonraki adımdır.
- Ağ zaman aşımında sağlayıcının isteği işleyip işlemediği kesin bilinemeyebilir;
  sağlayıcı destekli idempotency olmadan mutlak tek ücret garantisi verilemez.
- 32768 çıktı token sınırı, her çağrıda bu miktarın tüketildiği anlamına gelmez.
  Uzun podcast veya doğruluk incelemesini körlemesine kısaltmak yerine yeni gerçek
  sayaçlar incelenmeli. Hesap faturasına erişim olmadan kesin günlük TL/$ verilemez.
- Aynı olay farklı URL'lerle yeniden yazıldığında kaynak parmak izi kesin semantik
  tekrar tespiti sağlamaz. Yakın günler için olay bazlı küçük bir ek kayıt ayrıca
  tasarlanabilir; gerçek güncellemeler yanlışlıkla elenmemelidir.
- Yayın ağacından eski dosyaları kaldırmak Git geçmişindeki MP3 nesnelerini küçültmez.
  Geçmişi yeniden yazmak ayrı ve ayrıca onay gerektiren bir taşımadır.

Ses kalitesi için yeni örnek üretim/dinleme ancak ayrıca açık onayla yapılır.

## Canlı kullanımda bildirilen arayüz düzeltmeleri

Mobil menüde yatay taşma ayarı, alt çizginin dikey taşmasını da bir kaydırma
alanına dönüştürüyordu. Menü artık kaydırma alanı değildir; küçük ekran/büyük yazıda
satıra yerleşir. 320–1440 px ve büyütülmüş yazıyla doğrulanır.
Yükleme mesajı oynatıcı akışına satır eklemiyordur: kısa beklemelerde gösterilmez,
350 ms üzerindeki beklemede düğmenin içinde sabit boyutlu gösterge ve ekran
okuyucu durumu kullanılır. Gerçek hata mesajı/tekrar dene kontrolü korunur.
Test yükleme öncesi/sırası/sonrasında panel, sekmeler, oynat düğmesi ve ilerleme
çubuğunun tüm dikdörtgenlerinin aynı kaldığını doğrular.
