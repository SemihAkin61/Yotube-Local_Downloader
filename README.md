# YouTube İndirici

Windows üzerinde çalışan, tarayıcı arayüzlü YouTube video ve ses indirici. Tek video veya oynatma listesini en fazla 1080p MP4 ya da 320 kbps MP3 olarak kaydeder. Dönüştürme, kaynak kalitesini yükseltmez.

## Gereksinimler

- Windows ve güncel Python 3; `py -3` komutu kullanılabilmeli. Kod en az Python 3.9 gerektirir; desteklenen güncel bir Python sürümü kullanın.
- FFmpeg: `ffmpeg` ve `ffprobe` komutları PATH üzerinden erişilebilir olmalı.
- Node.js 22 veya üzeri: `node` komutu PATH üzerinden erişilebilir olmalı. Uygulama Node.js'i otomatik bulup yt-dlp'ye bildirir.
- İnternet bağlantısı. yt-dlp, kurulum sırasında resmi GitHub sürümünden indirilir.
- İsteğe bağlı: `AC.vbs` ile penceresiz başlatmak için Brave ve Python'un `pyw.exe` başlatıcısı.

Python kodu yalnızca standart kütüphaneyi kullanır; `pip install` veya `requirements.txt` gerekmez. FFmpeg ve Node.js ayrı programlardır.

## Kurulum ve başlatma

1. Depoyu klonlayın veya ZIP olarak indirip bir klasöre çıkartın.
2. Python, FFmpeg ve Node.js'i kurduktan sonra yeni bir terminal açın. `py -3 --version`, `ffmpeg -version`, `ffprobe -version` ve `node --version` komutlarıyla kontrol edin.
3. `KURULUM.cmd` dosyasını çalıştırın. Bu işlem `.tools/yt-dlp.exe` dosyasını indirir veya günceller; Python ve FFmpeg'i kontrol eder. Python, FFmpeg veya Node.js'i kendisi kurmaz ve Node.js'i kontrol etmez.
4. `BASLAT.cmd` dosyasını çalıştırın. Varsayılan tarayıcıda http://127.0.0.1:8765 açılır; terminal penceresini açık tutun.

Brave kullanıyorsanız `AC.vbs` alternatif olarak uygulamayı arka planda açar. Masaüstü kısayolu kurulumla otomatik oluşturulmaz.

## Kullanım

1. YouTube video veya oynatma listesi bağlantısını yapıştırıp **Bağlantıyı getir** düğmesine basın.
2. MP4 veya MP3 seçin; uygunsa tek video ya da tüm liste seçimini yapın.
3. **İndir** düğmesine basın. Dosyalar `indirilenler/` altında işlem klasörlerine kaydedilir.

Aynı anda bir indirme çalışır. Uygulamanın açık olduğu tüm sekmeler kapatılınca sunucu yaklaşık 8–12 saniye sonra durur; devam eden indirme ve dönüştürmeler de durdurulur. Tamamlanan dosyalar korunur.

## Sorun giderme

- Araçları güncellemek için `KURULUM.cmd` dosyasını yeniden çalıştırın.
- İndirme çalışmıyorsa FFmpeg ve Node.js'in PATH üzerinden bulunabildiğini kontrol edin.
- Özel, oturum gerektiren, canlı veya bölgesel kısıtlı içerikler her zaman indirilemeyebilir.
- Uygulama yalnızca `127.0.0.1` adresinde, kendi bilgisayarınızda çalışır.

Yalnızca kendi içeriklerinizi veya indirme izniniz olan içerikleri indirin.

Belgeler: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [JavaScript çalışma ortamı gereksinimleri](https://github.com/yt-dlp/yt-dlp/wiki/EJS), [FFmpeg](https://ffmpeg.org/download.html), [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/).

## Gizlilik ve yerel çalışma

Uygulama hesap, API anahtarı, cookie veya oturum anahtarı istemez ve bunları kaydetmez. İndirme geçmişi dosyaları `indirilenler/` altında yerel olarak kalır. Bu klasör, araçlar ve önbellek Git dışında tutulur. Arayüzün çalışması için güncel bir tarayıcı gerekir; tarayıcı isteklerinde aynı kaynak kontrolü uygulanır. Aynı bilgisayardaki diğer programlara karşı bir erişim sınırı sağlamaz. Aynı anda uygulamanın tek kopyasını çalıştırın. YouTube ve indirme araçlarının sunucularıyla ağ bağlantısı kurulur.
