# İşletim

Python 3.12, Node 22 ve FFmpeg/ffprobe gerekir. Testler sentetik veri kullanır;
gerçek ses veya içerik üretimi başlatmaz.

```sh
python -m pip install -r requirements.txt
npm ci
python tests/run_python.py
npm test
npx playwright install --with-deps chromium
npm run test:browser
```

## Yapılandırma

Repository Secrets: `GEMINI_API_KEY`, `PULSE_DEPLOY_APP_PRIVATE_KEY`,
`PULSE_DRIVE_CLIENT_ID`, `PULSE_DRIVE_CLIENT_SECRET`,
`PULSE_DRIVE_REFRESH_TOKEN`, `PULSE_STATE_KEY`.
Sonuncusu isteğe bağlıdır: verilmezse mevcut GitHub App özel anahtarından HKDF ile ayrı bir AES-256-GCM anahtarı türetilir. Ayrı anahtar kullanılırsa güvenli rastgele 32 baytın standart Base64 karşılığıdır.

Repository Variables: `PULSE_DEPLOY_APP_ID`, `PULSE_DRIVE_FOLDER_ID`,
`PULSE_DRIVE_ENABLED=true`. Mevcut `PULSE_LIVE_APPROVED` ve `PULSE_AUTOMATION_ENABLED` ayarları korunur. Yeni kurulumda yalnız doğrulama tamamlanınca etkinleştirilir.
Mevcut çalışan model değişkenleri değişmeden taşınır.
`PULSE_DRIVE_FOLDER_ID` isteğe bağlıdır; boşsa Drive kökündeki mevcut `PULSE`
klasörü bulunur. Salt okunur kontrol, eksik klasör oluşturmaz ve aynı isimli
birden fazla kayıt varsa belirsiz hedefi kabul etmez.

Önce `Check configuration without generating content` ve kalite kontrolleri
çalıştırılır. Bu kontrol üretim yapmaz; yayın deposu ve Drive klasörünü yalnız okur.
Eski üretim deposunun zamanlaması kapatılmadan yenisi etkinleştirilmez.
Manuel ses üretimi ayrıca kullanıcı onayı gerektirir.

## Ara kayıtlar

Üretim ve bölüm ara kayıtları AES-256-GCM ile şifrelenir. Geçerli anahtar yoksa
üretim başlamaz; public iş akışları şifresiz kayıtları geri yüklemez.
Anahtar değiştirilirken tamamlanmamış işler varsa önce tamamlanmaları beklenir.
Şifreli dosya ve kullanım sayaçları gizli içerik veya kesin fatura ölçümü değildir.
Standart bağımlılık/model cache alanlarına kaynak kanıtları, taslaklar ve kimlik
bilgileri eklenmez. Kalite kontrolünün ekran görüntüleri yalnız sentetik veri içerir.
Günlükler herkese açıktır; gizli değerler veya tam kaynak metinleri yazdırılmaz.

## Üç çalışma anahtarı

Repository **Variables** alanında üç bağımsız anahtar vardır. Boş veya tanımsız
olanlar mevcut yayını korumak için `true` kabul edilir; kapatmak için tam olarak
`false`, açmak için `true` kullanılır.

- `PULSE_AUTOMATION_ENABLED`: ana anahtar. Kapalıyken tüm üretim, yayın, bölüm
  kurtarma, yedekleme ve tanı iş akışları manuel başlatılsa da çalışmaz. Kontrol
  işi çalışan işleri iptal etmeyi dener; site tüm HTML sayfalarında ara ekranına
  geçer. Haberler, sesler ve yeniden açılacak sayfalar silinmez.
- `PULSE_TECH_PODCAST_ENABLED`: Yeni Sekme'nin senaryo, editör, inceleme, ses,
  döküm ve bölüm üretimi. Kapalıysa teknoloji haberleri ve Günün Özeti devam eder.
- `PULSE_GAME_PODCAST_ENABLED`: aynı kontrol Moradon FM için geçerlidir.

Kapalı bir podcast açıkça `podcast_enabled=false, podcast=null` olarak mühürlenir;
bozuk veya yanlışlıkla eksik podcast bu istisnadan yararlanamaz. Site oynatıcıları
ve Drive'ın taşınabilir günlük ZIP'i yalnız o gün gerçekten mevcut sesleri kullanır.
İki podcast kapalıyken de haberler ve iki özetle tam bir yayın yapılabilir.
`PULSE_CHAPTERS_ENABLED` artık kullanılmaz. `PULSE_LIVE_APPROVED` ayrı canlı yayın
iznidir; çalışma anahtarı değildir ve mevcut değeri korunur.

**Apply owner pause and podcast controls** işi 10 dakikada bir değişkenleri okuyup
siteye taşır; GitHub cron gecikebilir. Hemen uygulamak için Actions sayfasından bu
iş akışında **Run workflow** seçilir. Bu iş içerik/ses üretmez, Google/AI çağrısı
ve token tüketimi yapmaz. Ana anahtar kapalıyken yalnız bu küçük kontrol işi
(yeniden açılmayı uygulamak için) ve geliştirme kalite testleri çalışabilir.
Değişken kaydı anlık bildirim değildir. Açık tarayıcılar yayınlanan kontrolü
30 saniyede bir ve yeniden odaklanınca alır; mevcut dinleme durur. Dış servise
önceden gönderilmiş istek geri alınamaz. Podcast kapatılırken aktif üretim işi
iptal edilirse başarılı şifreli ara kayıtlar sonraki zamanlanmış denemede kullanılır.
Tekrar açma yeni ses üretimi başlatmaz; korunmuş site sayfaları açılır ve günlük
üretim mevcut takviminde devam eder. Eski tarih güncel yayın gibi gösterilmez.

## Podcast sohbet denetimi

25.10.2026 ve sonrası için yazım, editör ve bağımsız inceleme aynı üç rutin
çağrıda kalır. İnceleme, kapsanan gerçek haberleri ve gerekçeli yorum/yanıtların
replik indekslerini kaynaklarla karşılaştırır. 15–20 dakika editoryal hedeftir;
120–160 kelime/dakika yalnız geniş bir planlama tahminidir. 1800 kelimenin altında
kaynaklara özgü kısa bölüm gerekçesi gerekir; zorunlu alt süre veya kelime kotası
yoktur. Yetersiz sohbet mevcut tek düzeltme ve yeniden inceleme döngüsüne gider;
yalnız inceleme raporunun biçimi hatalıysa aynı hak yalnız rapor kontrolüne ayrılır,
doğru diyalog yeniden yazılmaz. Bu hak ek bir denetim döngüsü oluşturmaz.
Onay ve replik referansları son metin/kaynak kimliklerine bağlanır; değiştirilmiş
onay ses üretimine geçemez. Eski mühürlenmiş yayınlar yeniden üretilmez.
İnceleme raporu ve planlama ölçümleri yalnız şifreli ara kayıtlarda kalır.

## Yayın

Her iki yayının haberleri ve özetleri ile yalnız açık podcastlerin sesleri ve
doğrulanmış bölüm bilgileri birlikte hazır olmadan yayın açılmaz. Drive yedeği doğrulanmadan eski yayın temizlenmez.
Podcast bölüm denetimi artık ham ASR parçalarını tam cümle varsaymaz. Mevcut
dökümler cümle sonuna kadar birleştirilir; yeni dökümlerde saklanan gerçek kelime
zamanları varsa bir satırdaki ayrı cümleler de ayrılabilir. Eksik bölüm için eski
dökümde kelime zamanları saklanmamışsa yalnız o programın mevcut sesi bir kez
yeniden yazıya dökülür; ses yeniden üretilmez. Zaman uydurulmaz;
eksik veya hatalı kelime hizalamasında ham ölçülmüş aralık korunur. Yarım kalan
cümle haber kesitinin sonu olamaz. Karışık konu içeren aralıklar tek habere
atanmaz; bağımsız inceleme ve mevcut tek düzeltme hakkı korunur. Onaylı diğer
programın bölüm bilgileri ve sesler yeniden üretilmez.
Başarısız günlük üretimden sonra yalnız mühürlenmiş, bugüne ait hazır ses kaydı
varsa `publish-ready` bölümleri tamamlayıp aynı yayını doğrular ve yayımlar.
Eksik içerik/ses üretmez; mühürlenmemiş ara kaydı hazır saymaz. Bölüm kurtarma
işlerinin kuyruk kilidi iş koşulu değerlendirildikten sonra alınır: atlanan
`workflow_run` olayları bekleyen günlük üretimi kuyruktan düşüremez.
Taşınabilir ZIP için orijinal haber görselleri tek URL başına bir kez alınır;
indirme sınırı görsel başına 64 MB'dır. Haber keşfinin 8 MB ve HTML'in 2 MB
sınırları değişmez. Görseller küçültülmeden mevcut biçim doğrulamasından geçer;
yalnız arşivde 100 milyon piksele kadar panoramalar doğrulanabilir. Keşfin
40 milyon piksel sınırı, 30 saniyelik çözümleme sınırı ve seri işleme korunur;
çözücü iki iş parçacığıyla çalışır. Sınırı aşan dosya yedeği
eksikmiş gibi başarılı gösterilmez; hata bölüm ve güvenli görsel özetiyle bildirilir.
Yalnız hazır site dosyaları yayın deposuna aktarılır. Başarılı ara aşamalar yeniden
kullanılır. Aynı gün yeniden çalıştırma yeni sayı oluşturmaz.
Git geçmişi yeniden yazılsa da GitHub eski PR commit bağlantılarını tutabilir; bunların kalıcı silinmesi için GitHub desteği gerekebilir.
Public depolardaki zamanlanmış işler 60 gün etkinlik olmazsa kapanabilir;
zamanlama ve yayın sağlığı izlenmelidir. Cron kesin saat garantisi değildir.
