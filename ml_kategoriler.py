"""
Kategori hiyerarşisi — ana kategori + alt kategoriler.

Format:
  ANA_KAT → {
    "ikon": str,
    "yazi": str,
    "hashtag": list[str],
    "alt": {
      "alt_kat_id": {"yazi": str, "hashtag": str (opsiyonel)}
    }
  }

Mesaj sablon'larında "elektronik:telefon" tarzı tam path kullanılır,
ya da sadece "elektronik" (alt kategori yoksa).
"""

KATEGORI_AGAC = {
    # ELEKTRONİK
    "elektronik": {
        "ikon": "💻",
        "yazi": "Elektronik",
        "hashtag": ["#Elektronik", "#Teknoloji"],
        "alt": {
            "telefon":    {"yazi": "Telefon",     "hashtag": "#Telefon"},
            "bilgisayar": {"yazi": "Bilgisayar",  "hashtag": "#Laptop"},
            "tv":         {"yazi": "TV & Görüntü","hashtag": "#TV"},
            "ses":        {"yazi": "Ses Sistemi", "hashtag": "#Kulaklık"},
            "saat":       {"yazi": "Akıllı Saat", "hashtag": "#Smartwatch"},
            "beyaz_esya": {"yazi": "Beyaz Eşya",  "hashtag": "#BeyazEşya"},
            "alet":       {"yazi": "Aletler",     "hashtag": "#Alet"},
            "kamera":     {"yazi": "Kamera",      "hashtag": "#Kamera"},
            "aksesuar":   {"yazi": "Aksesuar",    "hashtag": "#Aksesuar"},
        },
    },
    # GİYİM
    "giyim": {
        "ikon": "👗",
        "yazi": "Giyim & Moda",
        "hashtag": ["#Giyim", "#Moda"],
        "alt": {
            "ayakkabi":   {"yazi": "Ayakkabı",    "hashtag": "#Sneaker"},
            "ust_giyim":  {"yazi": "Üst Giyim",   "hashtag": "#ÜstGiyim"},
            "alt_giyim":  {"yazi": "Alt Giyim",   "hashtag": "#Pantolon"},
            "dis_giyim":  {"yazi": "Dış Giyim",   "hashtag": "#Mont"},
            "canta":      {"yazi": "Çanta",       "hashtag": "#Çanta"},
            "ic_giyim":   {"yazi": "İç Giyim",    "hashtag": "#İçGiyim"},
            "aksesuar":   {"yazi": "Aksesuar",    "hashtag": "#Aksesuar"},
        },
    },
    # KOZMETİK
    "kozmetik": {
        "ikon": "💄",
        "yazi": "Kozmetik",
        "hashtag": ["#Kozmetik", "#Güzellik"],
        "alt": {
            "yuz_bakim":  {"yazi": "Yüz Bakım",   "hashtag": "#CiltBakım"},
            "makyaj":     {"yazi": "Makyaj",      "hashtag": "#Makyaj"},
            "parfum":     {"yazi": "Parfüm",      "hashtag": "#Parfüm"},
            "sac_bakim":  {"yazi": "Saç Bakım",   "hashtag": "#SaçBakım"},
            "vucut":      {"yazi": "Vücut Bakım", "hashtag": "#Bakım"},
        },
    },
    # EV
    "ev": {
        "ikon": "🏠",
        "yazi": "Ev & Yaşam",
        "hashtag": ["#EvDekor", "#Yaşam"],
        "alt": {
            "tekstil":    {"yazi": "Yatak Tekstil",  "hashtag": "#YatakOdası"},
            "mutfak":     {"yazi": "Mutfak",         "hashtag": "#Mutfak"},
            "mobilya":    {"yazi": "Mobilya",        "hashtag": "#Mobilya"},
            "dekor":      {"yazi": "Dekorasyon",     "hashtag": "#Dekorasyon"},
            "banyo":      {"yazi": "Banyo",          "hashtag": "#Banyo"},
            "bahce":      {"yazi": "Bahçe",          "hashtag": "#Bahçe"},
        },
    },
    # MARKET
    "market": {
        "ikon": "🛒",
        "yazi": "Market",
        "hashtag": ["#Market", "#Gıda"],
        "alt": {
            "atistir":    {"yazi": "Atıştırmalık", "hashtag": "#Çikolata"},
            "icecek":     {"yazi": "İçecek",       "hashtag": "#Kahve"},
            "temel":      {"yazi": "Temel Gıda",   "hashtag": "#Gıda"},
            "temizlik":   {"yazi": "Temizlik",     "hashtag": "#Temizlik"},
            "evcil":      {"yazi": "Pet Shop",     "hashtag": "#Evcil"},
        },
    },
    # SPOR
    "spor": {
        "ikon": "⚽",
        "yazi": "Spor",
        "hashtag": ["#Spor", "#Fitness"],
        "alt": {
            "fitness":    {"yazi": "Fitness",      "hashtag": "#Fitness"},
            "outdoor":    {"yazi": "Outdoor",      "hashtag": "#Outdoor"},
            "bisiklet":   {"yazi": "Bisiklet",     "hashtag": "#Bisiklet"},
            "top":        {"yazi": "Top Sporları", "hashtag": "#Futbol"},
            "su_sporu":   {"yazi": "Su Sporu",     "hashtag": "#Yüzme"},
            "kayak":      {"yazi": "Kış Sporları", "hashtag": "#Kayak"},
        },
    },
    # OYUN
    "oyun": {
        "ikon": "🎮",
        "yazi": "Oyun & Gaming",
        "hashtag": ["#Gaming", "#Oyun"],
        "alt": {
            "lego":       {"yazi": "Lego",         "hashtag": "#Lego"},
            "konsol":     {"yazi": "Konsol Oyunu", "hashtag": "#PS5"},
            "aksesuar":   {"yazi": "Gaming Aksesuar", "hashtag": "#Gaming"},
            "oyuncak":    {"yazi": "Oyuncak",      "hashtag": "#Oyuncak"},
        },
    },
    # BEBEK
    "bebek": {
        "ikon": "👶",
        "yazi": "Bebek & Çocuk",
        "hashtag": ["#Bebek", "#Çocuk"],
        "alt": {
            "bez":        {"yazi": "Bebek Bezi",   "hashtag": "#Bez"},
            "beslenme":   {"yazi": "Bebek Mama",   "hashtag": "#BebekMama"},
            "koltuk":     {"yazi": "Araba Koltuğu", "hashtag": "#AracKoltuğu"},
            "puset":      {"yazi": "Puset",        "hashtag": "#Puset"},
            "oyuncak":    {"yazi": "Bebek Oyuncak","hashtag": "#BebekOyuncak"},
        },
    },
    # SAĞLIK
    "saglik": {
        "ikon": "💊",
        "yazi": "Sağlık & Vitamin",
        "hashtag": ["#Sağlık", "#Vitamin"],
        "alt": {
            "vitamin":    {"yazi": "Vitamin",      "hashtag": "#Vitamin"},
            "takviye":    {"yazi": "Takviye",      "hashtag": "#Takviye"},
            "tibbi":      {"yazi": "Tıbbi Cihaz",  "hashtag": "#TıbbiCihaz"},
            "kisisel":    {"yazi": "Kişisel Bakım","hashtag": "#KişiselBakım"},
        },
    },
    # OTOMOTİV
    "otomotiv": {
        "ikon": "🚗",
        "yazi": "Otomotiv",
        "hashtag": ["#Otomotiv", "#Araba"],
        "alt": {
            "lastik":     {"yazi": "Lastik",       "hashtag": "#Lastik"},
            "yag":        {"yazi": "Motor Yağı",   "hashtag": "#MotorYağı"},
            "aku":        {"yazi": "Akü",          "hashtag": "#Akü"},
            "bakim":      {"yazi": "Araç Bakım",   "hashtag": "#OtoBakım"},
            "aksesuar":   {"yazi": "Aksesuar",     "hashtag": "#OtoAksesuar"},
        },
    },
}


def ana_kategori_listesi() -> list[str]:
    return list(KATEGORI_AGAC.keys())


def alt_kategori_listesi(ana: str) -> list[str]:
    return list(KATEGORI_AGAC.get(ana, {}).get("alt", {}).keys())


def tum_kategoriler_flat() -> list[str]:
    """[(ana, alt), ...] tarzı tüm path'leri döndürür."""
    sonuc = []
    for ana, data in KATEGORI_AGAC.items():
        sonuc.append((ana, None))
        for alt in data.get("alt", {}):
            sonuc.append((ana, alt))
    return sonuc


def kategori_bilgisi(ana: str, alt: str | None = None) -> dict:
    """Görüntüleme bilgisi (ikon, yazı, hashtag listesi)."""
    if ana not in KATEGORI_AGAC:
        return {"ikon": "🛍️", "yazi": "Alışveriş", "hashtag": ["#Fırsat"]}
    ana_data = KATEGORI_AGAC[ana]
    if alt and alt in ana_data.get("alt", {}):
        alt_data = ana_data["alt"][alt]
        return {
            "ikon": ana_data["ikon"],
            "yazi": alt_data["yazi"],
            "hashtag": [alt_data.get("hashtag", "")] + ana_data["hashtag"],
            "ana": ana,
            "alt": alt,
        }
    return {
        "ikon": ana_data["ikon"],
        "yazi": ana_data["yazi"],
        "hashtag": ana_data["hashtag"],
        "ana": ana,
        "alt": None,
    }


def normalize(kategori: str) -> tuple[str, str | None]:
    """'elektronik:telefon' veya 'elektronik' formatından (ana, alt) tuple."""
    if not kategori:
        return "genel", None
    if ":" in kategori:
        ana, alt = kategori.split(":", 1)
        return ana, alt
    return kategori, None


def format(ana: str, alt: str | None) -> str:
    """('elektronik', 'telefon') → 'elektronik:telefon'"""
    if alt:
        return f"{ana}:{alt}"
    return ana
