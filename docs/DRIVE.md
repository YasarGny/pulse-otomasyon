# Özel Drive yedeği

Yedekler `PULSE/2026/10/16.10.2026/PULSE-16.10.2026-<yayın-kimliği>.zip` biçimindedir. Sayfalarda da tarih `16.10.2026` görünür; manifest tarihleri hesaplama uyumluluğu için ISO olarak saklanır.

ZIP'i indirip çıkardıktan sonra **index.html** dosyasını tarayıcıda açın. İnternet olmadan haberler, ayrıntı sayfaları, kaynak bağlantıları, yerel görseller ve dört ses dosyası kullanılabilir. Drive HTML klasörlerini web sitesi olarak sunmaz; Drive önizlemesi canlı site gibi çalışmaz. Arşivde sabah kilidi ve ağdan JSON isteği yoktur. Kaynak bağlantılarını açmak internet gerektirir.

## Hesabınızdan gereken tek seferlik bağlantı

Sohbet Drive bağlantısı GitHub Actions'a kalıcı yetki vermez. Dar kapsamlı `drive.file` izni sadece bu uygulamanın oluşturduğu dosyalar içindir; bütün Drive'ınızı okumak istenmez. Anahtar veya token'ı sohbete göndermeyin.

1. [Google Cloud Console](https://console.cloud.google.com/) → üstte proje seçici → **New project** → `PULSE` → **Create**.
2. **APIs & Services → Library** → **Google Drive API** → **Enable**.
3. **Google Auth Platform → Branding** → **Get started**. Uygulama adı `PULSE`, destek e-postası kendi adresiniz. **Audience: External**; iletişim e-postanızı girin.
4. **Audience → Test users → Add users** ile kendi Google hesabınızı ekleyin. **Data Access → Add or remove scopes** içinde `https://www.googleapis.com/auth/drive.file` seçin.
5. **Clients → Create client → Application type: Desktop app** → `PULSE local setup` → **Create** → **Download JSON**. Bu dosyayı depoya koymayın.
6. **Audience → Publishing status → Publish app** ile **In production** yapın. Testing modundaki çevrimdışı yetki Drive kapsamı için genellikle yedi günde biter. Kendi hesabınızdaki kişisel kullanımda Google doğrulanmamış uygulama uyarısı gösterebilir; yalnız kendi oluşturduğunuz istemciyi onaylayın. Yayın durumunun değişmesi PULSE web sitesini canlıya almaz.
7. Kendi bilgisayarınızda kaynak depoyu açın. Python, GitHub CLI ve `requests` gereklidir. Terminalde:

   ```sh
   gh auth login
   python -m pip install requests
   python scripts/connect_drive.py --client-file "/indirilen/dosyanin/tam/yolu.json"
   ```

   Açılan Google penceresinde kendi hesabınızla onaylayın. Betik özel `PULSE` klasörünü oluşturur, aşağıdaki ayarları doğrudan GitHub'a yazar ve anahtarları ekrana basmaz. Bağlantı kodu alınamazsa beş dakikada kapanır.
8. [Actions](https://github.com/YasarGny/pulse-otomasyon/actions/workflows/drive-backup.yml) → **Run workflow**. **Verify private Drive backup** başarılı olmalı; Drive'daki ZIP'i indirip `index.html` dosyasını açarak kontrol edin. Bu prova dosya silmez.
9. Başarılı provadan sonra [Actions variables](https://github.com/YasarGny/pulse-otomasyon/settings/variables/actions) → `PULSE_DRIVE_ENABLED` → **Edit** → `true` → **Save**. Bu, günlük yedeklemeyi ve yalnız doğrulanmış eski yayın klasörlerinin temizliğini etkinleştirir. Başarısızlıkta kapalı bırakın.

Kaydedilen Secrets: `PULSE_DRIVE_CLIENT_ID`, `PULSE_DRIVE_CLIENT_SECRET`, `PULSE_DRIVE_REFRESH_TOKEN`. Variables: `PULSE_DRIVE_FOLDER_ID`, başlangıçta `PULSE_DRIVE_ENABLED=false`. Betik kullanılamıyorsa aynı adlarla repo **Settings → Secrets and variables → Actions** altında eklenir; refresh token'ı oluşturmak için yine OAuth onayı gerekir.

## Saklama ve bütünlük

Her ZIP içinde dosya boyutları ve SHA-256 envanteri bulunur. Yükleme tamamlandıktan sonra dosya Drive'dan tamamen geri okunur; boyut ve SHA-256 tutmazsa temizleme makbuzu üretilmez. Var olan yedek tekrar kullanılırken yeniden indirilir, envanter, asıl haber JSON'ları ve dört MP3 karşılaştırılır. Aynı tarihin yeniden denemesi yeni sayı oluşturmaz. Eksik görsel indirmesi yedeği durdurur; dosya yok sayılarak başarılı ilan edilmez.

Günlük dağıtımda Drive etkinse yedekleme senkronizasyondan önce yapılır. Yedekleme başarısızsa dağıtım/temizleme durur; mevcut dosyalar korunur. En yeni iki yayın tarihi ve aktif yayın GitHub'da kalır. Silinen yayınların kaynak URL özetleri küçük bir tekrar önleme defterine aktarılır. Drive'dan hiçbir eski yedek otomatik silinmez.

**Git geçmişi:** Klasör temizliği çalışma ağacını küçültür; eski MP3 Git nesnelerini küçültmez. Kalıcı boyut azaltma için yayın deposunu yalnız güncel anlık görüntüler tutacak bir dala geçirmek ve eski geçmişi kaldırmak gerekir. Bu geri dönüşü etkileyen ayrı bir geçiştir: tüm Drive yedekleri doğrulanmadan, depo yedeği alınmadan ve sahibinden ayrıca açık onay gelmeden geçmiş yeniden yazılmaz. Bu sürüm force-push veya eski Git geçmişini silme yapmaz.
