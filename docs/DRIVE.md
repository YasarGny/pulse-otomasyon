# Özel Drive yedeği

Yedekler `PULSE/2026/10/16.10.2026/PULSE-16.10.2026-<yayın-kimliği>.zip` biçimindedir. Sayfalarda da tarih `16.10.2026` görünür; manifest tarihleri hesaplama uyumluluğu için ISO olarak saklanır.

ZIP'i indirip çıkardıktan sonra **index.html** dosyasını tarayıcıda açın. İnternet olmadan haberler, ayrıntı sayfaları, kaynak bağlantıları, yerel görseller ve dört ses dosyası kullanılabilir. Drive HTML klasörlerini web sitesi olarak sunmaz; Drive önizlemesi canlı site gibi çalışmaz. Arşivde sabah kilidi ve ağdan JSON isteği yoktur. Kaynak bağlantılarını açmak internet gerektirir.

## Tarayıcıdan kurulum — indirme veya terminal yok

GitHub günlük yüklemeyi kendi yapar. Google hesabına bir kez tarayıcıdan izin
vermeniz gerekir; GitHub hesabı tek başına Google Drive erişimi sağlamaz.
Sohbet Drive bağlantısı da Actions'a kalıcı yetki vermez. `drive.file` kapsamı
uygulamanın oluşturduğu dosyalarla sınırlıdır; tüm Drive'ınızı okumak istenmez.
**Client secret veya refresh token'ı sohbete, Issues'a ya da dosyalara yapıştırmayın.**

### 1. Google tarafında uygulama

1. [Google Cloud Console](https://console.cloud.google.com/) → üstte proje seçici → **New project** → `PULSE` → **Create**. Önceden PULSE projesi oluşturduysanız onu seçin.
2. **APIs & Services → Library** → **Google Drive API** → **Enable**.
3. **Google Auth Platform → Branding → Get started**. Ad `PULSE`, destek ve iletişim e-postası kendi adresiniz. **Audience: External**.
4. **Audience → Test users → Add users** ile kendi Google hesabınızı ekleyin. **Data Access → Add or remove scopes** içinde `https://www.googleapis.com/auth/drive.file` seçin.
5. **Audience → Publishing status → Publish app** ile **In production** yapın. Testing modunda Drive kapsamındaki refresh token genellikle yedi günde biter. Bu işlem web sitesini yayınlamaz; OAuth yetkisinin süresini ilgilendirir.
6. **Clients → Create client → Application type: Web application** → ad `PULSE GitHub backup`. **Authorized redirect URIs → Add URI** alanına tam olarak `https://developers.google.com/oauthplayground` yazın. **Create** düğmesine basın.
7. Açılan penceredeki **Client ID** ve **Client secret** değerlerini aşağıdaki iki yerde kullanın. **JSON indirmeniz gerekmiyor.** Secret yalnız oluşturulurken gösterilebilir; güvenli biçimde doğrudan GitHub Secret alanına kopyalayın.

### 2. Google iznini tarayıcıdan verin

1. [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) sayfasını açın.
2. Sağ üstte dişliye basın → **Use your own OAuth credentials** kutusunu işaretleyin → kendi **OAuth Client ID** ve **OAuth Client secret** değerlerinizi girin. **Access type: Offline** olmalı. Pencereyi kapatın.
3. Solda **Step 1** altındaki **Input your own scopes** alanına `https://www.googleapis.com/auth/drive.file` yapıştırın → **Authorize APIs**.
4. Yedeklerin tutulacağı kendi Google hesabını seçip izin verin. Kendi oluşturduğunuz uygulama için doğrulanmamış uygulama ekranı çıkarsa uygulama adını/hesabı kontrol edin; yalnız kendi PULSE uygulamanız için devam edin.
5. **Step 2 → Exchange authorization code for tokens** düğmesine basın. Görünen **Refresh token** değerini GitHub Secret'a kopyalayın; **Access token** değerini kullanmayın.

**Kendi OAuth istemcinizi kullanmak zorunlu:** Playground'un varsayılan istemcisiyle
alınan refresh token yaklaşık 24 saat sonra iptal edilebilir. Kendi istemciniz ve
Production durumu günlük otomasyon içindir. Google hesabınızdan erişimi kaldırmak
veya istemciyi silmek yedeklemeyi durdurur; bu durumda dosya temizliği de durur.

### 3. GitHub Secrets ve prova

1. [Repo Actions Secrets](https://github.com/YasarGny/pulse-otomasyon/settings/secrets/actions) → **New repository secret**. Aşağıdaki üç kaydı tek tek oluşturun:

   | Name | Secret değeri |
   | --- | --- |
   | `PULSE_DRIVE_CLIENT_ID` | Google Client ID |
   | `PULSE_DRIVE_CLIENT_SECRET` | Google Client secret |
   | `PULSE_DRIVE_REFRESH_TOKEN` | Playground Step 2 Refresh token |

2. [Drive yedek provası](https://github.com/YasarGny/pulse-otomasyon/actions/workflows/drive-backup.yml) → **Run workflow → Branch: main → Run workflow**.
3. GitHub özel Drive'ınızda **PULSE** klasörünü otomatik oluşturur, tarihli ZIP'leri yükler ve tamamını geri okuyup doğrular. Klasörü elle oluşturmanız veya klasör ID'si girmeniz gerekmez.
4. Prova yeşil olduğunda Drive'daki ZIP'i kontrol edin. Bu aşamaya kadar hiçbir GitHub yayını silinmez. Arşiv dosyasını kendi tarayıcınızda incelemek için ZIP'i indirip çıkarmak gerekir; **bağlantı kurulumu için indirme gerekmez**.
5. [Actions variables](https://github.com/YasarGny/pulse-otomasyon/settings/variables/actions) → **New repository variable** → Name: `PULSE_DRIVE_ENABLED`, Value: `true` → **Add variable**. Varsa **Edit → true → Save**. Böylece günlük yedekleme ve yalnız doğrulanmış eski yayın klasörlerinin temizliği etkinleşir. Prova başarısızsa etkinleştirmeyin.

İsterseniz `PULSE_DRIVE_FOLDER_ID` değişkeniyle uygulamanın oluşturduğu bir klasörü
sabitleyebilirsiniz; zorunlu değildir. Mevcut yerel OAuth betiği isteğe bağlı alternatif
olarak korunur; yukarıdaki tarayıcı yolunda kullanılmaz.

## Saklama ve bütünlük

Her ZIP içinde dosya boyutları ve SHA-256 envanteri bulunur. Yükleme tamamlandıktan sonra dosya Drive'dan tamamen geri okunur; boyut ve SHA-256 tutmazsa temizleme makbuzu üretilmez. Var olan yedek tekrar kullanılırken yeniden indirilir, envanter, asıl haber JSON'ları ve dört MP3 karşılaştırılır. Aynı tarihin yeniden denemesi yeni sayı oluşturmaz. Eksik görsel indirmesi yedeği durdurur; dosya yok sayılarak başarılı ilan edilmez.

Günlük dağıtımda Drive etkinse yedekleme senkronizasyondan önce yapılır. Yedekleme başarısızsa dağıtım/temizleme durur; mevcut dosyalar korunur. En yeni iki yayın tarihi ve aktif yayın GitHub'da kalır. Silinen yayınların kaynak URL özetleri küçük bir tekrar önleme defterine aktarılır. Drive'dan hiçbir eski yedek otomatik silinmez.

**Git geçmişi:** Klasör temizliği çalışma ağacını küçültür; eski MP3 Git nesnelerini küçültmez. Kalıcı boyut azaltma için yayın deposunu yalnız güncel anlık görüntüler tutacak bir dala geçirmek ve eski geçmişi kaldırmak gerekir. Bu geri dönüşü etkileyen ayrı bir geçiştir: tüm Drive yedekleri doğrulanmadan, depo yedeği alınmadan ve sahibinden ayrıca açık onay gelmeden geçmiş yeniden yazılmaz. Bu sürüm force-push veya eski Git geçmişini silme yapmaz.
