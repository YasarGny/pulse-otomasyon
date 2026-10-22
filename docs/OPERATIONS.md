# PULSE işletim ve güvenli geçiş rehberi

## Manuel ses üretimi için onay

Arayüz düzeltmesi veya dağıtım onayı, yeniden ses üretimi onayı değildir.
Manuel gerçek ses üretimi, `refresh_audio`, `expanded_issue` veya günlük üretim
işini elle başlatmadan önce kullanıcıdan açık onay alınır. Arayüz değişiklikleri
`refresh-website.yml` ile mevcut dört ses dosyasını koruyarak yayımlanır.
Mevcut onaylı günlük otomasyon bu manuel müdahalelerden ayrıdır.
PULSE seslendirmesi **Pals** olmalıdır; özet ve podcast ortak telaffuz kopyasını
kullanır, özgün haber ve onaylı konuşma metinlerindeki adlar değiştirilmez.

### Üretim öncesi telaffuz kontrol listesi

Her yayının özel `pronunciation-review.json` dosyasında özet ve podcast için
sözlük dönüşümleri, kullanım sayıları ve tanınmayan özel ad adayları bulunur.
Rapor her seslendirmeden **önce** yazılır. Otomatik adaylar kesin yabancı ad tespiti
veya telaffuz onayı değildir; bilinmeyenler otomatik değiştirilmez. Günlük işin
Actions özetinde adaylar gösterilir, bağlamları özel `pulse-state` artifact'ında
kalır. Raporlar halka açık siteye veya Drive yayın ZIP'ine aktarılmaz.
İncelenen adların doğru biçimleri `pulse/pronunciations.json` içine eklenebilir;
mevcut sesleri değiştirmek ayrıca onay gerektirir. Rapor üretimi ekstra API veya
ses üretimi çağrısı yapmaz ve günlük zamanlamayı durdurmaz.

Yerel bir konuşma metnini ücretsiz ve çevrimdışı kontrol etmek için:

```bash
python -m pulse.speech --input /path/to/script.txt --output /tmp/pronunciation-review.json
```

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

Güncel doğrulanmış JSON ve kalıcı, küçük URL parmak izi kaydı, daha önce
yayımlanmış kaynakları yeni seçkiden çıkarır. Yeterli yeni haber kalmazsa eski haber yeniden yayımlanmaz.
Aynı günün sürümü yayın deposunda zaten mevcutsa, Actions artifact'ları silinmiş
olsa bile doğrulanmış sürüm oradan geri alınır; yeniden API ücreti oluşturulmaz.

İşin başarılı ara çıktıları, başarısız sonucun ardından da 2 günlük Actions
artifact'ına yazılır. Yalnız bu depodaki bu iş akışının `main` üzerindeki güvenilir
`schedule`/`workflow_dispatch` çalışmaları geri yüklenir; PR çıktıları kullanılmaz.
Yeniden çalıştırma aynı günlük JSON'u, konuşma metnini ve geçerli sesleri kullanır.
Tamamlanmış bir sürüm yeniden numaralandırılmaz veya tekrar seslendirilmez.
Artifact silinirse henüz yayımlanmamış, tamamlanmamış günün bazı ücretli üretimleri yeniden gerekebilir;
2 günlük artifact geçmişi uzun vadeli arşiv değildir. Güncel sürüm yayın deposunda; önceki günler doğrulanmış Drive ZIP’lerinde kalır. Araştırma başarısız olursa diğer günün haberleriyle doldurulmaz.

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

Haber seçimi tam metin üretiminden önce kategori, farklı kaynak/olay kimlikleri ve
genişletilmiş yayın alt sınırıyla denetlenir (teknoloji 12, oyun 10; üst sınır 24).
Geçersiz seçki aynı kaynaklarla yalnız bir kez yeniden değerlendirilir. Kaynak
yetersizse sayı doldurulmaz, tam metin/ses üretimine geçilmez. Hata kategori,
seçilen geçerli haber sayısı ve gereken aralığı bildirir. Son yayın doğrulaması
ve bağımsız tam haber denetimi ayrıca korunur.

Tamamlanmamış günlük iş tekrarında araştırma 30 dakikadan eskiyse RSS havuzu
yenilenir; tamamlanmış kategorinin kaynak kanıtları korunur. Kısa RSS alıntıları
seçimden önce izinli yayıncının tam metniyle zenginleştirilir. Modelin seçim
girdisi yine kaynak başına en çok 2200 karakterdir; tam kanıt sonraki metin ve
denetim adımlarında korunur. `research-diagnostics.yml` ücretli AI/ses çağrısı
yapmadan eski/yeni havuz sayısını, kaynak hatalarını ve aday başlıkları inceler.

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
Güncel hazır yayın public yayın deposundaki `releases/` altında korunur; geçmiş
günler özel Drive ZIP’lerindedir. Artifact temizliği bu kopyaları silmez.
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

## Telaffuz ve ses revizyonu

`pulse/pronunciations.json`, iki ses üretim yolunun ortak ve gözden geçirilebilir
telaffuz sözlüğüdür. PULSE için İngilizce **Pals** okunuşu kullanılır. Haber metni
ve bağımsız denetimden geçmiş podcast metni değiştirilmez; yalnız sentez kopyası
dönüştürülür. Bilinmeyen özel adlar tahmin edilmez. Sözlük değişince `AUDIO_REVISION`
yükseltilmeli; özel sunucu sesleri ve çalışan Edge/Gemini yöntemleri korunmalıdır.

Günlük workflow’un `refresh_audio=true` seçeneği yalnız güncel eksiksiz yayının
seslerini yeni değişmez bir sürümde üretir. Tarih, dahili sayı ve haber seçkisi
korunur; `audio-vN` yolu sabitten hesaplanır. İki özet ve iki podcast tam doğrulanmadan
yeni sürüm açılmaz. Başarısız sentez mevcut sesleri değiştirmez. Sentez kopyaları
ve sözlük/diyalog hash’leri private Actions kontrol noktasında kalır.

## Kalıcı oynatıcı ve konu işaretleri

`assets/listening.js` opsiyonel konu verisini son MP3 SHA-256 kimliğine bağlar.
`site/assets/chapters/<mp3-sha256>.json` yalnız denetlenmiş kamuya açık başlıkları
ve gerçek başlangıç saniyelerini içerir; döküm, API yanıtı ve anahtar içermez.
`pulse.chapters` ve tarayıcı aynı sıralama/süre/başlık koşullarını denetler.
Hatalı/eksik veri podcast'i engellemez, yalnız konu sekmesi gösterilmez.
Derleme yalnız güncel seslerle eşleşen veriyi `assets/chapters/index.json` içine
alır; mevcut bölüm JSON'u, manifest ve MP3 hash'leri değişmez. Taşınabilir Drive
ZIP'i de konu verisini içerir ve ağ gerektirmeden kullanır.

Mevcut sesleri değiştirmeden incelemek için `podcast-chapters.yml` elle
çalıştırılır. Sadece mevcut kayıtları okur; sentez veya dağıtım yapmaz. Dökümler
üç günlük özel artifact olarak saklanır. İsteğe bağlı çözümleme bağımlılıkları
`requirements-chapters.txt` içindedir; çalışan Edge/Gemini sentez ortamına zorunlu
eklenmez. PyAV 19, faster-whisper 1.2.1 ile uyumsuz olduğundan 16.0.1 sabittir.

Canlı geçiş onayı sonrasında bölüm işaretleri günlük akışta varsayılan açıktır;
`PULSE_CHAPTERS_ENABLED=false` isteğe bağlı son-ses çözümlemesini kapatır.
Sabah 07:15 sınırı yalnız yayını bekletmeyen ilk denemenin sınırıdır; işaretlemeyi
günün geri kalanı için iptal etmez. `complete-chapters.yml`, başarılı günlük iş
sonrasında ve Türkiye saatiyle 08:17–23:17 arasında her saat güncel yayını
kontrol eder. Elle de çalıştırılabilir; haber veya ses üretmez. Hazırlık/eski
yayınlarda ve iki podcastin indeksli işaretleri zaten hazırsa ücretli çağrı yapmaz.
Günlük dağıtımla aynı concurrency kilidini kullanır; yanlış gün/ses kimliğiyle
tamamlama engellenir. Bir programın onaylı işaretleri diğerinin hatası nedeniyle
kaybolmaz. Yeni işaretler mevcut yayın kimliği ve dört MP3 korunarak yeniden
derlenir; günün Drive ZIP'i yenilenip doğrulandıktan sonra Pages'e gönderilir.
Eksik işaret veya dağıtım hatası workflow'u başarısız bırakır; saatlik telafi
hazır özel aşamalardan devam eder. Döküm, başarılı öneri/denetim yanıtları ve
onaylı işaretler üç günlük `pulse-chapter-state-...` artifact'ında saklanır.
Yalnız bu workflow'un main dalındaki güvenilir tetikleyicileri geri yüklenir.
Yanıt önbelleği tam girdi, model, talimat ve yanıt hash'leriyle bağlıdır;
yapısal olarak geçersiz öneriler önbellekten çıkarılır. Döküm, özel denetim
yanıtları ve kullanım kayıtları public siteye veya Drive yayın ZIP'ine girmez.
Konu listesi 4–10 gibi bir hedefe sığdırılmak için kırpılmaz; konuşulan bütün
ana geçişler kapsanır (şema üst sınırı 40). Bağımsız denetçinin eksik konu
geri bildirimi aynı ses/döküm/model kimliğiyle sonraki denemeye taşınır.
Checkpoint kaydı metadata klasörlerini aynalar; silinen reddedilmiş yanıtlar
ve giderilmiş eski geri bildirimler sonraki artifact'a geri eklenmez.
İlk tamamlama, aynı yayın kimliğinin güvenilir günlük checkpoint'indeki hazır
döküm ve denetim aşamalarını da devralır. Açık sekmeler, aynı yayın kimliğine
sonradan eklenen işaretleri başarılı manifest kontrollerinden sonra yeniden
arar; oynatma ve okuma konumu değiştirilmez.
Konu işaretleri yayının zorunlu ses/JSON kapısından ayrıdır. Zamanları model tahmin etmez: Whisper'ın gerçek segment
başlangıçlarını metin editörü seçer, ikinci bağımsız inceleme onaylar. Bu otomatik
inceleme insan dinleme kontrolü veya hatasızlık garantisi değildir. İlk mevcut
kayıtların geçişleri ayrıca incelenmelidir. Başarısız işaretleme günlük yayın
kapısını veya orijinal sesleri değiştirmez; Actions özetinde sonucu görünür.

Site yalnız güncel yayını gösterir; geçmiş haber/bölüm kataloğu oluşturulmaz.
Çalan kayıt kendi release/asset kimliğini tutar; sayfalarda gezinmek onu değiştirmez.
Sabah kapısı açılınca yeni yayın beklenir. Kullanıcının başlattığı sesin kontrolleri
kalır; eski dosya yayından kaldırıldıktan sonra tamponlanmamış kısmın devamı
garanti edilemez. Hata durumunda yeni kayda kendiliğinden geçilmez.

## Günlük Drive arşivi, temizlik ve haber tekrarı

Her gün için son sürüm `PULSE-DD.MM.YYYY.zip` olarak saklanır: ana sayfa, haber
detayları, kaynak bağlantıları, yerel görseller, dört ses ve varsa konu işaretleri.
ZIP açılıp `index.html` tarayıcıda açılarak dolaşılabilir; kaynak siteler dış bağlantıdır.
Yüklenen ZIP tamamen geri indirilip hash/envanter denetlenmeden eski ZIP veya
site dosyaları kaldırılmaz. Aynı günün eski sürümleri yalnız son sürüm doğrulandıktan
sonra emekliye ayrılır. Drive doğrulaması başarısızsa dağıtım durur.
Drive okuma ve mutlak metadata güncelleme (GET/PATCH) isteklerinde geçici
408/429/500/502/503/504 veya bağlantı/zaman aşımı hataları en çok beş denemeyle,
artan bekleme ve küçük rastgele gecikmeyle yeniden denenir. En fazla 30 saniyelik
sayısal `Retry-After` dikkate alınır. Kalıcı hatalar dağıtımı yine durdurur;
dosya oluşturan POST ve gövdeli PUT yüklemeleri körlemesine tekrarlanmaz.

Hazırlık dağıtımında önceki günün tüm release klasörleri ve artık kullanılmayan
haber yolları doğrulanmış Drive makbuzlarıyla kaldırılır. Hazır dağıtımda yalnız
aktif release tutulur; aynı günün eski sürümleri de son günlük yedek doğrulanmışsa
kaldırılır. Bütün adaylar silme başlamadan denetlenir. Hazırlık tekrarında önceki temizlik
tamamlanmışsa ve yedeklenecek yayın yoksa boş makbuzla devam edilir; eksik
“hazır yayın” bu istisnadan yararlanamaz. Yedekleme mevcut günlük
concurrency kilidi altındadır; kullanıcıdan yeni bir Drive izni gerektirmez.

`data/source-history.json` haber metni, başlık veya görsel içermez. Sabit 512 KiB
Bloom filtresinin sıkıştırılmış biçimidir (JSON alanı üst sınırı yaklaşık 700 KB).
Kaynak URL SHA-256 parmak izleri eklenir; önceki ham hash listeleri kayıpsız taşınır.
HTTP/HTTPS, www, son eğik çizgi, fragment ve bilinen takip parametreleri eşitlenir;
içerik kimliğini değiştirebilen query parametreleri korunur. Eski biçimden kalan,
URL’si artık mevcut olmayan takipli hashler geriye dönük eşitlenemez.

Filtre eklenen kimliği unutmaz. Az olasılıkla yeni bir adresi de eski sanabilir;
doluluk %30’u aşarsa geçmişi sıfırlamak yerine yayın durur ve geçiş gerekir.
En kötü izinli dolulukta tek kontrolün yanlış eşleşme olasılığı yaklaşık %0,022’dir;
normal dolulukta çok daha düşüktür. Başka yayıncı/URL ile yeniden yazılmış aynı
olayı kesin tanımaz. Gerçek yeni gelişmeler için farklı makale kimlikleri korunur.

Bu temizlik yayın ağacını küçültür; Git geçmişindeki eski MP3 nesnelerini silmez.
Git geçmişini yeniden yazmak ayrı, ayrıca onaylanması gereken bir taşıma işlemidir.

Konu satırına dokunmak sesi ilgili saniyeden başlatır, haberi/okuma konumunu
korur. Başka bölümün sayfasını incelemek sesi değiştirmez. Uzun oynatıcı konusu
ölçülen taşma kadar ileri/geri kayar; azaltılmış harekette tam metin sabittir.
Konu listeleri satıra yayılır, kaymaz. Kategoriye özgü arama ve
çoklu filtreler geri dönüşte korunur; filtre panelinde Uygula dışında kapatma
seçimleri değiştirmez. Native dialog ve klavye odağı kullanılır.


## Üretim maliyeti ölçümü

Son inceleme: [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md). Günlük çalışma özel
`api-usage.jsonl` içine sağlayıcı token sayaçlarını ve giriş karakterlerini yazar;
prompt/yanıt/anahtar içermez. Günlük Actions checkpoint'ine dahildir, public site
ve Drive yayın ZIP'ine dahil değildir. Eksik sayaç sıfır maliyet anlamına gelmez.
Ücretli TTS yanıtı dönüştürülemezse yalnız girdi ve içerik hash'i eşleşen ham yanıt
kurtarılır. Bilinmeyen/bozuk ham içerik geçerli yayın sayılmaz; yerel dönüştürme
hatası nedeniyle aynı alınmış yanıt tekrar servisten istenmez.

## Haber tekrarı: kesin bağlantılar ve yakın dönem olay hafızası

Bağlantı geçmişi v3, SHA-256 parmak izlerini kesin bir kümede tutar. Yeni bir
bağlantıyı Bloom çakışması yüzünden elemez. Eski v2 filtresi geri çözülemez;
eski olasılıklı eşleşmeler yalnız tanısal bilgi olarak korunur. Mühürlü geçmiş günlük
sürümlerden (aynı günün yayımlanmış revizyonları dahil) doğrulanarak alınan başlangıç parmak izleri `pulse/history-seed.json`
içindedir; bunlar önceki günleri yeni sisteme taşır. Yeni kayıtlar yaklaşık
haber başına 67 bayt JSON'dur; 40 haber/gün yaklaşık 1 MB/yıl eder. 500.000
parmak izinde sessizce sıfırlamak yerine açık hata verir.

Son 90 günün olay kimliği, başlığı ve en çok 320 karakterlik kısa özeti ayrı
hafızada tutulur; ses, görsel ve tam haber metni tutulmaz. Son günlük sürüm de
kaydedilir, yalnız Drive doğrulanmış eski sürümler silinir. Günlük seçki için
adaylarla ilişkili en fazla 80 eski olay mevcut seçki isteğine eklenir; yeni bir
model çağrısı yapılmaz. Editör aynı olayı farklı kaynakta yeniden seçmemeli,
aynı şirket/oyun hakkındaki somut yeni gelişmeyi ise ayrı olay olarak seçmelidir.
Bilinen olay kimliği tekrar seçilirse kod da eler; haber alt sınırı düşürülmez.
Bu anlamsal denetim yüzde yüz tekrar yakalama garantisi değildir: çeviri,
ilişkilendirme ve model yorumundan kaynaklı belirsizlikler vardır. 90 günden eski
bağlantı parmak izleri kalır; kısa olay hafızası zamanla sona erer.

## Görsel hakları kanıt taraması

`image-rights-audit.yml` mevcut canlı yayının her görseli için kaynak sayfadaki
kredileri ve kullanım koşulu bağlantılarını toplar. API/AI anahtarı, ses üretimi,
yayın veya görsel kopyalama yapmaz. HTTP 200, CDN adresi, robots.txt, kaynak
belirtme veya kredi satırı yeniden kullanım izni değildir. Rapor otomatik hukuki
onay vermez; belirli görseli kapsayan lisans, hak sahibi ve koşullar ayrıca
incelenmelidir. Açık izin doğrulanmadan dış görseller yerel varlık olarak
kopyalanmaz. Erişilemeyen kaynak "yasak" değil "doğrulanamadı" sayılır.

## Geçici yayın kontrolü hatalarından toparlanma

Tarayıcı, ağ/timeout/429/5xx hatasında son tam doğrulanmış yayını en fazla
120 saniyelik doğrulama süresi içinde korur; bu süre başarısız denemelerle
uzatılmaz. Ertesi gün 06:00 veya hazırlık manifesti bu toleransı geçersiz kılar.
Bozuk JSON, hash uyuşmazlığı ve eksik dosya gibi bütünlük hataları hemen kapatır.
Doğrulama işleminin tamamı (manifest, iki JSON, dört ses HEAD isteği) ortak
15 saniyelik son süreye tabidir. Hata durumunda 5/10/20/30 saniye aralıklarla
tekrar denenir; bağlantı geri geldiğinde, sekmeye dönüldüğünde veya tekrar dene
butonuyla beklemeden kontrol edilir. Başarılı doğrulamada yeniden deneme sayacı
sıfırlanır. Sayfa değiştirme/render hataları da aynı toparlanma yoluna girer.

CDN Date/Age yanıtı geriden gelirse zaman geri alınmaz: son doğrulanmış sunucu
zamanı + monotonik süre alt sınırı kullanılır. Bu, geriden gelen yanıtın sekmeyi
kalıcı hata döngüsüne sokmasını ve eski saatin 06:00 kapanışını ertelemesini önler.

## Akış ve haber podcast kesitleri

`/akis/` günlük yayının ayrı dikey okuma görünümüdür; normal sayfalar korunur.
Metin kendi içinde kayar. Sınırda yeni bir dokunma/kaydırma hareketi gerekir;
kaydırma ivmesi haber değiştirmez. Önceki/sonraki düğmeleri ve haber sınırında
PageUp/PageDown desteği vardır. Okuma konumları sekmenin geçmiş durumunda tutulur.

Haber kesitleri **ses sentezi değildir**. `prepare_chapters.py` mevcut son MP3'ün
zamanlı dökümünü kullanır. Aynı öneri ve bağımsız denetleme çağrısında `story_id`,
başlangıç ve dahil son döküm segmenti seçilir. Başlık benzerliği eşleşme sayılmaz.
Bölüm işaretlerinin sonraki konu başlangıcı kesit bitişi diye varsayılmaz.
`clips_reviewed`, özgün kayıt SHA-256 ve haber kataloğu SHA-256 gerekir; belirsiz,
yer almayan veya ayrıştırılamayan habere kesit atanmaz. Bir habere birden çok,
birbiriyle çakışmayan kesit atanabilir. Onaylı boş liste geçerli bir sonuçtur.

`pulse.clips.build_clips` doğrulanmış aralıkları FFmpeg stream-copy ile kısa MP3'e
ayırır; orijinal kayıtları değiştirmez ve yeniden kodlamaz. MP3 kare sınırları
nedeniyle en fazla 0,2 saniye süre farkına izin verilir; her çıktı ffprobe ve tam
ses çözümlemesinden geçer. Arayüz saniye sayaçlarına güvenerek tam podcast'i
kesmeye çalışmaz: kısa dosyanın doğal sonu arka planda da oynatmayı bitirir.
Kesitler önceden topluca indirilmez. Oynatma için mevcut tek `audio` ve yüzen
oynatıcı kullanılır; hız, ses ve medya kontrolleri aynı kalır. Tam bölüme geçiş
kesitteki karşılık gelen saniyeden devam eder. Haber değişimi kesiti durdurur,
tam podcast'i durdurmaz. Tam podcast'in dinleme konumu kesitle ezilmez.

`assets/clips/index.json` güncel yayın kimliğine bağlıdır. İndekse yalnız güncel, doğrulanmış eşleşmeler eklenir. Kısa dosyalar
`releases/<yayın>/clips/` altındadır; eski yayın klasörüyle birlikte yalnız
Drive yedeği doğrulandıktan sonra kaldırılır. Aynı
kesit aynı gün yeniden derlendiğinde hash doğrulamasıyla tekrar kullanılır.
Drive taşınabilir ZIP'i Akış sayfasını, kesit indeksini ve kısa MP3'leri de içerir;
mevcut yedek doğrulama ve temizleme sırası değişmez. Geçmiş haber menüsü eklenmez.
Eski, yalnız başlık içeren chapter sidecar'ları okuma/oynatmayı bozmaz; bağımsız
chapter tamamlama işi katalog bağlı eşleşmeler eksikse özel kontrol noktasından
kayıt dökümünü tekrar kullanarak yükseltir. Ses üretme iş akışı elle başlatılmaz.


### Sürükleyici Akış ve habere ait kesit sırası

Akış'ın tek satırlı başlığında kapatma solda, başlık ekran merkezinde, yerel
kategori seçimi sağdadır. Mobilde sabit alt araç çubuğu yoktur; sıradaki haberin
başlığı ve görseli okuma içeriğinin sonunda tıklanabilir bir önizlemedir.
Önceki habere dönüş içerikte, masaüstü oklarında ve PageUp ile erişilebilirdir.
Başlık okurken hareket ederek içerik sıçratmaz. Tarayıcı tam ekran izni istenmez;
kullanılabilir `dvh` alanı ve cihazın güvenli kenar boşlukları kullanılır.

Aynı habere ait birden çok doğrulanmış aralık tek “Podcast’te bu konu” alanında,
kesit sayısı ve toplam süreyle gösterilir. Mevcut tek ses öğesi bu kısa dosyaları
kayıt sırasına göre çalar; son dosyanın doğal bitişinde durur. Aradaki ilgisiz
konuşma oynatılmaz, dosyalar veya onaylanmış sınırlar yeniden üretilmez.
Çoklu kesitte önceki/sonraki kesit düğmeleri ve “Kesit 1/2” bilgisi vardır.
Tam bölüme geçiş o anda çalan kesitin özgün kayıttaki saniyesini kullanır.
Haber değişimi veya sayfalar arasında gezinme dinlenen kesit sırasını durdurmaz.
Başka haberin sesi açıkça başlatıldığında tek oynatıcı yeni kesite geçer.
“Dinlenen habere dön” Akış içinde ilgili haberi bulur; kategori farklıysa doğru
kategoriye geçer. Diğer sayfalarda ilgili haber ayrıntısını açar. Son kesitte
oynatma durur; başka haber otomatik başlamaz. Tam podcast de gezinirken devam eder.
Yeniden dinleme sıralamanın başından başlar. Bu arayüz güncellemesi model veya
ses üretimi çağrısı yapmaz; `refresh-website.yml` ile yayımlanır.

## Zorunlu günlük kalite ve hazır yayın kurtarması

20.10.2026 sonrası üretimde dört kaydın tam çözülmesi, beş saniye ve üzeri
-50 dB sessizlik bulunmaması ve iki podcast için son dosya hash'ine bağlı,
bağımsız incelenmiş bölüm/haber eşleşmeleri zorunludur. Bölüm analizi artık
07:15 yaklaşınca atlanmaz; eksik bölümle yayın açılmaz. TTS parçaları da cache'e
alınmadan denetlenir; hatalı parça en çok bir kez yenilenir, sağlam parçalar
korunur. Bu değişiklik mevcut erkek ses kimliklerini ve Edge TTS yöntemini korur.

`publish-ready.yml` yalnız mevcut, mühürlü kontrol noktasını yayımlar; model veya
ses üretmez. 07:15 ve 07:25 TRT tetikleri tamamlanmış paketi doğrular, 07:30
öncesi yayına vermez. 07:45 ve 08:15 ek kontrolleri hazır paketi kurtarır; zaten
hazır yayın varsa canlı dosyaları denetler ve yeni yedek/commit oluşturmaz.
GitHub cron ve dış servisler kesin saat garantisi vermez; eksik veya bozuk yayın
başarılı sayılmaz. Aynı concurrency grubu tüm yayın yazarlarını sıraya koyar.

20 Ekim Moradon FM için tek seferlik `repair-audio-2026-10-20.yml`, yalnız
`audio-repair-2026-10-20.json` içindeki kaynak SHA ve sessiz aralığı kabul eder.
MP3 paketlerini yeniden kodlamadan keser; diğer üç ana ses dosyasını korur.
Mevcut incelenmiş bölüm/kesit sınırlarını aynı konuşmaların yeni zamanlarına
matematiksel olarak taşır; yeni başlık veya konuşma uydurmaz. Yeni kayıt hash'i,
yayın kimliği, kesit dosyaları ve günlük Drive ZIP'i birlikte yenilenir.

### Akış devamı ve görsel/konu yükleme dayanıklılığı

`pulse-flow-progress-v1` yalnız cihazın localStorage alanında, tek günlük
kayıt tutar: yayın tarihi/kimliği, haber kimliği, kategori ve okuma konumu.
Menüden dönüş ve yeni sekme bu kaydı kullanır; tarayıcı geri/ileri konumu
önceliklidir. Yeni tarihte kayıt bırakılır; aynı gün sıralama değişirse haber
kimliğiyle bulunur, kaldırılmış haber kategori başına döner. Revizyon değişince
eski “tamamlandı” durumu yeni haberleri okunmuş saymaz. Ses otomatik başlamaz;
mevcut ses devam eder. “Başa dön” seçili kategorinin ilk haberini açar. Arşiv
ZIP'i canlı konum kaydını okumaz/değiştirmez; engellenmiş storage Akış'ı bozmaz.
Görsel/font yüklenirken konum yerleşimi tamamlanır; kullanıcı girdisi otomatik
konum düzeltmesini iptal eder.

Erişilemeyen kaynak fotoğrafın yerine yerel PULSE kapağı açıkça “Temsili görsel”
etiketiyle gösterilir; kaynak fotoğrafın kredi satırı bu sırada gizlenir, haberin
kaynak bağlantısı korunur. Bu bir görsel izin tespiti veya kaynak fotoğrafı
kopyalama değildir. Fotoğrafın manuel yeniden denemesi çalışmaya devam eder.
Bölüm dizini eskiyse SHA-adresli sidecar ayrıca okunup aynı ses hash'i ve zaman
kurallarıyla doğrulanır; başka kayda ait bölümler hiçbir durumda kullanılmaz.
Hazırlık ekranı son kullanıcıya iç hedef aşımı veya teknik hata metni göstermez.

Günün yayını zaten hazırsa normal otomatik tekrar eski özel artifact'ı geri
yüklemez; `restore_published` doğrulanmış güncel yayını kullanır. Böylece aynı gün
onaylı ses kesimi veya görsel revizyonundan sonra eski kontrol noktası yeni
canlı dosyalarla çakışmaz. Açıkça istenen revizyon modları kendi kontrol
noktalarını korur; bu değişiklik yeni ses üretimi başlatmaz.

Editör API'sindeki geçici ağ/408/429/5xx hataları en fazla üç ulaşım denemesiyle
aynı adımda toparlanır; bekleme sınırlıdır. 400/401/403 gibi kalıcı hatalar yeniden
denenmez. Başarılı fakat bozuk JSON içerik en fazla bir kez yeniden istenir;
geçersiz içerik düzeltilmiş gibi kabul edilmez, mevcut kullanım sayaçları korunur.

Akış’ta sıradaki haber kartı ve önceki/sonraki düğmeleri, içeriği değiştirmeden
önce odağı kaydırmadan okuma alanına taşır. Mobil tarayıcının alttaki odaklı
düğmeyi görünür tutmak için yeni haberi aşağı kaydırması önlenir. İlk ziyaret
baştan, yeniden ziyaret o haberdeki son konumdan açılır; bitiş ekranı uygun
kontrole odaklanır. Navigasyon ses oturumuna dokunmaz. Dokunmatik Chromium
testi gerçek kart dokunmalarını, masaüstü testi sabit okları ve klavye odağını denetler.

“Sıradaki haber” kartının üzerinden başlayan sınır kaydırması da metinle aynı
biçimde işlenir; hareket, kartın tıklamasını tetikleyip ikinci haberi atlamamalıdır.
Diğer bağlantı, ses düğmesi ve form kontrolleri bu jestten korunur. Native
Chromium dokunma testi bir hareketin tek haber ilerlettiğini ve geri dönebildiğini denetler.

### 21.10.2026: editoryal yapı ve uzunluk hatalarından toparlanma

Haber seçkisinin kaynak kimliği, zorunlu başlık/özet/önem alanları ve varsa
brief biçimi makale üretiminden önce doğrulanır. Eksik alan, aynı kanıtlarla
sınırlı bir düzeltme isteğine gider; KeyError ile düzeltme aşamasını atlamaz.
Tam makale JSON’u da bozuk kimlik/alan/paragraf için bir kez düzeltilir, ardından
ayrı olgu denetiminden geçer. Kaynak, haber sayısı ve inceleme koşulları korunur.

Podcastte yerel kelime sayımı bağımsız denetimden önce yapılır; aralık dışındaki
metin en çok iki hedefli düzeltmeyle aralığın ortasına yönlendirilir. Gerçek ses süresi
sınırları korunur, dolgu veya tekrara izin verilmez; sonuç ayrıca bağımsız olgu
ve sohbet denetiminden geçer. Metin, tam kanıt/ayar parmak izine bağlı özel
podcast-draft.json dosyasında saklanır; başarısız aşama yeniden başladığında
ilk taslağı ve editör aşamasını tekrar satın almaz. Taslak hiçbir zaman onay
sayılmaz; değişen kanıtlar eski taslağı geçersiz kılar. Geçici HTTP ve bozuk JSON
yanıtları sınırlı olarak yeniden denenir. Normal başarılı akışa ek model çağrısı
eklenmez; ücretli bağımsız denetim zaten kısa olduğu bilinen metne harcanmaz.

Kullanıcı 21.10.2026’da bugünkü eksik üretimin tamamlanmasını açıkça istedi:
mevcut günlük checkpoint ile normal üretim çalıştırılabilir; hazır dosyaları
yeniden üretmek için refresh_audio veya expanded_issue kullanılmaz. Bu izin
yeni bir günün elle ses üretimi için genel izin değildir.

Sabah plan adımı üretimden önce sentetik tam test paketini yeniden çalıştırmaz;
aynı paket PR ve main kalite CI’ında zorunlu çalışır. Gerçek dosya, ses, bölüm,
Drive ve canlı Pages kontrolleri korunur. Üretim cron’una 08:30/09:00 TRT için
iki sınırlı geç toparlanma denemesi eklendi; günün manifesti ready ise bu ek
tetikler plan aşamasında kapanır ve yeni model/ses/yedek işi çalıştırmaz.

İptal edilen günlük çalışmanın generate işi `always()` koşuluyla yeniden
başlamamalıdır; koşul ayrıca `!cancelled()` gerektirir. Başarısız/atlanmış
gate sonucu uygun biçimde değerlendirilirken kullanıcı iptali dikkate alınır.
Güvenli checkpoint kaydetme adımları kendi always() koşullarını korur.

Kelime aralığı süre için kaba yazım hedefidir, tek başına kalite ölçüsü değildir.
2446 veya 3429 kelimelik, bağımsız denetimden geçen iyi bir metin yalnız yazım
hedefinin sınırları nedeniyle kısaltılıp uzatılmaz. Ses üretiminden önce yalnız
belirgin sapmalar için geniş bir makullük kontrolü yapılır: gerçek süre hedefi
ve 120–180 kelime/dakika tahminiyle türetilen bandın dışındaki metin en çok iki
kez düzeltilir. Bu konuşma hızı kesin ölçüm değildir; pahalı ses üretiminden önce
açıkça kısa/uzun taslağı yakalayan bir ön kontroldür.
Asıl yayın sözleşmesi değişmedi: teknoloji gerçek ses süresi 15–25 dakika, oyun
12–22 dakika; olgu/sohbet incelemesi, ses bütünlüğü, sessizlik ve bölüm kontrolleri
zorunludur. Bu sürelerin dışındaki MP3, kelime sayısı uygun olsa da yayımlanamaz.

### İlk cron’un üretimi de üstlenmesi

06:00 tetikleyicisi canlı hazırlık kapısını güncelledikten sonra aynı çalışma
içinde üretime devam eder. Araştırma 06:15 gelmediyse yalnız o saate kadar bekler;
gecikmişse hemen başlar. İçerik ve ses için ayrıca 06:30/06:45 saatlerini beklemez.
Böylece ilk cron zamanında geldiğinde ikinci 06:15 cron’unun gecikmesine bağlı
kalınmaz. Diğer cron’lar ara çıktılardan devam eden yedeklerdir; aynı gün ready
olan yayın için ücretli üretim çalıştırılmaz. 07:30 yayın kapısı değişmedi.

### 22.10.2026’dan itibaren ortak editoryal politika

Kullanıcı 21.10.2026’da iki yayına aynı politika uygulanmasını, haberlerin önem
sırasına konmasını ve podcastte zorlama bağlantılar kurulmamasını onayladı.
Bugünkü haber/ses üretimi veya dağıtımı başlatılmaz. `daily-v2` profili yalnız
22.10.2026 ve sonraki tarihlerde yeni sayılar için seçilir. Önceki `expanded-v1`
sayıların haber ve gerçek süre sözleşmeleri değişmez; eski ZIP’ler doğrulanabilir.

İki kategori de 15–20 önemli ve farklı gelişme hedefler. Bu hedef alt sınır
değildir: yalnız yeterli kaynağı olan haberler seçilir; boş seçki engellenir.
24 haberlik teknik paket üst sınırı korunur. Araştırma aşamasının güncel aday
havuzu kontrolleri değişmez. Daha az haber seçmek, araştırma hatalarını veya
eksik kaynakları yok sayma izni değildir.

Her haberin `editorial_priority` alanı etki, somut gelişmenin büyüklüğü, güncellik
ve kanıt açıklığı için 0–4 değerlendirme ile kaynak olgularına dayanan gerekçe
içerir. Puan nesnel gerçek veya doğruluk garantisi değildir. Gerekçedeki olgular
mevcut bağımsız haber incelemesine dahildir; ek model çağrısı gerekmez. Aynı
rubrik iki kategoride de kullanılır. Toplam puan sıralamayı belirler; eşitlikler
kararlı haber kimliğiyle çözülür, kategori veya görsel tercih edilmez. Kategori
sayfaları ve birleşik liste aynı sıralama bilgisini kullanır. Ana sayfada en
yüksek öncelikli haber başa gelir; üçlü seçkide iki yayın da temsil edilir.
Eski profildeki sayılar mevcut yerleşimlerini korur.

İki podcast de yaklaşık 15–25 dakika / 2500–3100 kelime hedefler. Yeni profilde
kelime veya dakika kotası için metin uzatılmaz, kısaltılmaz veya yeniden
üretilmez. Gerçek sesin çözümlenebilmesi, en az 40 saniyelik temel dosya kontrolü,
olgu/sohbet incelemesi, uzun sessizlik denetimi ve iki podcastin onaylı bölüm/kesit
verileri zorunludur. 40 saniye editoryal hedef değildir; içerik derinliği ve önemli
konuların yeterli ele alınması bağımsız incelemede değerlendirilir. Kaynaklar
yeterliyken yüzeysel veya tekrarla uzatılmış sohbet reddedilir.

Yaşar ana sunucudur. Konular arasında gerçek ilişki varsa kullanılabilir; yoksa
kısa ve doğrudan konu değişimi geçerlidir. Her geçişe ortak tema, espri veya soru
eklenmez. Necdet her konuda soru sormak veya karşı çıkmak zorunda değildir.
Yazım, editör ve bağımsız denetim talimatları bu davranışı birlikte uygular.
Çalışan Gemini/Edge yöntemi, ses kimlikleri ve telaffuz katmanı değiştirilmez.

Az haberli yeni profilde günün özeti sabit 20 saniyeye zorlanmaz. Üretim,
checkpoint yeniden kullanımı ve son yayın denetimi aynı metne bağlı süre alt
sınırını kullanır: özet metnindeki kelime sayısı / 4; en az 5, en çok 20 saniye.
240 kelime/dakika, bariz kısa çıktıyı ayıklamak için geniş bir üst hız varsayımıdır;
konuşma hedefi veya kaydın bütün metni kapsadığının kanıtı değildir. Tarayıcıda
yeni profil için 5 saniyelik temel metadata kontrolü bulunur; sunucunun daha güçlü
metin kontrolü ve doğrulanan MP3 kimliği korunur. Önceki profillerde 20 saniye
şartı değişmez. Tam çözümleme, boyut/hash, uzun sessizlik ve yayın kontrolleri
devam eder; kısa özeti uzatmak için metin veya ses yeniden üretilmez.

### Tam kapaklı dinleme kartları

Günün seçkisinde iki podcast kapağı, kategori sayfalarında o kategorinin podcasti
ve Günün Özeti yan yana gösterilir. Kare kapaklar kırpılmaz; kategori grubunun
genişliği 440px, ana sayfa podcast grubunun genişliği 480px ile sınırlıdır.
Kapak bağlantısı bölüm ayrıntısını açar, sağ alttaki bağımsız 44px düğme mevcut
tek ses oturumunu oynatır/duraklatır. Kart içine ikinci oynatıcı yerleştirilmez.
Kategori başlıklarında çıplak haber sayısı bulunmaz; arama/filtre sonuçlarında
“N haber bulundu” gösterilir. Özetlerin özgün, üretilmiş kalıcı seri kapakları
`ozet-teknoloji` ve `ozet-oyun` adıyla 192/768px WebP olarak saklanır; günlük
görsel üretimi gerekmez. Güncelleme yalnız `refresh-website.yml` ile mevcut
haber ve dört MP3 korunarak, yenilenmiş Drive yedeği doğrulandıktan sonra yayımlanır.

### Haber doğruluk reddinden sonra devam etme

Tam haber doğruluk denetiminde önem gerekçesi kaynak kanıtı değildir: taslağın
`editorial_priority` alanında yazılır, düzeltilebilir ve onaylı sürümü yayına taşınır.
Gerekçesi veya puan şeması geçersiz olan bir haber onaylanmış sayılmaz. Denetim
kapısı kaldırılmaz. İki denetim de reddederse o çalışma başarısız olur.

Her dört haberlik grubun son taslağı, kullanılan kaynak kanıtları ve denetim
bulguları özel günlük çalışma alanındaki `articles/*.review.json` dosyalarına
kaydedilir. Sonraki deneme aynı girdiler için bu bulgularla başlar; onaylanmış
haber grupları yeniden üretilmez. Kaynak, tarih ve geçmiş olay bağlamı aynıysa
seçki de `articles/selection.json` üzerinden tekrar doğrulanarak kullanılır;
girdi değişirse önbellek geçersizdir. v2 haber önbelleği eski denetim sözleşmesini
kullanmaz. Ayrıntılar özel `pulse-state` artifact'ında kalır; site build'i bunları
kopyalamaz. Actions hata mesajında yalnız kaynak kimlikleri ve özel rapor dosya
adı yer alır. API/servis ve cron gecikmeleri için mutlak saat garantisi yoktur;
bu değişiklik bağımsız incelemeyi atlayarak yayın garantisi vermez.
