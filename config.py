"""
Tüm sabitler ve ortam değişkenleri buradan okunur.
Başka hiçbir dosya os.environ'a dokunmaz.
"""
import os

# ── Sürüm damgası (deploy doğrulama) ─────────────────────────────
# Bu sayıyı her önemli düzeltmede artır. Bot başlarken loglar.
# Railway logunda bu numarayı görmüyorsan → eski kod çalışıyor demektir.
SURUM = "v21.8-2026.05.27"   # Gemini-siz ogrenen sistem: urun hafizasi + admin duzeltme

# ── Telegram kimlik bilgileri ────────────────────────────────────
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")

# ── Filtre eşikleri ──────────────────────────────────────────────
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "20"))
MIN_KALITE     = int(os.environ.get("MIN_KALITE", "15"))
KUYRUK_BEKLEME = int(os.environ.get("KUYRUK_BEKLEME", "180"))
TEST_MODE      = os.environ.get("TEST_MODE", "0") == "1"

# ── Sistem ───────────────────────────────────────────────────────
DATA_DIR         = os.environ.get("DATA_DIR") or ("/data" if os.path.exists("/data") else ".")
GORULMUS_FILE    = os.path.join(DATA_DIR, "gorulmus.json")
ISTATISTIK_FILE  = os.path.join(DATA_DIR, "istatistik.json")
LOGO_DOSYA       = "logo.PNG"
GORULMUS_MAX     = 3_000
GORULMUS_TTL     = 7 * 24 * 3_600   # saniye
WATCHDOG_ARALIK  = 3_600             # saniye
MARKA_SPAM_LIMIT = int(os.environ.get("MARKA_SPAM_LIMIT", "999"))   # 999 = pratik olarak devre dışı
MARKA_SPAM_SURE  = 3_600            # saniye
KUPON_MIN_TL     = int(os.environ.get("KUPON_MIN_TL", "500"))  # Bu TL'nin üstündeki kuponlar geçer

# ── Yeni özellik bayrakları ─────────────────────────────────────
QR_KOD_AKTIF        = os.environ.get("QR_KOD_AKTIF", "1") == "1"
SPIKE_MODU_AKTIF    = os.environ.get("SPIKE_MODU_AKTIF", "1") == "1"
ESKI_MESAJ_LIMIT_DK = int(os.environ.get("ESKI_MESAJ_LIMIT_DK", "180"))   # Bu dakikadan eskiyse atla
STOK_KONTROL_SAAT   = int(os.environ.get("STOK_KONTROL_SAAT", "6"))       # 0 = devre dışı
MIN_GORSEL_BOYUT    = int(os.environ.get("MIN_GORSEL_BOYUT", "400"))     # Bu altındaki görsellere logo ekleme

# ── Kara liste ───────────────────────────────────────────────────
KARA_LISTE = [
    # Küçük aksesuarlar
    "çorap", "kılıf", "sticker",
    "ekran koruyucu", "defter", "kalem",
    "ase modeli", "aksesuar seti",
    # Kitap / dergi / kırtasiye (artık paylaşılmıyor)
    "kitap", "roman", "dergi", "kırtasiye", "puzzle",
    "ansiklopedi", "ders kitabı", "öğretici", "test kitabı",
]

# ── Kaynak kanallar ──────────────────────────────────────────────
KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar",
    "@donanimhabersicakfirsatlar",
    "@yurticifirsat",
    "@firsatmerkez",
    "@indirimhabercisi",
    "@firsatpaylasim",
    "@uygunlasohbet",
    "@firsatavcilari01",
    "@firsatvakti",
    "@firsatyurdu",
    "@yurtdisifirsat",
]

# ── Kategoriler ──────────────────────────────────────────────────
# NOT: Kategori listesi artık ML modelinden geliyor (utils/ml_kategoriler.py).
# Keyword bazlı sistem kaldırıldı (v17). Sadece ML kullanılıyor.


MAGAZA_EMOJI = {
    "Trendyol": "🛍️",  "Hepsiburada": "🏪", "Amazon TR": "📦",
    "MediaMarkt": "🔴", "Teknosa": "💻",     "Gratis": "💄",
    "Boyner": "👗",     "N11": "🛒",         "Çiçeksepeti": "🌸",
    "Temu": "🌍",       "E-Ticaret": "🛒",
}

MAGAZA_HASHTAG = {
    "Trendyol": "#Trendyol",       "Hepsiburada": "#Hepsiburada",
    "Amazon TR": "#Amazon",         "MediaMarkt": "#MediaMarkt",
    "Teknosa": "#Teknosa",          "Gratis": "#Gratis",
    "N11": "#N11",                  "Çiçeksepeti": "#Çiçeksepeti",
}

KATEGORI_YAZI = {
    "elektronik": "Elektronik",     "giyim": "Giyim & Moda",
    "kozmetik": "Kozmetik",         "ev": "Ev & Yaşam",
    "market": "Market",             "spor": "Spor",
    "oyun": "Oyun & Gaming",        "bebek": "Bebek & Çocuk",
    "saglik": "Sağlık & Vitamin",   "otomotiv": "Otomotiv",
    "genel": "Alışveriş",
}

GUVENILIR_MARKALAR = [
    "apple", "samsung", "sony", "lg", "philips", "dyson", "nike",
    "adidas", "puma", "asus", "lenovo", "dell", "xiaomi", "huawei",
    "bosch", "siemens", "toshiba", "canon", "hp", "acer",
]
