# RIGLAB — Manuel PC sistem kataloğu

Bütçe aralıklarına uygun sistemleri kendin hazırlayabilirsin. Parça adlarını, fiyatlarını ve Akakçe ürün bağlantılarını yönetim ekranından gir; site kullanıcının bütçesine uyan yayınlanmış kaydı önerir.

Varsayılan akış **manuel** çalışır. Akakçe’den otomatik fiyat veya stok sorgulanmaz. Kayıtlı fiyatlar açıkça elle girilmiş olarak gösterilir; otomatik uyumluluk kontrolü yapılmış gibi sunulmaz.

## Windows’ta başlat

1. Proje ZIP’ini **Tümünü Ayıkla** ile çıkar.
2. `BASLAT.cmd` dosyasının bulunduğu klasöre girip dosyaya çift tıkla.
3. Site açılınca üst menüden **Yönetim** bağlantısına tıkla.
4. **Yeni sistem** ekle; alanları doldurup **Kaydet ve yayınla** seç.

Başlatıcı kendi klasörüne geçer, `.venv` ortamını kurar ve siteyi boş bir yerel portta açar. Python kurulu ve PATH’te olmalı. İlk bağımlılık kurulumu internet gerektirir. Açılan terminali açık tut; kapatınca yerel site durur. Yönetici olarak başlatmak gerekmez.

Komut satırından kullanmak istersen proje klasöründe:

```bash
python -m pip install -r requirements.txt
python bot.py
```

Python 3.12 ve sonrası için hazırlanmıştır; önceki Windows/Python 3.15 kurulumu da temel bağımlılıkları yükleyebilmiştir. Windows başlatıcısı bu Linux geliştirme ortamında yerel Windows çalıştırmasıyla sınanamadı. Yerel Flask sunucusu, sayfalar ve gerçek tarayıcı akışı test edildi.

## Sistem ekleme

- Sistem adı ve alt/üst bütçe sınırlarını listeden seç. Seçenekler: **20.000, 30.000, 40.000, 50.000, 60.000, 70.000, 80.000, 90.000, 100.000, 120.000, 140.000, 160.000, 200.000 ve 250.000 TL**. Ziyaretçiler de yalnızca bu 14 tutardan birini seçebilir; serbest bütçe girişi ve kaydırıcı kaldırıldı. Parça fiyatları bu kısıtlamadan bağımsızdır.
- Hedef çözünürlüğü seç veya tüm çözünürlükler için yayınla.
- **Parçaları tek tek ekle:** işlemci, ekran kartı, anakart, RAM, SSD, PSU ve kasa için ad, fiyat ve HTTPS Akakçe ürün bağlantısı gir. İşlemci soğutucusu isteğe bağlıdır.
- **Tek bağlantıyla hazır sistem ekle:** hazır sistemin fiyatını ve Akakçe ürün bağlantısını gir.
- İlanları ve uyumluluğu kontrol ettiğini onayla. Not ekleyebilirsin.
- **Taslak kaydet** ile eksik kaydı sakla; taslaklar ziyaretçilere önerilmez.
- **Kaydet ve yayınla** ile tamamlanan kaydı önerilere dahil et.

Fiyatı sıfır girilen bir parça dahil/hediye ürün olarak kullanılabilir; yayındaki sistem toplamı pozitif olmalı. Yedi zorunlu parça tamamlanmadan veya toplam üst bütçeyi aşıyorsa parça sistemi yayınlanamaz.

Birden fazla sistem uyarsa önce yüksek **Öneri önceliği**, sonra daha yüksek alt bütçe sınırı seçilir. Kaydın aralığı, çözünürlüğü ve toplam tutarı kullanıcının bütçesine uymalıdır. Daha pahalı bir sistem veya taslak kayıt önerilmez. Hiç kayıt yoksa ürün ve fiyat uydurulmaz.

**Düzenle**, **Yayından kaldır / Yayınla** ve **Sil** işlemleri yönetim listesindedir. Başka bir pencerede değişen kaydın eski sürümüyle üzerine yazılması engellenir. Önceden kaydedilmiş farklı bütçe aralıkları silinmez; düzenleyicide önceki değer olarak korunur, yeni seçimler yalnızca listedeki tutarlardan yapılır.

## Kayıtlar ve yedek

Kayıtlar SQLite veritabanında saklanır:

- Windows: `%LOCALAPPDATA%\riglab\manual.sqlite3`
- Diğer sistemler: proje içindeki `data/manual.sqlite3`
- Özel kalıcı konum: `RIGLAB_DATA_DIR` ortam değişkeni

Windows’ta ZIP’i yeniden indirip farklı klasöre çıkarsan da aynı kullanıcı veri konumu kullanılır. `data/` Git’e eklenmez; kişisel katalog kaynak kodla paylaşılmaz.

**Yedek indir** bir JSON dosyası oluşturur. **Yedek yükle** kayıtları geri alır; aynı kimlikteki kayıtlar güncellenir. Yüklemeden önce arayüz onay ister. Geçersiz bir yedek, veritabanına kısmen yazılmaz. Başka bilgisayara veya sunucuya taşımak için bu dosyayı kullanabilirsin.

## İnternete açık kurulum

Yerel `bot.py` yalnızca `127.0.0.1` üzerinde dinler; bu bilgisayarda yönetim şifresiz kullanılabilir. Yayımlanan uygulamada bu yerel yetki açık değildir. Yönetim girişi için ortam ayarlarında `RIGLAB_ADMIN_PASSWORD` tanımlanır. Şifreyi kaynak koda veya sohbet mesajına yazma.

`RIGLAB_SESSION_SECRET` ile kalıcı bir oturum anahtarı ve HTTPS kurulumunda `RIGLAB_COOKIE_SECURE=1` kullan. Kataloğun silinmemesi için `RIGLAB_DATA_DIR` kalıcı diske işaret etmelidir. Aynı oturum anahtarını paylaşmayan birden fazla worker kullanılmamalıdır. Yönetim yazma işlemleri oturum ve CSRF doğrulaması gerektirir.

```bash
gunicorn --bind 127.0.0.1:10000 --workers 1 --threads 4 main:app
```

Siteyi yayımlamak veya mevcut kayıtları uzak sunucuya taşımak bu kod değişikliğinin parçası olarak yapılmadı.

## Doğrulama

```bash
python -m unittest discover -s tests -v
node --check static/app.js
node --check static/admin.js
```

63 test; bütçe hesabı, manuel yayın/taslak kuralları, fiyat/URL doğrulaması, öncelik ve çözünürlük seçimi, düzenleme çakışmaları, silme, yedekleme, parola/oturum ve CSRF kontrollerini içerir. Önceki isteğe bağlı otomatik kaynak testleri de korunur. Test kayıtları yalnızca geçici veritabanlarındadır; gerçek kataloğa örnek fiyat eklenmez.

Gerçek Chromium ile manuel ekranın baştan sona testi:

```bash
python -m pip install -r requirements-browser.txt
python tests/manual_browser.py --executable /usr/bin/chromium
```

Bu test geçici sunucu ve veritabanında parça/ilan girişi, taslak ve yayın, bütçeye göre sonuç, hazır sistem kaydı, mobil görünüm, dışa aktarma ve yeniden başlatmada kalıcılığı doğrular. Fiyat ağına erişim test sırasında özellikle kapatılır.

## İsteğe bağlı otomatik kaynaklar

Eski HTTP ve tarayıcı adaptörleri açıkça seçilirse kullanılabilir:

```bash
python bot.py --source http
python -m pip install -r requirements-browser.txt
python bot.py --source browser
```

Bunlar varsayılan değildir ve Akakçe’nin canlı erişimi doğrulanmış değildir. Önceki denemelerde 406/429 yanıtları alındı. TLS doğrulaması, robots kuralları ve kalıcı Retry-After beklemesi korunur; tarayıcı taklidi, CAPTCHA çözme veya erişim engeli aşma uygulanmaz. Manuel katalog bunlara bağımlı değildir.
