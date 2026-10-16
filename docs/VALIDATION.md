# Doğrulama kaydı — 16 Ekim 2026

Bu kayıt yerel bulut makinesi ve PR üzerindeki gerçek GitHub Actions kalite
çalışmalarını kapsar. Canlıya geçiş veya Pages dağıtımı yapıldığı iddiası değildir.

| Kontrol | Sonuç |
|---|---|
| Python 3.12 / FFmpeg / ffprobe / bağımlılıklar | Hazır; pip check başarılı. |
| Python unittest | **50 geçti**, başarısız/atlanan test yok. |
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
| Pages HTTP doğrulayıcısı | Hazır ve hazırlık durumları test edildi; eski HTML veya değiştirilmiş MP3 baytları reddediliyor. Gerçek canlı dağıtım 38907695793 koşusunda başarıyla doğrulandı. |
| Actions YAML | Yeni iki workflow actionlint v1.7.7 ile başarılı; dağıtım composite ve bütün shell blokları ayrıca sözdizimi kontrolünden geçti. |
| Mevcut Gemini yöntemi | Mock sağlayıcı + gerçek FFmpeg ile başarılı WAV yolu ve iki özel ses ID'si doğrulandı; yeni strict modda ses dışı yanıt reddedildi. Eski üreticinin tip bilgisi olmayan WAV yanıtıyla uyumluluğu ayrıca korundu ve sınandı. Bunlara ek olarak gerçek GitHub dry-run iki podcast sentezini başarıyla tamamladı. |
| Eski akış uyumluluğu | Senaryo üreticisinin eski çağrı biçimi ve varsayılan Yeni Sekme prompt'u test edildi. Onaylı geçişten sonra Notion workflow/betikleri kaldırıldı; eski HTML girişleri yönlendirildi, doğrudan ses URL'leri korundu. |
| Public artifact / sırlar | Build yalnız web varlıklarını kopyalıyor; ham araştırma/senaryo/kaynak Python'ları dışarıda. Anahtar desenleri ve mevcut secret değerleri için engelleme test edildi. |
| Build tekrarı | Hazırlık build'i aynı komutla iki kez başarıyla çalıştı. |

Tarayıcı ekran görüntüleri `test-results/` altındadır; CI bu klasörü artifact
olarak yükler. Standart testler sentetiktir. `live-*-mobile.png` görüntüleri ise 16 Ekim
2026 gerçek Pages yayını üzerinden alınmıştır.

## Gerçek canlı geçiş — 16 Ekim 2026

- Kullanıcı canlı geçişi ve ardından Notion temizliğini açıkça onayladı. Kod kapısı
  PR #4 ile açıldı; kullanıcı `PULSE_LIVE_APPROVED=true` ve hedef Pages
  Source=GitHub Actions ayarlarını tamamladı. App özel anahtarı yalnız Secrets'ta.
- [App erişim testi](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38907291864)
  token oluşturmayı, hedef depo okumasını ve Contents yazma yetkisini doğruladı.
- [İlk canlı yayın](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38907695793)
  plan, gate, generate ve publish işlerinin tamamında başarılı. Gerçek Pages
  HTML, manifest, iki JSON ve dört MP3 baytları/hash'leri doğrulandı.
- Sürüm: `2026-10-16-75d6476f03155fb9`. İki bölüm de Sayı 001. Teknoloji 5,
  oyun 6 haber. Mobil 390 px gerçek yayında taşma ve JavaScript hatası yok;
  ana sayfada yalnız iki yayın kartı, haber veya oynatıcı yok.
- Dört gerçek ses tarayıcıda oynatıldı; oynatma zamanı ilerledi. Süreler:
  teknoloji özeti 178,920 sn / Yeni Sekme 230,230 sn; oyun özeti 240,024 sn /
  Moradon FM 247,590 sn. Yerel Chromium'un bulut proxy CA deposu farkı test
  bağlamında ele alındı; üretim TLS doğrulaması ve gerçek Pages kontrolü açıktır.
- PR #5 ile eski Notion workflow/betikleri ve kaynaksız pilot JSON kaldırıldı,
  eski HTML adresleri yeni köke/teknolojiye yönlendirildi. Eski MP3 doğrudan
  bağlantıları korunur. Günlük cron artık varsayılan açık;
  `PULSE_AUTOMATION_ENABLED=false` ile durdurulur.
- İlk canlı işte `.pulse-work/` gizli klasörü artifact filtresine takıldı; bu
  ara kayıt eksikliği canlı çıktıyı etkilemedi. PR #5 `include-hidden-files:true`
  ekler; tekrar çalışma yayımlanmış JSON/MP3 üzerinden de geri dönebilir.

- [Gerçek aynı gün tekrarı](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38908982331)
  dört işte de başarılı. Sayı 001 ve `2026-10-16-75d6476f03155fb9` sürümü
  korunur; yayımlanan dosyalar üzerinden geri dönüş ve tekrar doğrulama çalışır.
  `pulse-state-2026-10-16-38908982331-1` artifact'ı gerçekten oluştu
  (9.892.080 bayt); gizli klasör düzeltmesi hosted ortamda doğrulandı.
- Üç eski HTML adresinin yeni köke/teknolojiye yönlenmesi gerçek tarayıcıda
  doğrulandı; hedef `data/` altında yalnız `publication.json` kaldı.

## Kalan gözlem

İlk gerçek ertesi sabah 06.00 kapanışı ve 07.30/gerçek hazır olma açılışı
henüz yaşanmadı. Bu geçişler 14 Node ve 19 tarayıcı kontrolünde sınandı;
gelecekteki cron koşusunun zamanında başlayacağı iddia edilmez. GitHub cron
gecikebilir; hazır ve güncel çift yayın yoksa site matbaa ekranında kalır.

Bulut makinesine Gemini anahtarı kopyalanmadı; gerçek üretim mevcut GitHub
Secret ile çalıştı. GitHub yönetim API'si Secrets/Variables/Pages ayarı
değişikliklerine 403 verdiğinden yalnız bu hesap ayarları kullanıcı tarafından
yapıldı. Site çıktısına anahtar veya ham senaryo aktarılmadı.

## Mobil tasarım ve yeni ses akışı — 16 Ekim 2026

- PR #7 ile sade PULSE/pembe nokta markası, kırpılmayan MMORPG/bilim kapakları,
  özel erişilebilir oynatıcılar ve açılışta matbaa parlamayan doğrulama uygulandı.
- Yerel ve hosted kontroller: 62 Python, 14 Node ve 23 Chromium senaryosu.
  Yavaş manifestte sıfır matbaa açılışı, ses hızı/ses seviyesi/arama/sessize alma,
  tek aktif oynatıcı ve mobil/yatay ölçüler kapsandı.
- İlk gerçek prova kısa ama geçerli diyaloğu eski 10 sıra sınırı yüzünden reddetti.
  PR #8 redakte edilmiş üretim hatalarını check annotation'larında görünür yaptı;
  PR #9 sınırı gerçek karşılıklı konuşma için dört sıraya indirdi. Tam MP3
  çözümleme ve en az 40 sn podcast kontrolü korundu.
- Eski teknoloji seçkisindeki iki açık oyun kategorili haber ayıklandı; yeni
  seçkiler `content_revision=2` ile bu karışımı engeller. Tarih ve sayı korunur.
- [Yeni gerçek ses provası](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38925720523)
  başarılı: plan/generate geçti; gate/publish deneme modunda atlandı. Kısa,
  yorumsuz Edge özetleri ve ayrı editör/kaynak denetiminden geçen Gemini
  sohbetleri aynı mevcut özel ses kimlikleriyle üretildi.
- Son beş tarayıcı artifact'ı korunarak 26 eski görsel artifact temizlendi.
  Geçici site/state çıktıları 2, tarayıcı çıktıları 3 gün saklanır; kalıcı
  `releases/` arşivi etkilenmez.

Bu kayıt otomatik doğruluk denetiminin hatasız olduğunu veya seslerin insan
tarafından dinlenip öznel olarak onaylandığını iddia etmez. Denetim kaynak
notlarına ve mevcutsa ham RSS kanıtına dayanır; onaysız senaryo seslendirilmez.

### Yeni sürümün gerçek canlı doğrulaması

[Canlı dağıtım](https://github.com/YasarGny/pulse-otomasyon/actions/runs/38926680182)
plan, gate, generate ve publish işlerinin tamamında başarılı. Aktif sürüm
`2026-10-16-4b2087cf3d367151`; teknoloji 3, oyun 6 haber, ikisi de Sayı 001 ve
`audio_revision=3`. Dört MP3 gerçek Pages yanıtından boyut/SHA-256 ile doğrulandı.

- Teknoloji özeti 35,5 sn; Yeni Sekme 136,8 sn.
- Oyun özeti 75,7 sn; Moradon FM 123,0 sn.
- Gerçek HTTPS sitede 390 px / 2× piksel yoğunluğunda üç sayfada sıfır matbaa
  parlaması ve yatay taşma; GitHub dış bağlantısı yok.
- Dört oynatıcı da gerçek MP3'le oynatma, arama, hız, ses, sessize alma ve
  duraklatma kontrollerini geçti. JavaScript çalışma hatası yok.
- Canlı ekran görüntüleri `test-results/final-live-*-mobile.png` altında.
- Ek olarak kaynak depodaki 30 kullanılmayan eski Pages artifact'ı silindi.
  Toplam 56 eski çıktı kaldırıldı; ölçülen geçici depolama 416 MB'den 156 MB'ye
  indi. Hedef deponun çalışan Pages artifact/iş akışına dokunulmadı.
- Kaynak private, yayın deposu public; eski proje URL'si HTTP 404. GitHub'ın
  yönetilen eski Pages kaydı API yetkisi nedeniyle kapatılamadı (403/422);
  kaynak Settings → Pages'de bir site hâlâ görünüyorsa hesap sahibi Unpublish
  site seçebilir. Bu platform kaydı site kaynaklarında bir workflow dosyası değildir.

Gerçek ertesi sabah döngüsü bu turda yaşanmadı; saat/kilit davranışı otomatik
kontrollerde sınandı. Yeni seslerin öznel doğallığı için insan dinleme onayı
iddia edilmez; kaynak/editör kapısı ve gerçek teknik oynatma doğrulanmıştır.

### 16.10.2026 — kompakt oynatıcı, haber ayrıntıları ve Drive hazırlığı

- Yerel doğrulama: 78 Python testi, 14 Node kontrolü, 26 Chromium kontrolü;
  ayrıca actionlint ve git diff --check başarılı.
- Tarayıcı turu 320–1440 px, yatay telefon, axe, sekmelerin klavye kullanımı,
  kaynaklı ayrıntı sayfası, 10 saniye atlama ve altı hızın tam döngüsünü kapsar.
- Çıkarılmış arşivde ağ kapalıyken ana sayfa, haberler, yerel resimler, ayrıntılar
  ve MP3 oynatımı geçti. Bu bulut Chromium politikası file:// gezinmesini engelledi;
  bu nedenle yerel testte dosyalar bellekten bir origin altında sunuldu. Burada
  doğrudan file:// testinin geçtiği iddia edilmez.
- Yedek bozulması, eksik resim, Drive geri okuma uyuşmazlığı ve eksik makbuzun
  temizliği engellemesi sınandı. Aynı gün hazırlık yeniden çalıştırıldığında
  ayrıntı rotaları ve mevcut sayı korunur.
- Gerçek yayın verisiyle yerel önizleme: teknoloji 3, oyun 6 haber. Kaynaklardan
  teknoloji için 2/3, oyun için 6/6 görsel bilgisi bulundu. Bir The Verge sayfası
  bu ortamdan HTTP 403 döndürdü; görsel uydurulmadı. DNS ve bazı dış resim istekleri
  de bu bulut ağında kısıtlı; gerçek Pages/CDN yayını ayrıca kontrol edilmelidir.
- Bu revizyon canlıya gönderilmedi. Yeni tasarım ve yeni silme davranışı sahibin
  son onayını bekler. Google hesabına gerçek Drive yüklemesi ve zamanlanmış yedek
  OAuth kurulmadan doğrulanmış sayılmaz. Git geçmişi yeniden yazılmadı.
