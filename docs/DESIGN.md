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
seçilir. Hiçbir yayın kapağı veya haber görseli `object-fit:cover` ile kırpılmaz;
tüm kare doğal oranıyla görünür. Yakınlaştıran hover animasyonu yoktur. Orijinal
üretim PNG'leri çalışma alanında saklanır; büyük PNG'ler public build'e alınmaz.
Sosyal görsel aynı kapaklardan `node scripts/render_og.cjs` ile yeniden üretilebilir.

## Ses ve hareket

Özel, klavyeyle kullanılabilen oynatıcı: oynat/duraklat, 15 saniye ileri/geri,
ilerleme, 0,75–2× hız, ses ve sessize alma. Aynı anda tek ses çalar. MP3'ler kullanıcı
başlatmadan indirilmez (`preload=none`). Mobil Safari gibi tarayıcılar programatik
ses seviyesi değişimini sınırlandırabilir; cihazın ses düğmeleri geçerlidir.

Hazır yayında ilk gezinmede matbaa gösterilmez. Kısa doğrulama boyunca nötr zemin
ve yalnız uzayan istekte PULSE yükleme işareti vardır. Gerçek hazırlık durumunda
inceleme kâğıdı, baskı taraması ve katmanlı kâğıt görseli; bağlantı hatasında ayrı
hata görünümü bulunur. Sayı/saat/JSON/MP3 doğrulaması atlanmaz. Animasyonlar yalnız
opacity/transform ağırlıklıdır ve `prefers-reduced-motion` ile kapanır.

## Doğrulama ve yayın

320 px telefon, farklı mobil ölçüler, tablet, masaüstü ve yatay telefon sınanır.
Gerçek MP3 oynatımı, hız/ses/arama, tek oynatıcı, yavaş manifestte sıfır matbaa
parlaması ve gerçek sabah kilidi tarayıcı testlerinde yer alır. axe erişilebilirlik
kontrolleri ana sayfa, yayınlar ve hazırlık ekranını kapsar. Önizleme görüntüleri
`test-results/` altında ve PR kalite artifact'ındadır. Canlı ses değişikliği önce
hosted dry-run ile, ardından dört dosyanın gerçek Pages hash kontrolüyle doğrulanır.
