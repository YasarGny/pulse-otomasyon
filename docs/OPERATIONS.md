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

Her iki yayın, dört ses dosyası ve doğrulanmış bölüm bilgileri birlikte hazır
olmadan yayın açılmaz. Drive yedeği doğrulanmadan eski yayın temizlenmez.
Yalnız hazır site dosyaları yayın deposuna aktarılır. Başarılı ara aşamalar yeniden
kullanılır. Aynı gün yeniden çalıştırma yeni sayı oluşturmaz.
Git geçmişi yeniden yazılsa da GitHub eski PR commit bağlantılarını tutabilir; bunların kalıcı silinmesi için GitHub desteği gerekebilir.
Public depolardaki zamanlanmış işler 60 gün etkinlik olmazsa kapanabilir;
zamanlama ve yayın sağlığı izlenmelidir. Cron kesin saat garantisi değildir.
