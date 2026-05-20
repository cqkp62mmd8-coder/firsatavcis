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
KATEGORILER = {
    "elektronik": {
        "anahtar": [
            # Telefon / bilgisayar
            "telefon", "iphone", "samsung galaxy", "laptop", "notebook",
            "bilgisayar", "tablet", "ipad",
            # Ses & görüntü
            "kulaklık", "kulakiçi", "airpods", "hoparlör", "soundbar",
            "ekran", "monitör", "tv", "televizyon", "led",
            # Çevre birimleri
            "klavye", "mouse", "fare", "webcam", "yazıcı", "printer",
            # Akıllı / giyilebilir
            "akıllı saat", "smartwatch", "smart band", "akıllı bileklik",
            # Şarj / güç
            "powerbank", "şarj cihazı", "şarj aleti", "kablo", "adaptör",
            # Akıllı ev
            "akıllı priz", "akıllı ampul", "akıllı lamba", "alexa", "google home",
            # Kamera / aksesuar
            "kamera", "fotoğraf makinesi", "lens", "objektif", "drone",
            # Konsol & oyun donanım
            "konsol", "playstation", "ps4", "ps5", "xbox", "nintendo", "switch",
            # Beyaz eşya / küçük ev aletleri (elektronik olarak da algılanmalı)
            "süpürge", "robot süpürge", "ütü", "saç kurutma", "saç şekillendirme",
            "blender", "mikser", "tost makinesi", "çay makinesi", "kahve makinesi",
            "espresso", "fritöz", "airfryer", "mikrodalga", "buharlı",
            "ankastre", "buzdolabı", "çamaşır makinesi", "bulaşık makinesi",
            "fırın", "ocak", "davlumbaz", "klima", "kombi", "şofben",
            # Markalar
            "dyson", "philips", "xiaomi", "apple", "huawei", "sony", "lg",
            "lenovo", "asus", "dell", "hp", "acer", "msi", "razer", "logitech",
            "bosch", "siemens", "arçelik", "vestel", "beko", "karaca", "tefal",
            "fakir", "arzum", "kiwi", "homend", "braun", "rowenta",
            "tplink", "tp-link", "huawei", "mediatek",
            # Aletler
            "akülü", "şarjlı", "matkap", "vidalama", "tornavida", "kompresör",
            "elektrikli alet", "el aleti", "tornavida seti",
        ],
        "ikon": "💻",
        "hashtag": ["#Elektronik", "#Teknoloji", "#TeknoFırsat"],
    },
    "giyim": {
        "anahtar": [
            "tişört", "t-shirt", "pantolon", "jean", "kot", "elbise",
            "ayakkabı", "sneaker", "bot", "topuklu", "çizme", "terlik",
            "çanta", "cüzdan", "ceket", "mont", "kaban", "kazak", "yelek",
            "sweatshirt", "hoodie", "gömlek", "bluz", "etek", "şort",
            "mayo", "bikini", "iç giyim", "iç çamaşırı", "pijama",
            "kemer", "şapka", "kep", "atkı", "eldiven", "fular",
            # Markalar
            "nike", "adidas", "puma", "new balance", "reebok", "converse",
            "vans", "skechers", "under armour",
            "zara", "mango", "lcw", "lcwaikiki", "koton", "defacto",
            "bershka", "pull&bear", "stradivarius", "hm", "h&m",
            "jack & jones", "tommy hilfiger", "calvin klein", "levi's",
            "polo", "lacoste", "boyner",
        ],
        "ikon": "👗",
        "hashtag": ["#Giyim", "#Moda", "#FashionFırsat"],
    },
    "kozmetik": {
        "anahtar": [
            # Genel
            "parfüm", "edt", "edp", "kolonya", "deodorant",
            # Cilt bakım
            "krem", "serum", "tonik", "maske", "yüz bakım", "cilt bakım",
            "nemlendirici", "leke kremi", "göz kremi", "spf", "güneş kremi",
            "vitamin c", "retinol", "hyaluronic",
            # Makyaj
            "makyaj", "ruj", "lipstick", "lip", "fondöten", "foundation",
            "kapatıcı", "concealer", "allık", "blush", "highlighter",
            "far", "eyeshadow", "eyeliner", "rimel", "maskara",
            "oje", "ojeli", "manikür",
            # Saç bakım
            "şampuan", "saç kremi", "saç maskesi", "saç bakım",
            # Vücut bakım
            "sabun", "duş jeli", "vücut losyonu", "el kremi",
            # Markalar / mağazalar
            "gratis", "watsons", "sephora", "rossmann",
            "maybelline", "loreal", "l'oreal", "nivea", "garnier",
            "neutrogena", "cerave", "the ordinary", "estee lauder",
            "lancome", "chanel", "dior", "ysl", "mac",
            "flormar", "golden rose", "pastel", "essence",
        ],
        "ikon": "💄",
        "hashtag": ["#Kozmetik", "#Güzellik", "#BeautyFırsat"],
    },
    "ev": {
        "anahtar": [
            # Mobilya
            "mobilya", "koltuk", "kanepe", "berjer", "puf", "masa",
            "sandalye", "yatak", "baza", "gardırop", "dolap", "raf",
            "kitaplık", "tv ünitesi", "konsol masa", "şifonyer",
            # Tekstil
            "yorgan", "yastık", "nevresim", "çarşaf", "battaniye",
            "perde", "halı", "kilim", "yolluk", "minder", "kırlent",
            "havlu", "bornoz",
            # Mutfak / yemek
            "tencere", "tava", "çaydanlık", "demlik", "kettle",
            "bardak", "tabak", "kase", "çatal", "kaşık",
            "bıçak seti", "mutfak terazisi",
            # Banyo / WC
            "klozet", "lavabo", "duş", "duşakabin", "ayna",
            # Dekorasyon
            "tablo", "vazo", "saksı", "mum", "abajur", "lamba", "avize",
            "ikea", "english home", "madame coco", "karaca home",
        ],
        "ikon": "🏠",
        "hashtag": ["#EvDekorasyon", "#EvEşyası", "#HomeDecor"],
    },
    "market": {
        "anahtar": [
            "gıda", "içecek", "kola", "ayran", "su",
            "kahve", "çay", "çikolata", "bisküvi", "gofret",
            "atıştırmalık", "cips", "kuruyemiş", "fındık", "ceviz",
            "süt", "peynir", "yoğurt", "tereyağı",
            "deterjan", "yumuşatıcı", "çamaşır suyu", "temizlik",
            "zeytin", "zeytinyağı", "ayçiçek yağı", "tuz",
            "makarna", "pirinç", "bulgur", "un", "şeker",
            "bakliyat", "mercimek", "nohut", "fasulye",
        ],
        "ikon": "🛒",
        "hashtag": ["#Market", "#Gıda", "#MarketFırsat"],
    },
    "spor": {
        "anahtar": [
            "spor", "fitness", "halter", "dumbbell", "kettlebell",
            "bisiklet", "scooter", "koşu bandı", "elips bisiklet",
            "yoga matı", "pilates", "tenis", "raket",
            "futbol", "basketbol", "voleybol", "top",
            "kamp", "çadır", "uyku tulumu", "trekking",
            "outdoor", "balıkçılık", "olta",
        ],
        "ikon": "⚽",
        "hashtag": ["#Spor", "#Fitness", "#SporFırsat"],
    },
    "oyun": {
        "anahtar": [
            "oyun", "gaming", "playstation", "ps4", "ps5",
            "xbox", "nintendo", "switch", "controller", "kol",
            "lego", "minecraft", "fifa", "fortnite",
            "steam", "gaming klavye", "gaming mouse", "gaming kulaklık",
            "oyuncu koltuğu", "gaming chair",
        ],
        "ikon": "🎮",
        "hashtag": ["#Gaming", "#Oyun", "#GamingFırsat"],
    },
    "bebek": {
        "anahtar": [
            "bebek", "çocuk", "oyuncak", "mama", "biberon",
            "bez", "ıslak mendil", "puset", "araba koltuğu",
            "anne sütü", "emzik", "bebek bezi", "bebek arabası",
            "lego duplo", "fisher price", "barbie", "hot wheels",
        ],
        "ikon": "👶",
        "hashtag": ["#Bebek", "#Çocuk", "#BebekFırsat"],
    },
    "saglik": {
        "anahtar": [
            "vitamin", "magnezyum", "kalsiyum", "demir", "çinko",
            "omega 3", "balık yağı", "protein tozu", "kreatin",
            "kollajen", "biotin", "ginseng",
            "tansiyon ölçer", "termometre", "ateş ölçer",
            "diş fırçası", "diş macunu", "diş ipi",
            "ağrı kesici", "vücut analiz",
            "saç kompleksi", "saç vitamin", "biotini",
            # İlaç formları
            "kapsül", "60 kapsül", "100 kapsül", "tablet vitamin",
            "yumuşak kapsül", "sert kapsül",
        ],
        "ikon": "💊",
        "hashtag": ["#Sağlık", "#Vitamin", "#SağlıkFırsat"],
    },
    "otomotiv": {
        "anahtar": [
            "araba", "araç", "lastik", "motoryağı", "yağ",
            "akü", "şarj akü", "jant", "stepne",
            "araç bakım", "polish", "vaks", "cam suyu", "antifriz",
            "araç içi", "araç tepsi", "tampon",
            "michelin", "goodyear", "bridgestone", "petlas",
        ],
        "ikon": "🚗",
        "hashtag": ["#Otomotiv", "#Araba", "#AraçFırsat"],
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
