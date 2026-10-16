# PULSE — mobil yayın tasarımı

Beyaz PULSE ve pembe nokta ana markadır; kalp ritmi ve ekolayzır süsleri yoktur.
Lacivert zemin üzerinde teknoloji turkuaz, oyun mor tonlarla ayrılır. Ana sayfa
iki yayına giriş sunar; haberler ve sesler kendi bölümündedir. GitHub bağlantısı
ve tekrarlanan slogan/açıklamalar arayüzden çıkarılmıştır.

## Görseller

İki özgün, üretilmiş editoryal illüstrasyon aynı sinematik dünya diliyle hazırlanır:
oyunda bir MMORPG keşif manzarası, teknolojide gözlemevi/araştırma yerleşkesi.
Bunlar haber fotoğrafı olarak sunulmaz. Gerçek haber görselleri RSS kaynaklarından
gelir ve kaynakları belirtilir; başarısız görsel haberi gizlemez.

Kapakların 1440 ve 768 px WebP sürümleri `srcset` ile ekran/piksel yoğunluğuna göre
seçilir. Yayın kapakları tam kare görünür. Haber kartları tutarlı 16:9 çerçevede
`object-fit:cover` kullanır; ayrıntı sayfasında görsel tam, doğal oranıyla açılır.
Görsel kaynağı sağ alt köşede yarı saydam koyu zemin üzerinde yer alır. Yakınlaştıran hover animasyonu yoktur. Orijinal
üretim PNG'leri çalışma alanında saklanır; büyük PNG'ler public build'e alınmaz.
Sosyal görsel aynı kapaklardan `node scripts/render_og.cjs` ile yeniden üretilebilir.

## Ses ve hareket

Özel, klavyeyle kullanılabilen oynatıcı: oynat/duraklat, 10 saniye ileri/geri,
ilerleme, basışla 1 / 1.1 / 1.2 / 1.25 / 1.5 / 2× hız, ses ve sessize alma. Aynı anda tek ses çalar. MP3'ler kullanıcı
başlatmadan indirilmez (`preload=none`). Mobil Safari gibi tarayıcılar programatik
ses seviyesi değişimini sınırlandırabilir; cihazın ses düğmeleri geçerlidir.

Hazır yayında ilk gezinmede matbaa gösterilmez. Kısa doğrulama boyunca nötr zemin
ve yalnız uzayan istekte PULSE yükleme işareti vardır. Gerçek hazırlık durumunda
SVG baskı makinesinden yavaşça çıkan gazete; bağlantı hatasında ayrı
hata görünümü bulunur. Sayı/saat/JSON/MP3 doğrulaması atlanmaz. Animasyonlar yalnız
opacity/transform ağırlıklıdır ve `prefers-reduced-motion` ile kapanır.

## Doğrulama ve yayın

320 px telefon, farklı mobil ölçüler, tablet, masaüstü ve yatay telefon sınanır.
Gerçek MP3 oynatımı, hız/ses/arama, tek oynatıcı, yavaş manifestte sıfır matbaa
parlaması ve gerçek sabah kilidi tarayıcı testlerinde yer alır. axe erişilebilirlik
kontrolleri ana sayfa, yayınlar ve hazırlık ekranını kapsar. Önizleme görüntüleri
`test-results/` altında ve PR kalite artifact'ındadır. Canlı ses değişikliği önce
hosted dry-run ile, ardından dört dosyanın gerçek Pages hash kontrolüyle doğrulanır.

## Kompakt dinleme ve ayrıntılar

İki büyük oynatıcı yerine klavyeyle de değişen Sesli özet / Podcast sekmeleri
vardır. Seçilmemiş panel gizlenir ve sesi duraklatılır. Mobilde büyük tekrar
kapakları kaldırılır. Haber listesi kısa olgusal özeti gösterir; başlık statik
`/<bölüm>/haber/<kimlik>/` ayrıntı sayfasını açar. Kaynak hem listede hem ayrıntıda
kalır. Görünen tarih `16.10.2026`, sistem manifest tarihi ISO biçimindedir.

Yeni içerikler bölüm bazında güvenilir kaynak listesine karşı doğrulanır.
RSS HTML/srcset içindeki büyük görseller de değerlendirilir; eksikse yayıncının
Open Graph görseli aranır. Erişilemeyen görsel uydurulmaz. Mevcut sesleri yeniden
üretmeden `refresh_media` ile görsel bilgisi tamamlanabilir.

Özel Drive arşivi ve hesap kurulumu: [DRIVE.md](DRIVE.md). Canlı Google yüklemesi
hesap sahibinin OAuth izni olmadan yapılamaz; özellik varsayılan olarak kapalıdır.


## Geniş günlük seçki

Teknoloji 15–20, oyun 12–18 haber hedefler. Yeni `expanded-v1` yayınları en az
12 teknoloji / 10 oyun haberini ve ayrı olay kimliklerini doğrular; yetersiz
kaynakla sayı doldurulmaz. İlk beş haber büyük kart, kalanı kompakt karttır.
Sekizer haber gösterilir, kategori filtresi ve Daha fazla göster düğmesi vardır.

Yeni Sekme 15–20, Moradon FM 12–18 dakika hedefler. Senaryo 5–7 konu etrafında
kurulur; yazım, editörlük ve bağımsız kaynak denetimi sürer. Yeni format için
minimum gerçek ses süreleri 900 / 720 saniyedir. Gemini ses yöntemi ve iki özel
ses kimliği değişmez; tamamlanan WAV parçaları senaryo/model/ses kimliğine
bağlı SHA-256 anahtarıyla yeniden kullanılır. Eski mühürlü kısa yayınlar kendi
sözleşmeleriyle doğrulanabilir.

Yayın günü sınırı tüm katmanlarda İstanbul 06:00’dır. Gece 00:00–05:59 arasında yapılan düzeltme önceki yayın tarihini korur; 06:00’da eski tarihli derleme, senkronizasyon ve push reddedilir. Yeni yayın için 07:30 alt sınırı ayrıca korunur.

Başarılı canlı doğrulamadan sonra geçici Actions çıktıları sınırlandırılır: güncel dağıtım paketi, en yeni iki tarihin son devam kaydı ve son iki tarayıcı test kanıtı korunur. Kaynak deposu, yayın dosyaları ve Drive arşivleri bu temizlikte değiştirilmez. Tamamlanmış MP3’ler doğrulandıktan sonra ham TTS parçaları devam kaydından çıkarılır; yarım üretimler korunur.

Zamanlama boş runner bekletmez: 06:00 yalnız matbaa durumunu hazırlar, 06:15 üretim başlar. Erken tamamlanan iki yayın özel devam kaydında saklanır; 07:30 çalışması bu kaydı doğrulayıp derler ve yayımlar. 06:20 ve 08:00 tekrarları kurtarma içindir. Hiçbir sabah aşaması 07:30’u çalışan runner içinde uyuyarak beklemez; erken yayın ve sonraki 06:00 sınırı korunur.
