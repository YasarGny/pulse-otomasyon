# PULSE işletim ve güvenli geçiş rehberi

Kullanıcı 16 Ekim 2026'da canlı geçişi ve ardından eski Notion sisteminin
temizlenmesini açıkça onayladı. `live_enabled` kod kapısı açıktır; canlı işler ayrıca
`PULSE_LIVE_APPROVED=true` gerektirir. Günlük cron varsayılan olarak açıktır;
`PULSE_AUTOMATION_ENABLED=false` ile durdurulur. Manuel işler varsayılan olarak
denemedir. Aşağıdaki kurulum ve geçiş adımları yeni kurulum/geri alma referansıdır.

## Tek kaynak, iki depo

- `YasarGny/pulse-otomasyon`: `site/` tek web kaynağı; `pulse/` araştırma, içerik,
  özet, doğrulama ve paketleme; `.github/workflows/daily-publish.yml` orkestrasyon.
- `YasarGny/YasarGny.github.io`: sadece `pulse.build` çıktısı; HTML/CSS/JS, JSON,
  kapaklar, dört MP3. Var olan `.github/workflows/pages.yml` dağıtım altyapısı
  korunur. Bu depoda site kaynakları elle geliştirilmez.
- Üretim dosyaları `releases/YYYY-MM-DD-<içerik-parmakizi>/` altında değişmezdir.
  `data/publication.json` iki yayını birden gösteren tek atomik giriş noktasıdır.
  Kaynak, ham RSS alıntıları, konuşma taslakları ve anahtarlar siteye kopyalanmaz.
- Kaynaksız eski pilot JSON dosyaları ve Notion üretim betikleri kaldırılmıştır.

## Geliştirme ve test

Python 3.12, Node 22+ ve FFmpeg/ffprobe gerekir. Bulut ortamı zaten yalıtılmıştır;
mevcut checkout'u kullanın, açıkça istenmedikçe Git worktree oluşturmayın.

```bash
cd /workspace/pulse-otomasyon
python3 -m venv /workspace/.venvs/pulse-otomasyon
. /workspace/.venvs/pulse-otomasyon/bin/activate
python -m pip install -r requirements.txt
npm ci
python -m unittest discover -s tests -p 'test_*.py' -v
npm test
# Sistem Chromium'u yoksa:
npx playwright install --with-deps chromium
npm run test:browser
```

Tarayıcı testleri sentetik haber ve sentetik ses içeren geçici bir site oluşturur;
üretim içeriği değildir. Masaüstü/tablet/mobil ekran görüntüleri `test-results/`
altındadır. Erişilebilirlik axe ile kontrol edilir. Sistem Chromium'u otomatik
bulunur; `PULSE_CHROMIUM` ve `PULSE_PYTHON` ile yollar değiştirilebilir.

Statik kaynakları yerel olarak sunmak için:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

Gerçek tamamlanmış yayın manifesti olmadığında matbaa ekranı görünmesi beklenir.
Tarayıcı testlerinin fixture sunucusu gerçek içerik üretmeden tasarım incelemek
ve bütün oyuncuları sınamak içindir: `python tests/serve_fixture.py`.

## Günlük akış ve saatler

GitHub cron UTC kullanır; İstanbul yıl boyunca UTC+3'tür. Ana tetik 03.00 UTC
(06.00 TRT). Yedek tetikler 06.20, 07.30, 08.00 TRT'dir. İşler aynı concurrency
grubundadır; çalışan iş iptal edilmez. GitHub tek bekleyen çalışma tutabilir ve
yeni bir yedek tetik önceki bekleyenin yerini alabilir. Cron bir zaman garantisi değildir.

| Hedef (TRT) | Yapılan işlem |
|---|---|
| 06.00 | Matbaa: önceki yayın bir sonraki günün yayını olamaz; hazırlık manifesti dağıtılır. |
| 06.15 | Güvenilir yayıncıların tarihli RSS/Atom kaynakları toplanır. |
| 06.30 | Bölüme özel Türkçe haber seçkisi, önem açıklamaları, gerçek kaynak URL'leri hazırlanır. |
| 06.45 | Her iki özet Edge TTS ile, her iki podcast mevcut Gemini yöntemiyle üretilir. |
| 07.15 | JSON, tarih/sayı, kaynaklar, hash, dosya boyutu ve dört MP3'ün tamamı doğrulanır. |
| 07.30 | İki yayın birlikte hazırsa atomik commit ile yayın deposuna aktarılır. |

Gecikmiş tetikleyici geçmiş bekleme noktalarını atlar, aynı işleri tamamlar;
bozuk veya eksik içerikle saati yakalamaya çalışmaz. Geceyi aşan bir iş eski
sayısını yeni günün yayını olarak yayımlayamaz. API başarısızlıklarında iş kırmızı
olur, matbaa açık kalır. Actions bildirimlerini açın: GitHub bildirim ayarları →
Actions → başarısız iş akışları.

Yayın deposundaki tarihli JSON geçmişi, önceki gün yayımlanmış kaynak URL'lerini
yeni seçkiden çıkarır. Yeterli yeni haber kalmazsa eski haber yeniden yayımlanmaz.
Aynı günün sürümü yayın deposunda zaten mevcutsa, Actions artifact'ları silinmiş
olsa bile doğrulanmış sürüm oradan geri alınır; yeniden API ücreti oluşturulmaz.

İşin başarılı ara çıktıları, başarısız sonucun ardından da 2 günlük Actions
artifact'ına yazılır. Yalnız bu depodaki bu iş akışının `main` üzerindeki güvenilir
`schedule`/`workflow_dispatch` çalışmaları geri yüklenir; PR çıktıları kullanılmaz.
Yeniden çalıştırma aynı günlük JSON'u, konuşma metnini ve geçerli sesleri kullanır.
Tamamlanmış bir sürüm yeniden numaralandırılmaz veya tekrar seslendirilmez.
Artifact silinirse henüz yayımlanmamış, tamamlanmamış günün bazı ücretli üretimleri yeniden gerekebilir;
2 günlük artifact geçmişi uzun vadeli arşiv değildir. Yayımlanmış sürümler yayın
deposunda kalır. Araştırma başarısız olursa diğer günün haberleriyle doldurulmaz.

Teknoloji sayısı 16 Ekim 2026 = 001 takvim başlangıcına bağlıdır. Oyun başlangıcı
ilk başarılı yayın gününde kaydedilir; o gün = 001. İlk deneme başarısızsa ertesi
günün ilk başarılı yayını yine 001 olur. Sonraki günlerde bu başlangıç, hazırlık
manifestlerinde de korunur. Başarısız günler takvim sıra numarasında boşluk
bırakabilir; aynı gün yeniden çalıştırmak sayıyı artırmaz.

## İçerik ve ses

Kaynaklar `pulse/feeds.json` içindedir. Model URL, görsel ve tarih yazamaz; yalnız
RSS'te bulunan ID'leri seçer ve özetler. Haberlerin zaman aralığı yayın saatinden
önceki 40 saat ile en fazla iki saat sonrasıdır; RSS'te geleceğe tarih atılmış bir
kayıt araştırma zamanı doğrulamasından ayrıca geçmelidir. En az üç kaynaklı ve
farklı haber gerekir. Her bölüm ayrı araştırılır. Otomobil kotası yoktur.

RSS bazen yalnız kısa alıntı veya görselsiz veri verir. Kaynak desteği olmayan
iddia eklenmemesi modele açıkça söylenir; bu, insan editoryal denetiminin veya
olgusal doğruluk garantisinin yerini tutmaz. İlk canlı denemede haberleri
kaynaklarıyla karşılaştırın. Gerçek RSS görselleri varsa gösterilir; yüklenemezse
haber metni ve kaynak bağlantısı kalır. Lisans/kullanım hakkı ve görsel erişimi
kaynak yayıncıya bağlıdır; görsel uydurulmaz, zorunlu tutulmaz.

Özet her haberin kısa, yorumsuz `brief` alanını okur; başlık, tam haber ve `why`
alanını okumaz. Eski JSON'da `brief` yoksa ilk olgusal özet cümlesi kullanılır.
Edge TTS `tr-TR-EmelNeural`, mevcut telaffuz kuralları ve doğrulanmış sentez yöntemi
korunur. TLS doğrulaması açık kalır.

Podcast bir haber listesini sırayla okumaz: Yaşar ana sunucu olarak iki-üç anlamlı
soru etrafında Necdet'le sohbeti yürütür. Zorunlu düzenleme ve bağımsız kaynak/üslup
denetimi vardır; olumsuz inceleme bir kez düzeltilip yeniden denetlenir, hâlâ
onaysızsa yayın engellenir. Otomatik model denetimi hatasızlık garantisi değildir;
kaynak dışı kesin iddia ve yanıltıcı yorumları azaltan bir yayın kapısıdır. Ham RSS
alıntıları mevcutsa denetçiye verilir; eski yayını yenilerken doğrulanmış haber
notları kullanılır. İnceleme kaydı ve son diyalog SHA-256 ile bağlanır; bu özel
ara kayıtlar web sitesine kopyalanmaz. Gemini Interactions sentezi ve özel sesler
`voice_glt4mz1jtaeh` / `voice_8nqcoox86z5q` değiştirilmez.

Manuel günlük workflow'da `refresh_audio=true` yalnız bugünün tamamlanmış
yayınının seslerini yeniler. `dry_run=true` önce deneme yapar. Tarih, sayılar ve
haberler korunur; yeni sesler yeni bir immutable release oluşturur. Dört sesin
tamamı hazır olmadan aktif manifest değişmez. Revize kayıt normal çalışma alanına
da aktarılır; sonraki normal tekrar eski sese dönemez.

Model varsayılanları mevcut üretimden alınmıştır: `gemini-3.8-flash` ve
`gemini-3.8-flash-tts`. Bunların bu hesabın API erişiminde çalıştığı, anahtar
sağlanmadan doğrulanamaz. API biçimi/özel ses erişimi başarısız olursa iş durur;
başka model veya ses yöntemi sessizce kullanılmaz. Model değişikliği gerekiyorsa
önce ayrı bir denemede doğrulayın. Repo Variables ile `PULSE_SCRIPT_MODEL` ve
`PULSE_TTS_MODEL` ayarlanabilir.

## Yayın kapısı: güvence ve sınırlar

Sunucu tarafında çalışan üretim/dağıtım işi iki yayını birlikte doğrular. MP3 için
ffprobe yeterli sayılmaz: FFmpeg `-xerror` ile bütün dosya çözülür; en az 20/40 sn,
25 KB ve kaydedilen SHA-256/boyut/süre eşleşmesi gerekir. Manifest yalnız bu
doğrulamanın ardından oluşur. Dört ses ve iki JSON aynı Git commit'inde değişir.
Push sonrasında iş ayrıca 15 dakikaya kadar gerçek Pages HTTP yanıtını bekler;
manifesti, üç sayfayı, iki JSON hash'ini ve dört MP3'ün indirilen gerçek baytlarının
SHA-256'sını kontrol eder. Commit'in başarılı olması dağıtım başarısı sayılmaz.
Pages build başarısız olursa eski dağıtım kalır; istemci yine eski tarihi yeni gün
olarak açmaz.

Tarayıcı kendi saatini kullanmaz; aynı origin'deki manifest yanıtının HTTP `Date`
ve varsa `Age` başlıklarıyla saat kurar. Manifestin tarihi, 07.30 alt sınırı,
iki JSON'un SHA-256'sı, tarih/sayı kimlikleri ve dört sesin HEAD erişimi/boyutu
doğrulanır. Saat yalnız hazır olduğu için değil, **hem 07.30 geçtiği hem yayın
hazır olduğu için** açılır. Açık sekmeler sunucu zamanı + monotonic süreyle
ertesi 06.00'da kapanır; her dakika yeni manifest aranır. İki dakika boyunca
başarılı doğrulama yapılamazsa görünüm güvenli biçimde kapanır. Gizli sekme yeniden
aktif olduğunda ayrıca kontrol edilir. Yerel saat değiştirmek açılışı atlatmaz.

GitHub Pages statik barındırmadır: matbaa ekranı bir erişim yetkisi sistemi değildir.
Önceden bilinen arşiv/MP3 URL'lerini sunucudan saatle engellemez ve HTTP 503 üretmez.
Manifest güveni aynı origin/depo ve Actions doğrulamasından gelir; depo ele
geçirilmesine karşı kriptografik imza iddiası yoktur. Kesin saatli HTTP engelleme
ve cron garantisi için ayrı sunucu/edge zamanlayıcı gerekir. Bu proje böyle bir
bağımlılık eklemeden, yeni günlük yayını eksik açmayı engeller.

## Hesaba özel kurulum: sırayla yapılacaklar

### 1. Gemini anahtarı

1. [Google AI Studio anahtarları](https://aistudio.google.com/apikey) sayfasını açın.
2. `Create API key` ile bu projeye uygun bir anahtar oluşturun; ücret/kota ve
   mevcut özel ses kimliklerine erişiminizi kontrol edin.
3. [pulse-otomasyon → Settings → Secrets and variables → Actions](https://github.com/YasarGny/pulse-otomasyon/settings/secrets/actions)
   sayfasında `New repository secret` seçin.
4. Adı `GEMINI_API_KEY`, değeri anahtar olsun. Zaten mevcut ve çalışıyorsa yeniden
   oluşturmayın. Anahtarı sohbete, dosyaya veya commit'e yazmayın.

Bulut makinesinde canlı deneme yapılacaksa aynı adın bulut ortamı ayarlarındaki
mevcut secret bağını da güvenli değer alanından tamamlayın. GitHub Secrets ile
bulut ortamı secret'ları ayrı yerlerdir; biri diğerini otomatik doldurmaz.

### 2. Yayın deposuna en az yetkili GitHub App

İki depo arasındaki `GITHUB_TOKEN` yazma yetkisi yeterli değildir. Tercih edilen
mekanizma, yalnız yayın deposuna kurulan kısa ömürlü token üreten GitHub App'tir.

1. [GitHub → Settings → Developer settings → GitHub Apps → New GitHub App](https://github.com/settings/apps/new)
   sayfasını açın. Benzersiz bir ad (örn. `PULSE Yasar Publisher`) girin.
2. Homepage URL: `https://github.com/YasarGny/pulse-otomasyon`. Webhook kullanımı
   gerekmiyor; `Active` işaretini kaldırın.
3. Repository permissions → **Contents: Read and write** seçin. Metadata salt
   okunur gelir; başka yetki gerekmez. `Only on this account` seçip oluşturun.
4. General sayfasındaki **App ID** değerini not edin. Sayfanın altında
   `Generate a private key` seçin; `.pem` dosyası indirilir.
5. Sol menü `Install App` → hesabınız → `Only select repositories` → yalnız
   `YasarGny.github.io` → `Install`.
6. [pulse-otomasyon Actions Variables](https://github.com/YasarGny/pulse-otomasyon/settings/variables/actions)
   → `New repository variable`: `PULSE_DEPLOY_APP_ID` = App ID.
7. [Actions Secrets](https://github.com/YasarGny/pulse-otomasyon/settings/secrets/actions)
   → `New repository secret`: `PULSE_DEPLOY_APP_PRIVATE_KEY` = indirilen PEM'in
   tamamı. PEM'i bu sohbete, kaynak koduna veya artifact'a koymayın.

App token'ı yalnız dağıtım işinde ve yalnız hedef depo için üretilir; iş bitiminde
iptal edilir. Haber/AI adımlarına verilmez. Token ile push, mevcut hedef Pages
workflow'unu tetikler. Hedef dal koruması bot push'unu engelliyorsa hesabınıza ait
Rulesets/branch protection ayarında yalnız bu App için uygun bypass veya izin
sağlanmalıdır; genel korumaları kaldırmayın.

### 3. Production koruması ve Pages

1. [Kaynak depo Environments](https://github.com/YasarGny/pulse-otomasyon/settings/environments)
   → `New environment` → `pulse-production` oluşturun.
2. Mümkünse başlangıçta `Required reviewers` olarak kendi hesabınızı ekleyin;
   planınız bunu desteklemiyorsa canlı değişkeni kapalı tutmak son onay kapısıdır.
3. Mevcut hedef ayarı `legacy` olarak okundu; aşağıdaki Source değişikliği canlı
   dağıtım ayarıdır ve **son onaydan sonra** uygulanır.
   [Yayın deposu Pages ayarları](https://github.com/YasarGny/YasarGny.github.io/settings/pages)
   → Build and deployment → Source: **GitHub Actions** seçin. Hedef depoda mevcut
   `Publish PULSE website` workflow'u korunur. Bu değişiklik tek başına yeni site
   dosyalarını göndermemelidir; bu görevde canlı dağıtım tetiklenmemiştir.
4. [Yayın deposu Actions](https://github.com/YasarGny/YasarGny.github.io/actions)
   altında mevcut Pages workflow'unun etkin olduğunu kontrol edin. GitHub Actions
   kapalıysa Settings → Actions → General üzerinden gerekli resmi `actions/*`
   iş akışlarına izin verin.

### 4. Canlıya dokunmadan ilk uçtan uca deneme

1. PR birleştirildikten sonra [kaynak Actions](https://github.com/YasarGny/pulse-otomasyon/actions)
   → **PULSE GitHub daily publication** → `Run workflow` → Branch `main`.
2. **dry_run işaretli kalsın.** `Run workflow` seçin.
3. İşin gerçekten iki ayrı haber seçkisini, iki özeti ve iki podcast'i ürettiğini
   doğrulayın. 07.30 öncesi başlatılırsa hedef saatlere kadar bekler.
4. `pulse-site-...` artifact'ını indirin; JSON kaynaklarını ve dört ses dosyasını
   kontrol edin. `pulse-state-...` yayın değil, yeniden başlatma kontrol noktasıdır.
5. İlk denemenin seslerini dinleyin; özellikle Gemini özel erkek seslerini ve
   Moradon FM üslubunu doğrulayın. İki yeni canlı API çağrısı bu ortamda anahtar
   olmadan doğrulanmış sayılmaz.

### 5. Son onaydan sonra canlı geçiş

Bu bölüm **kullanıcı son onayı olmadan uygulanmaz**.

1. Kullanıcının canlıya geçiş onayını alın; eski sistem hâlâ çalışır.
2. Son onaydan sonra asistan `pulse/deployment.json` içindeki `live_enabled`
   değerini ayrı, incelenebilir bir commit ile `true` yapar. Ardından Actions
   Variables → `PULSE_LIVE_APPROVED` = `true` eklenir.
3. Manuel workflow'da `dry_run` işaretini kaldırıp çalıştırın; production environment
   bekliyorsa `Review deployments` → `Approve and deploy` seçin.
4. [Ana site](https://yasargny.github.io/) ve `/teknoloji/`, `/oyun/` üzerinde
   tarih, sayı, dört gerçek ses, mobil ve kaynak bağlantılarını doğrulayın.
   Pages workflow'unun tamamlanmasını ve manifestin yeni sürüm olduğunu kontrol edin.
5. Zamanlama varsayılan açıktır; durdurmak için `PULSE_AUTOMATION_ENABLED=false` kullanın. Production environment'ın her gün
   insan onayı istememesi için yalnız doğrulama sonrası gerekli reviewer kuralını
   kaldırın; dal kısıtını `main` ile sınırlı tutabilirsiniz.
6. Sonraki gün 06.00 kapanışı ve yeni iki yayının birlikte açılışını da izleyin.

`PULSE_AUTOMATION_ENABLED=false` ise cron hiçbir şey yapmaz; değişken yoksa zamanlama açıktır.
`PULSE_LIVE_APPROVED` eksik/false veya kodda `live_enabled` false ise yeni
workflow hiçbir canlı dosyayı değiştirmez.
Günlük üretim yine ücretli API kullanabilir: yalnız denemeye hazırken manuel başlatın.

### 6. Eski sistem ve depo görünürlüğü

Notion üreticileri, eski workflow dosyaları, kök yönlendirme, `web-player/` ve
eski MP3/JSON dosyaları kaldırıldı. Aktif site yalnız `site/` çıktısına ve
`releases/` arşivine bağlıdır. Eski Notion workflow'larına ait iki Actions kaydı
da temizlendi; günlük yayın/checkpoint ve kalite kayıtları silinmez.

Kaynak depo inceleme sırasında zaten private idi; hedef yayın deposu public idi.
Eski `/pulse-otomasyon/` URL'si HTTP 404 döndü. Kaynak Pages yönetim API'si
403, yönetilen `pages-build-deployment` workflow kapatma API'si 422 döndü. Bu
workflow GitHub tarafından yönetilir; bir YAML dosyası değildir. Kaynak depo
Settings → Pages ekranında hâlâ bir site görünüyorsa `Unpublish site` / `Delete
site` ile hesap sahibi kapatabilir. Bu işlem hedef deponun Pages yayınına yapılmaz.

GitHub Free private depodan Pages yayını desteklemez; uygun ücretli plan gerekir.
Plan bilgisi mevcut bağlantıdan okunamadı. Çalışan hedef deponun görünürlüğü bu
nedenle değiştirilmedi. Kaynak private kalabilir; Actions kotası ve artifact
erişimi hesap planına tabidir. Private kaynak ile public hedef arasında yalnız
public dosya allowlist'i aktarılır.

## Geri alma

Yeni otomasyonu durdurmak için `PULSE_AUTOMATION_ENABLED=false` ve
`PULSE_LIVE_APPROVED=false` yapın. Hedef deponun son site commit'ini GitHub'da
revert etmek önceki atomik dağıtımı geri getirir. Notion üreticisi kaldırılmıştır; geri alma GitHub tabanlı sürümler üzerinden yapılır. Güncel tarihli eksiksiz manifest yoksa matbaa ekranının
kalması beklenen güvenli davranıştır; eski haberi bugünkü diye etiketlemeyin.

## Mevcut dosyaların durumu

| Dosya/akış | Karar |
|---|---|
| `pulse_audio.py`, `pulse_publish.py`, `sync_player_embed.py` | Yeni hatta bağımlılığı olmadığı doğrulandı; kaldırıldı. |
| `.github/workflows/pulse-audio.yml`, `sync-player-embed.yml` | Notion tabanlı eski üretim; kaldırıldı. |
| `pulse_podcast_audio.py` | Yeni ve eski sistemin ortak ses motoru; başarılı API/yöntem ve kimlikler korundu; hata loglarında yanıt gövdesi çıkarıldı; eski üreticinin varsayılan yanıt uyumluluğu korundu. Yeni hat `strict_audio=True` ile ses dışı API verisini reddeder; iki yol ayrı testlerle doğrulandı. |
| `pulse_podcast_writer.py` | Eski çağrı biçimi korundu; bölüm/tarih/sayı için isteğe bağlı argümanlar eklendi. |
| `site/data/teknoloji.json`, `site/data/oyun.json` | Doğrulanmamış pilot; kaldırıldı. |
| `web-player/` | Kullanım dışı eski oynatıcı, ses ve metadatalar kaldırıldı. |
| `site/` | Tek yeni web kaynağı; yayın deposuna elle çatallanmaz. |

## Bulut ortamının ağ erişimi

Yerel canlı deneme ve GitHub yönetimi için `api.github.com`,
`generativelanguage.googleapis.com`, `speech.platform.bing.com` ve
`pulse/feeds.json` içindeki RSS hostları gerekir. Ağ izinleri bulut ortamı
taslağına mevcut izinler korunarak eklenmiştir. Taslak kaydı çalışma makinesine
uygulama veya yayınlama değildir. `CONNECT tunnel failed, response 403` ağ
engeline işaret eder; bunu sırf `gh auth status` token değişkenini tanımadı diye
yeni bir GitHub token'ı isteyerek çözmeye çalışmayın. Mevcut platform Git proxy
kimlik doğrulamasıyla Git read/push ayrıca sınanmalıdır.

## Private depo çıktı bütçesi

Geçici site ve yeniden başlatma artifact'ları 2, tarayıcı sonuçları 3 gün saklanır.
Kalıcı hazır yayınlar public yayın deposundaki `releases/` altında korunur;
artifact'ın silinmesi arşivi veya aynı günün dayanıklı geri dönüşünü silmez.
İlk temizlikte son beş tarayıcı kanıtı korundu, daha eski ekran görüntüsü
artifact'ları kaldırıldı; job/test geçmişi silinmedi. Kaynak private olduğundan
planın Actions dakika ve depolama kotası geçerlidir.

Geçiş revizyonu, teknolojiye yanlış konmuş açık oyun kategorili haberleri ayıklar;
tarih ve sayı korunur. Yeni `content_revision=2` yayınları bu ayrımı doğrular.

## Haberleri değiştirmeden web tasarımını yayımlama

Onaylı ve test edilmiş `main` için **Publish reviewed website without regenerating
content** (`refresh-website.yml`) elle çalıştırılabilir. Günlük işlerle aynı concurrency
grubunu ve `pulse-production` ortamını kullanır. Canlı onayı ve Drive etkinliği
zorunludur. Mevcut manifest, tarih, sayı, JSON ve dört MP3 değiştirilmez.

Akış mevcut eksiksiz yayını doğrular, tek kaynak `site/` ile yeniden derler, aktif
günün ZIP’ini yeni tasarımla Drive’a yükleyip tamamen geri okuyarak doğrular.
Yalnız bundan sonra eski günlük ZIP emekliye ayrılır; gün başına tek son sürüm
politikası korunur. Normal günlük işler değişmeyen arşivi yeniden yüklemez.

Atomik yayın commit’inden sonra Pages üzerindeki HTML, JSON, dört MP3 ve ayrıca
uygulama/tasarım varlıklarının hash’leri denetlenir. Tarihi geçmiş veya hazırlık
halindeki yayınla bu akış çalışmaz; yeni eksiksiz günlük sayıyı beklemek gerekir.
Uygulama ekleme desteği yeni Secrets veya ek GitHub izni gerektirmez.
