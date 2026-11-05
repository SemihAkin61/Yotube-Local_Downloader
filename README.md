# YouTube İndirici

Windows üzerinde çalışan, tarayıcı arayüzlü YouTube video ve ses indirici. Tek video veya oynatma listesini en fazla 1080p MP4 ya da 320 kbps MP3 olarak kaydeder. Dönüştürme, kaynak kalitesini yükseltmez.

## Gereksinimler

- Windows ve güncel Python 3; `py -3` komutu kullanılabilmeli. Kod en az Python 3.9 gerektirir; desteklenen güncel bir Python sürümü kullanın.
- FFmpeg: `ffmpeg` ve `ffprobe` komutları PATH üzerinden erişilebilir olmalı.
- Node.js 22 veya üzeri: `node` komutu PATH üzerinden erişilebilir olmalı. Uygulama Node.js'i otomatik bulup yt-dlp'ye bildirir.
- İnternet bağlantısı. yt-dlp, kurulum sırasında resmi GitHub sürümünden indirilir.
- İsteğe bağlı: `AC.vbs` ile penceresiz başlatmak için Python'un `pyw.exe` başlatıcısı (Python kurulumuyla birlikte gelir).

Python kodu yalnızca standart kütüphaneyi kullanır; `pip install` veya `requirements.txt` gerekmez. FFmpeg ve Node.js ayrı programlardır.

## Kurulum ve başlatma

1. Depoyu klonlayın veya ZIP olarak indirip bir klasöre çıkartın.
2. Python, FFmpeg ve Node.js'i kurduktan sonra yeni bir terminal açın. `py -3 --version`, `ffmpeg -version`, `ffprobe -version` ve `node --version` komutlarıyla kontrol edin.
3. `KURULUM.cmd` dosyasını çalıştırın. Bu işlem `.tools/yt-dlp.exe` dosyasını indirir veya günceller, hızlı (çok bağlantılı) indirme yardımcısını hazırlar; Python ve FFmpeg'i kontrol eder. Python, FFmpeg veya Node.js'i kendisi kurmaz ve Node.js'i kontrol etmez.
4. Uygulamayı başlatın (iki yol var):
   - **Önerilen — `AC.vbs`:** Terminal penceresi açmadan arka planda başlar ve siteyi tarayıcıda açar. Brave kuruluysa Brave'de, değilse Windows'un varsayılan tarayıcısında (Chrome, Edge, Firefox vb.) açılır.
   - **`BASLAT.cmd`:** Terminal penceresiyle başlar; hata ayıklarken kullanışlıdır. Terminal penceresini açık tutun.

### Masaüstü kısayolu

Kısayol otomatik oluşturulmaz. `AC.vbs` dosyasına sağ tıklayıp **Diğer seçenekleri göster → Gönder → Masaüstü (kısayol oluştur)** seçin. Bundan sonra masaüstündeki simgeye çift tıklamanız yeterlidir.

### Güncelleme

- `git clone` ile indirdiyseniz proje klasöründe `git pull` çalıştırın; yalnızca değişen dosyalar iner, `indirilenler/` klasöründeki dosyalarınız korunur.
- ZIP ile indirdiyseniz yeni ZIP'i indirip `indirilenler/` klasörünüzü yeni klasöre taşıyın.
- Her güncellemeden sonra `KURULUM.cmd` dosyasını **bir kez** yeniden çalıştırın.

## Kullanım

1. YouTube video veya oynatma listesi bağlantısını yapıştırıp **Bağlantıyı getir** düğmesine basın.
2. MP4 veya MP3 seçin; uygunsa tek video ya da tüm liste seçimini yapın.
3. **İndir** düğmesine basın. Sesler `indirilenler/mp3/`, videolar `indirilenler/mp4/` klasörüne kaydedilir. Dosya adlarında video kimliği bulunmaz; aynı isim varsa `(2)`, `(3)` eklenerek önceki dosya korunur. Önceden indirilmiş dosyalar mevcut konumlarında kalır.

Aynı anda bir indirme çalışır. Uygulamanın açık olduğu tüm sekmeler kapatılınca sunucu yaklaşık 8–12 saniye sonra durur; devam eden indirme ve dönüştürmeler de durdurulur. Tamamlanan dosyalar korunur.

## Sorun giderme

- Araçları güncellemek için `KURULUM.cmd` dosyasını yeniden çalıştırın.
- İndirme çalışmıyorsa FFmpeg ve Node.js'in PATH üzerinden bulunabildiğini kontrol edin.
- İndirme yavaşsa veya güncellemeden sonra sorun çıkıyorsa `KURULUM.cmd` dosyasını yeniden çalıştırın.
- `AC.vbs` hata verirse ayrıntıyı görmek için `BASLAT.cmd` ile başlatın.
- Özel, oturum gerektiren, canlı veya bölgesel kısıtlı içerikler her zaman indirilemeyebilir.
- Uygulama yalnızca `127.0.0.1` adresinde, kendi bilgisayarınızda çalışır.

Yalnızca kendi içeriklerinizi veya indirme izniniz olan içerikleri indirin.

Belgeler: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [JavaScript çalışma ortamı gereksinimleri](https://github.com/yt-dlp/yt-dlp/wiki/EJS), [FFmpeg](https://ffmpeg.org/download.html), [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/).

## Gizlilik ve yerel çalışma

Uygulama hesap, API anahtarı, cookie veya oturum anahtarı istemez ve bunları kaydetmez. İndirme geçmişi dosyaları `indirilenler/` altında yerel olarak kalır. Bu klasör, araçlar ve önbellek Git dışında tutulur. Arayüzün çalışması için güncel bir tarayıcı gerekir; tarayıcı isteklerinde aynı kaynak kontrolü uygulanır. Aynı bilgisayardaki diğer programlara karşı bir erişim sınırı sağlamaz. Aynı anda uygulamanın tek kopyasını çalıştırın. YouTube ve indirme araçlarının sunucularıyla ağ bağlantısı kurulur.
