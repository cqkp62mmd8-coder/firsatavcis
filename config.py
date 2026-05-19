"""
Tüm sabitler ve ortam değişkenleri buradan okunur.
Başka hiçbir dosya os.environ'a dokunmaz.
"""
import os

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
DATA_DIR         = "/data" if os.path.exists("/data") else "."
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
    "çorap", "kılıf", "sticker",
    "ekran koruyucu", "defter", "kalem",
    "ase modeli", "aksesuar seti",
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
KATEGORILER = {
    "elektronik": {
        "anahtar": [
            "telefon", "iphone", "samsung", "laptop", "bilgisayar", "tablet",
            "kulaklık", "hoparlör", "ekran", "monitör", "klavye", "mouse",
            "powerbank", "akıllı saat", "smartwatch", "kamera", "tv",
            "televizyon", "konsol", "playstation", "xbox", "nintendo",
            "drone", "robot", "dyson", "philips", "xiaomi", "apple",
            "huawei", "sony", "lg", "lenovo", "asus", "dell", "hp", "acer",
        ],
        "ikon": "💻",
        "hashtag": ["#Elektronik", "#Teknoloji", "#TeknoFırsat"],
    },
    "giyim": {
        "anahtar": [
            "tişört", "pantolon", "elbise", "ayakkabı", "bot", "çanta",
            "ceket", "mont", "kazak", "sweatshirt", "hoodie", "gömlek",
            "etek", "şort", "mayo", "bikini", "nike", "adidas", "puma",
            "zara", "mango", "lcw", "koton", "defacto", "bershka",
        ],
        "ikon": "👗",
        "hashtag": ["#Giyim", "#Moda", "#FashionFırsat"],
    },
    "kozmetik": {
        "anahtar": [
            "parfüm", "krem", "serum", "makyaj", "ruj", "fondöten",
            "şampuan", "saç", "cilt", "losyon", "deodorant", "sabun",
            "gratis", "watsons", "maybelline", "loreal", "nivea",
            "allık", "blush", "spf", "güneş",
        ],
        "ikon": "💄",
        "hashtag": ["#Kozmetik", "#Güzellik", "#BeautyFırsat"],
    },
    "ev": {
        "anahtar": [
            "mobilya", "koltuk", "masa", "sandalye", "yatak", "yorgan",
            "yastık", "perde", "halı", "mutfak", "tencere", "tava",
            "fırın", "çamaşır", "bulaşık", "süpürge", "ikea",
        ],
        "ikon": "🏠",
        "hashtag": ["#EvDekorasyon", "#EvEşyası", "#HomeDecor"],
    },
    "market": {
        "anahtar": [
            "gıda", "içecek", "kahve", "çay", "çikolata", "bisküvi",
            "atıştırmalık", "süt", "peynir", "deterjan", "temizlik",
            "zeytin", "zeytinyağı", "sıvı", "çekirdek",
        ],
        "ikon": "🛒",
        "hashtag": ["#Market", "#Gıda", "#MarketFırsat"],
    },
    "spor": {
        "anahtar": [
            "spor", "fitness", "halter", "bisiklet", "koşu", "yoga",
            "pilates", "tenis", "futbol", "basketbol", "kamp",
        ],
        "ikon": "⚽",
        "hashtag": ["#Spor", "#Fitness", "#SporFırsat"],
    },
    "oyun": {
        "anahtar": ["oyun", "gaming", "ps5", "ps4", "controller", "lego", "nintendo"],
        "ikon": "🎮",
        "hashtag": ["#Gaming", "#Oyun", "#GamingFırsat"],
    },
    "bebek": {
        "anahtar": ["bebek", "çocuk", "oyuncak", "mama", "bez", "puset"],
        "ikon": "👶",
        "hashtag": ["#Bebek", "#Çocuk", "#BebekFırsat"],
    },
    "kitap": {
        "anahtar": ["kitap", "roman", "dergi", "kırtasiye", "puzzle"],
        "ikon": "📚",
        "hashtag": ["#Kitap", "#KitapFırsat"],
    },
}

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
    "elektronik": "Elektronik",    "giyim": "Giyim & Moda",
    "kozmetik": "Kozmetik",        "ev": "Ev & Yaşam",
    "market": "Market",            "spor": "Spor",
    "oyun": "Oyun & Gaming",       "bebek": "Bebek & Çocuk",
    "kitap": "Kitap",              "genel": "Alışveriş",
}

GUVENILIR_MARKALAR = [
    "apple", "samsung", "sony", "lg", "philips", "dyson", "nike",
    "adidas", "puma", "asus", "lenovo", "dell", "xiaomi", "huawei",
    "bosch", "siemens", "toshiba", "canon", "hp", "acer",
]
