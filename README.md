# RIGLAB

Oyun odaklı, yalnızca kasa içeren bir PC toplama prototipi. Kullanıcı 15.000–150.000 TL bütçe ve 1080p / 1440p / 4K hedefi seçer. Flask API, sınırlı bir parça kataloğundaki eksiksiz ve uyumlu kombinasyonları değerlendirir. Sonuçta yedi parça, toplam tutar, kalan bütçe, fiyat kontrol zamanı ve Akakçe ürün sayfaları gösterilir.

## Geliştirme

### Kendi bilgisayarında bot.py ile kullan

`bot.py` bu projenin dosyalarıyla birlikte çalışır. Tek başına başka bir klasöre kopyalama. Site ve fiyat botu kendi bilgisayarında çalıştığında Akakçe istekleri de o bilgisayarın internet bağlantısından gider. Uzak sunucuya yayımlanan site, ziyaretçinin bağlantısını kendiliğinden kullanmaz. Proxy ayarları ve TLS doğrulaması değiştirilmez.

**Windows'ta önerilen başlangıç:** ZIP'i tamamen çıkar, `BASLAT.cmd` dosyasının bulunduğu klasöre gir ve dosyaya çift tıkla. Başlatıcı kendi klasörüne geçer, `.venv` oluşturur, sabitlenmiş bağımlılıkları kurar ve siteyi boş bir yerel portta açar. Python kurulu ve PATH'te olmalı; Edge veya Chrome da kurulu olmalıdır. Terminali açık tut. İlk bağımlılık kurulumu zaman alabilir.

Bu başlatıcı `--source browser` kullanır: fiyat okuma sırasında ayrı bir Edge/Chrome penceresi açılır; JavaScript ile oluşan DOM okunur. Kişisel tarayıcı profili, giriş bilgileri veya çerezler kopyalanmaz. Tarayıcı gerçek kimliğine `Riglab/0.1` ekleyerek kendini açıkça tanıtır. TLS ve proxy ayarları korunur; robots.txt ve aynı kalıcı bekleme kuralları uygulanır. HTTP reddi, 429 veya doğrulama ekranında işlem durur. Bu mod bir erişim engelini kaldırma garantisi değildir; **gerçek Akakçe verileriyle başarı henüz doğrulanmadı**.

46 birim testine ek olarak gerçek Chromium'da, yalnızca sentetik yerel yanıtlarla, JavaScript ürünlerinin yedi parçalı sisteme dönüşmesi ve 429 sonrası tarayıcı açılmasının durması doğrulandı. Playwright ve bağımlılıklarının Windows/Python 3.15 için hazır wheel dosyaları bulunduğu kontrol edildi. `BASLAT.cmd` bu Linux ortamında yerel Windows çalıştırmasıyla sınanamadı.

Tarayıcı modunu komut satırından kullanmak için:

```bash
python -m pip install -r requirements-browser.txt
python bot.py --source browser --port 0
```

Başlatıcıyı kullanmayanlar için normal HTTP yolu aşağıdadır:

Windows / PowerShell, Python 3.12 kurulu olduğunda proje klasöründe:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe bot.py
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bot.py
```

Bot yerel siteyi başlatıp tarayıcıyı açar. Bütçeni siteden gir. Yalnızca kendi bilgisayarından erişilebilen sunucu, terminali kapatınca / Ctrl+C ile durur. Port doluysa `python bot.py --port 0`; otomatik tarayıcı istemezsen `--no-browser` kullan.

Terminalde parçaları, fiyatları ve ürün bağlantılarını görmek için:

```bash
python bot.py --budget 40000 --resolution 1440p
python bot.py --budget 40000 --resolution 1440p --output sistem.json
```

Buradaki `python`, yukarıdaki sanal ortamın Python çalıştırıcısı olmalıdır. Çıktı dosyası varsa üzerine yazılmaz. Gerçek fiyat bulunamazsa bot hata verir; sistem veya fiyat uydurmaz. Yerel çalıştırma, Akakçe'nin otomatik erişime izin vereceğini veya mevcut ayrıştırıcının gerçek sayfalarla uyumlu olduğunu garanti etmez. Canlı kaynak doğrulaması hâlâ gereklidir.

### Doğrudan uygulamayı başlatma

Python 3.12 ile:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Uygulama yerelde 10000 portunda çalışır; `PORT` ile değiştirilebilir. Gemini veya başka bir yapay zekâ API anahtarı gerekmez. Öneri motoru denetlenebilir kurallar ve parça öncelik puanları kullanır; FPS tahmini yapmaz.

Bulut ortamındaki hazır sanal ortam `/workspace/.venvs/emo.ai` konumundadır. Geliştirme sunucusu:

```bash
PYTHONDONTWRITEBYTECODE=1 /workspace/.venvs/emo.ai/bin/gunicorn \
  --chdir /workspace/emo.ai --bind 127.0.0.1:10000 \
  --workers 1 --threads 4 --timeout 120 --reload main:app
```

Tek worker, fiyat önbelleğini ve yenileme kilidini paylaşır. Üretimde birden fazla worker/instance için ortak önbellek, dağıtık istek sınırı ve ayrı fiyat güncelleme işi eklenmelidir. `--reload` geliştirme içindir.

## Canlı Akakçe entegrasyonunun durumu

**Canlı fiyat çekme henüz doğrulanmadı.** Bu bulut ortamının mevcut ağ politikası Akakçe bağlantısını HTTP CONNECT 403 ile engelliyor. `akakce.com` ve `www.akakce.com` alan adları ortam ayarlarının taslağına eklendi; taslak kaydı erişimi çalışır hâle getirmez. Ayarlar uygulandıktan sonra gerçek sayfa yapısı ve erişim koşullarıyla entegrasyon testi yapılmalıdır.

`pc_builder/prices.py` herkese açık ürün sayfalarındaki JSON-LD `Product` / `Offer` / `AggregateOffer` verisini okumak üzere yazılmış, **canlı sayfalarla doğrulanmayı bekleyen bir adaptördür**. Rastgele sayfa metninden fiyat tahmin etmez. Tam ürün eşleşmesi, TRY para birimi ve gerçek Akakçe ürün URL'si olmadan fiyat kabul etmez. Yapılandırılmış veri değişmişse adaptör güncellenmelidir. Özellikle SKU bilgisi olmayan ilanlar güvenli eşleştirme için elenir.

Adaptör robots.txt kurallarına uyar, istekleri saniyede en fazla bir başlangıçla sınırlar, üç bağlantıdan fazlasını eşzamanlı açmaz, sonuçları 15 dakika önbellekler ve kaynak hatasında 60 saniye bekler. Her yenilemenin süre sınırı vardır. TLS doğrulaması ve ortamın proxy/CA ayarları korunur. CAPTCHA, erişim engeli veya robots kısıtlaması aşılmaz. Otomatik erişim izinli değilse izinli bir veri akışı / iş ortaklığı gerekir.

HTTP 429 için sunucunun `Retry-After` başlığı (saniye veya HTTP tarihi) dikkate alınır. Başlık yoksa 60 saniye bekleme uygulanır; bu süre erişimin açılacağına dair bir garanti değildir. Bekleme sonu kullanıcı önbellek klasöründeki `riglab/akakce-cooldown.json` dosyasında saklanır; süreç yeniden başlatılsa da süre dolmadan yeni fiyat isteği gönderilmez. Dosyada yalnızca sürüm ve bekleme zamanı bulunur. Windows'ta konum `%LOCALAPPDATA%\riglab`; diğer sistemlerde `$XDG_CACHE_HOME/riglab` veya `~/.cache/riglab` olur. Önbellek yazılamıyorsa bekleme yalnızca mevcut süreçte korunabilir. API ve terminal kalan süreyi bildirir. Bu kısıtlama hedef servisin erişim politikasını çözmez veya aşmaz.

Yerel kullanıcıdan `robots.txt` için HTTP 406 yanıtı bildirildi. Dosyanın düz metin türüne uygun `Accept` başlığı düzeltildi; bu değişikliğin canlı sunucuda sorunu çözdüğü henüz doğrulanmadı. `401`, `403` veya `406` devam ederse süreç boyunca yeni fiyat istekleri gönderilmez; site ve terminal durum kodunu açıkça gösterir. Sunucunun reddetme nedeni yalnızca durum kodundan kesinleştirilemez. Başlık düzeltmesi dışında tarayıcı taklidi veya erişim engeli aşma uygulanmaz.

Kaynak erişilemiyorsa API `503 source_unavailable`, eksiksiz uygun kombinasyon yoksa `422 no_matching_build` döndürür. Önceki veya sahte fiyatlar yerine açık bir hata gösterilir. Test fiyatları yalnızca `tests/` altında sentetiktir; uygulamada demo fiyat veya sahte ürün bağlantısı yoktur.

## Uyumluluk ve kapsam

Katalog `pc_builder/catalog.py` içinde elle yönetilir. Şu kontroller uygulanır:

- İşlemci ve anakart soketi; DDR4 / DDR5 eşleşmesi.
- Anakart boyutu, ekran kartı uzunluğu ve PSU'nun kasaya sığması.
- Ekran kartının PSU önerisi, güç payı ve 8-pin bağlantı sayısı.
- NVMe desteği ve işlemcinin BOX ürün koduyla dahil soğutucu.

Bu kontroller tam bir donanım doğrulamasının yerini tutmaz. Satın almadan önce üretici teknik özellikleri, anakart BIOS sürümü, satıcıdaki tam ürün kodu ve kutu içeriği doğrulanmalıdır. Kargo, montaj, işletim sistemi ve çevre birimleri dahil değildir. Katalog tüm piyasayı kapsamaz; seçim puanları bağımsız performans ölçümü değildir.

## Testler

```bash
PYTHONDONTWRITEBYTECODE=1 /workspace/.venvs/emo.ai/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

46 test; bütçe hesabı, eksik parça, uyumsuz soket/bellek, güç ve kasa boyutu, SKU/fiyat ayrıştırma, önbellek, kaynak kesintisi, API ve bot komut satırı doğrulamasını kapsar. Botun dosya koruması, JSON çıktısı, yalnızca yerel sunucu başlatması, robots.txt içerik türü, reddedilen isteğin yinelenmemesi, Retry-After biçimleri, yeniden başlatmada beklemenin korunması ve tarayıcı sağlayıcısı da kontrol edilir. Testler canlı Akakçe erişimi gerektirmez ve bunun çalıştığına kanıt değildir.

Gerçek tarayıcı / JavaScript bütünleşme testi (sadece sentetik yanıtlar):

```bash
python -m pip install -r requirements-browser.txt
python tests/browser_integration.py --executable /usr/bin/chromium
```

Masaüstü ve mobil Chromium kontrolleri ayrıca çalıştırıldı: form, hata durumu, yatay taşma ve sentetik yanıtla yedi parçalı sonuç görünümü doğrulandı. Gerçek `/api/build` isteğinin ağ engelinde fiyat üretmeden 503 vermesi de kontrol edildi.
