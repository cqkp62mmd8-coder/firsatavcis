import os

# ─── Telegram Kimlik Bilgileri ──────────────────────────────────
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")

# ─── Filtre Eşikleri ───────────────────────────────────────────
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))
MIN_KALITE     = int(os.environ.get("MIN_KALITE", "15"))
KUYRUK_BEKLEME = int(os.environ.get("KUYRUK_BEKLEME", "180"))

# ─── Kara Liste ────────────────────────────────────────────────
KARA_LISTE = [
    "corap", "çorap", "kilif", "kılıf", "sticker",
    "ekran koruyucu", "defter", "kalem", "ase"
]

# ─── Kaynak Kanallar ───────────────────────────────────────────
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

# ─── Kalıcı Depolama ───────────────────────────────────────────
DATA_DIR        = "/data" if os.path.exists("/data") else "."
GORULMUS_FILE   = os.path.join(DATA_DIR, "gorulmus.json")
ISTATISTIK_FILE = os.path.join(DATA_DIR, "istatistik.json")
LOGO_DOSYA      = "logo.PNG"
GORULMUS_MAX    = 3000
GORULMUS_TTL    = 7 * 24 * 3600

# ─── Sistem ────────────────────────────────────────────────────
WATCHDOG_ARALIK  = 3600
MARKA_SPAM_LIMIT = 3
MARKA_SPAM_SURE  = 3600

# ─── Kategori Tanımları ────────────────────────────────────────
KATEGORILER = {
    "elektronik": {
        "anahtar": ["telefon", "iphone", "samsung", "laptop", "bilgisayar", "tablet",
                    "kulaklık", "hoparlör", "ekran", "monitör", "klavye", "mouse",
                    "powerbank", "akıllı saat", "smartwatch", "kamera", "tv",
                    "televizyon", "konsol", "playstation", "xbox", "nintendo",
                    "drone", "robot", "dyson", "philips", "xiaomi", "apple",
                    "huawei", "sony", "lg", "lenovo", "asus", "dell", "hp", "acer"],
        "ikon": "💻", "hashtag": ["#Elektronik", "#Teknoloji", "#TeknoFırsat"]
    },
    "giyim": {
        "anahtar": ["tişört", "pantolon", "elbise", "ayakkabı", "bot", "çanta",
                    "ceket", "mont", "kazak", "sweatshirt", "hoodie", "gömlek",
                    "etek", "şort", "mayo", "bikini", "nike", "adidas", "puma",
                    "zara", "mango", "lcw", "koton", "defacto", "bershka"],
        "ikon": "👗", "hashtag": ["#Giyim", "#Moda", "#FashionFırsat"]
    },
    "kozmetik": {
        "anahtar": ["parfüm", "krem", "serum", "makyaj", "ruj", "fondöten",
                    "şampuan", "saç", "cilt", "losyon", "deodorant", "sabun",
                    "gratis", "watsons", "maybelline", "loreal", "nivea",
                    "allık", "blush", "spf", "güneş"],
        "ikon": "💄", "hashtag": ["#Kozmetik", "#Güzellik", "#BeautyFırsat"]
    },
    "ev": {
        "anahtar": ["mobilya", "koltuk", "masa", "sandalye", "yatak", "yorgan",
                    "yastık", "perde", "halı", "mutfak", "tencere", "tava",
                    "fırın", "çamaşır", "bulaşık", "süpürge", "ikea"],
        "ikon": "🏠", "hashtag": ["#EvDekorasyon", "#EvEşyası", "#HomeDecor"]
    },
    "market": {
        "anahtar": ["gıda", "içecek", "kahve", "çay", "çikolata", "bisküvi",
                    "atıştırmalık", "süt", "peynir", "deterjan", "temizlik",
                    "zeytin", "zeytinyağı", "sıvı", "çekirdek"],
        "ikon": "🛒", "hashtag": ["#Market", "#Gıda", "#MarketFırsat"]
    },
    "spor": {
        "anahtar": ["spor", "fitness", "halter", "bisiklet", "koşu", "yoga",
                    "pilates", "tenis", "futbol", "basketbol", "kamp"],
        "ikon": "⚽", "hashtag": ["#Spor", "#Fitness", "#SporFırsat"]
    },
    "oyun": {
        "anahtar": ["oyun", "gaming", "ps5", "ps4", "controller", "lego", "nintendo"],
        "ikon": "🎮", "hashtag": ["#Gaming", "#Oyun", "#GamingFırsat"]
    },
    "bebek": {
        "anahtar": ["bebek", "çocuk", "oyuncak", "mama", "bez", "puset"],
        "ikon": "👶", "hashtag": ["#Bebek", "#Çocuk", "#BebekFırsat"]
    },
    "kitap": {
        "anahtar": ["kitap", "roman", "dergi", "kırtasiye", "puzzle"],
        "ikon": "📚", "hashtag": ["#Kitap", "#KitapFırsat"]
    },
}

MAGAZA_EMOJI = {
    "Trendyol": "🛍️", "Hepsiburada": "🏪", "Amazon TR": "📦",
    "MediaMarkt": "🔴", "Teknosa": "💻", "Gratis": "💄",
    "Boyner": "👗", "N11": "🛒", "Çiçeksepeti": "🌸",
    "Temu": "🌍", "E-Ticaret": "🛒",
}

MAGAZA_HASHTAG = {
    "Trendyol": "#Trendyol", "Hepsiburada": "#Hepsiburada",
    "Amazon TR": "#Amazon", "MediaMarkt": "#MediaMarkt",
    "Teknosa": "#Teknosa", "Gratis": "#Gratis",
    "N11": "#N11", "Çiçeksepeti": "#Çiçeksepeti",
}

KATEGORI_YAZI = {
    "elektronik": "Elektronik", "giyim": "Giyim & Moda",
    "kozmetik": "Kozmetik", "ev": "Ev & Yaşam", "market": "Market",
    "spor": "Spor", "oyun": "Oyun & Gaming", "bebek": "Bebek & Çocuk",
    "kitap": "Kitap", "genel": "Alışveriş",
}
