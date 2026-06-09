# FırsatPulsu — Türkçe Telegram Fırsat Botu

E-ticaret kanallarını izleyip ürünleri akıllıca ayrıştıran, filtreleyen ve
kendi Telegram kanalınıza affiliate fırsatları olarak paylaşan, üretim
kalitesinde bir Türkçe fırsat aggregator botu.

> Tek dosyalık bir script değil: 23+ modüllük, 361 otomatik testli, gerçek
> mesajlarla olgunlaştırılmış bir sistem. Kurun, yapılandırın, çalıştırın.

---

## Öne Çıkanlar

- **Akıllı ürün ayrıştırma** — Tek mesajda birden çok ürün, kupon mesajları
  (🔥/🔻 "Düştü/Piyasası"), toplu link mesajları ve tekil ürünleri ayrı ayrı
  doğru biçimde işler.
- **Sahte indirim koruması** — "Piyasası" uydurması ve şişirilmiş eski fiyatları
  yakalar; gerçek olmayan %50 indirimleri paylaşmaz.
- **Reklam ve gürültü filtresi** — Sponsorlu içerik, başvuru/yatırım kalıpları,
  slogan başlıkları, kitap akınları ve ürün-olmayan linkleri (WhatsApp/Telegram/
  sosyal paylaş butonları) ayıklar. Affiliate bildirimlerini (#işbirliği) korur.
- **Kategori + kalite skoru** — Ürünleri ML destekli sınıflandırır ve her
  paylaşıma kalite puanı verir; isteğe bağlı kalite eşiğiyle filtreler.
- **Tıklama takibi** — Yerleşik yönlendirme sunucusuyla affiliate tıklamalarını
  ölçer; `/tiklamalar` ve `/rapor` ile raporlar.
- **Kalıcı veri** — SQLite tabanlı; karakutu (son olaylar), öğrenen sözlük,
  kalite karnesi ve istatistikler yeniden başlatmalarda korunur.
- **Zengin yönetim paneli** — Telegram üzerinden 35+ admin komutu: canlı durum,
  teşhis, performans, anomali tespiti, A/B testi, model eğitimi ve daha fazlası.
- **Kendini iyileştirme** — Watchdog, otomatik yeniden başlatma, sağlık takibi
  ve günlük Telegram yedeği.

---

## Gereksinimler

- Python 3.12+
- Bir Telegram hesabı (Telethon kullanıcı oturumu) ve bir hedef kanal
- (İsteğe bağlı) Google Gemini API anahtarı — gelişmiş ürün adı/kategori için
- Çalıştırma ortamı: Railway, Docker veya herhangi bir Linux sunucu

Python paketleri (`requirements.txt`): telethon, Pillow, qrcode, aiohttp

---

## Hızlı Başlangıç

```bash
# 1) Depoyu alın ve bağımlılıkları kurun
pip install -r requirements.txt

# 2) Ortam değişkenlerini ayarlayın
cp .env.example .env
# .env dosyasını düzenleyin (aşağıdaki tabloya bakın)

# 3) Çalıştırın
python main.py
```

Kolay kurulum için `kurulum.sh` scriptini de kullanabilirsiniz:

```bash
bash kurulum.sh
```

---

## Yapılandırma

Tüm ayarlar ortam değişkenleriyle yapılır. Zorunlu olanlar:

| Değişken | Açıklama |
|----------|----------|
| `API_ID` / `API_HASH` | Telegram API kimliği (my.telegram.org) |
| `SESSION_STRING` | Telethon kullanıcı oturum dizesi |
| `CHANNEL_ID` | Paylaşımların yapılacağı kanal (örn `@kanaliniz`) |
| `ADMIN_ID` | Yönetici Telegram kullanıcı kimliği |

Sık kullanılan isteğe bağlı ayarlar (varsayılanlarıyla):

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DATA_DIR` | `/data` (varsa) | Kalıcı veri dizini (kalıcı volume önerilir) |
| `MIN_INDIRIM` | `20` | Paylaşım için minimum indirim yüzdesi |
| `MIN_KALITE` | `15` | Minimum kalite eşiği |
| `KALITE_PUAN_ESIK` | `0` | Kalite skoru filtresi (0 = filtre kapalı, skor yine kaydedilir) |
| `KATEGORI_GUVEN_ESIK` | `45` | Kategori güven eşiği |
| `DUPLICATE_GUN` | `3` | Tekrar engelleme penceresi (gün) |
| `KITAP_FILTRELE` | `1` | Kitapları paylaşma (Amazon ISBN linkleri) |
| `KUPON_MIN_TL` | — | Kupon ürünleri için minimum TL |
| `KUYRUK_BEKLEME` | — | Paylaşımlar arası bekleme (saniye) |
| `ENGELLI_GONDERENLER` | — | Engellenecek göndericiler (virgülle) |
| `TIKLAMA_TAKIP_AKTIF` | `0` | Tıklama takibini aç |
| `TIKLAMA_BASE_URL` | — | Yönlendirme sunucusu temel adresi |
| `TIKLAMA_PORT` | — | Yönlendirme/health portu |
| `BOT_TOKEN` | — | (İsteğe bağlı) yönetim için bot |

Gemini kurulumu için `GEMINI_KURULUM.md`, dağıtım için `DEPLOY_REHBERI.md`
dosyasına bakın.

---

## Yönetim Komutları (Telegram)

Botu kendi Telegram'ınızdan yönetin. Başlıca komutlar:

- **Durum & teşhis:** `/durum`, `/teshis`, `/saglik`, `/performans`, `/panel`
- **İçerik & kalite:** `/karne`, `/karakutu`, `/sozluk`, `/anomali`, `/trend`
- **Tıklama & rapor:** `/tiklamalar`, `/rapor`, `/istatistik`
- **Model (ML):** `/mlistatistik`, `/yenidenegit`, `/kfold`, `/abtest`, `/tani`
- **Kontrol:** `/baslat`, `/durdur`, `/bakim`, `/temizle`, `/yedekle`
- **Yardım:** `/yardim`

Tam liste için bot içinde `/yardim` komutunu çalıştırın.

---

## Mimari

```
main.py            → Başlangıç, planlayıcılar, watchdog
config.py          → Ortam tabanlı yapılandırma
handlers/          → mesaj (ayrıştırma/filtre), admin (komutlar), callback
services/          → analiz, şablon, kupon ayrıştırıcı, ürün kapısı, scraping,
                     görsel, sağlık, zenginleştirme
utils/             → db (SQLite), kalite, reklam filtresi, tıklama, cache,
                     duplicate, karakutu, sözlük, log, self_heal
schedulers/        → günlük/haftalık/sürpriz görevler
tests/             → 361 otomatik test (run_tests.py)
```

Testleri çalıştırma:

```bash
python tests/run_tests.py
```

---

## Dağıtım

- **Railway:** `Procfile` ile worker olarak çalışır; kalıcı volume'u `/data`
  yoluna bağlayın ve `DATA_DIR=/data` ayarlayın. Ayrıntı: `DEPLOY_REHBERI.md`.
- **Docker:** (paket içinde) `docker compose up` ile tek komutta çalışır.
- **Diğer:** Herhangi bir Linux sunucuda `python main.py`.

---

## Lisans

Bu yazılım ticari bir lisansla satılmaktadır. Satın alma kapsamı (münhasır veya
tekil kullanım) ve yeniden dağıtım koşulları için `LISANS.md` dosyasına bakın.

## Destek

Kurulum ve yapılandırma desteği satış paketine dahildir. İletişim bilgisi satış
ilanında belirtilmiştir.
