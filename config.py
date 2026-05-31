"""
Tüm sabitler ve ortam değişkenleri buradan okunur.
Başka hiçbir dosya os.environ'a dokunmaz.
"""
import os

# ── Güvenli env okuma — bozuk değerde çökme, varsayılana düş + uyar ──
_config_uyarilari: list[str] = []


def _int_env(anahtar: str, varsayilan: int, min_d: int | None = None,
             max_d: int | None = None) -> int:
    """Ortam değişkenini güvenle int'e çevir. Bozuksa varsayılan + uyarı."""
    ham = os.environ.get(anahtar)
    if ham is None or ham == "":
        return varsayilan
    try:
        deger = int(str(ham).strip())
    except (ValueError, TypeError):
        _config_uyarilari.append(
            f"{anahtar}='{ham}' geçersiz (sayı bekleniyor) → {varsayilan} kullanıldı")
        return varsayilan
    # Mantıklı aralık kontrolü
    if min_d is not None and deger < min_d:
        _config_uyarilari.append(f"{anahtar}={deger} çok düşük → {min_d} kullanıldı")
        return min_d
    if max_d is not None and deger > max_d:
        _config_uyarilari.append(f"{anahtar}={deger} çok yüksek → {max_d} kullanıldı")
        return max_d
    return deger


def _bool_env(anahtar: str, varsayilan: bool = False) -> bool:
    """Ortam değişkenini güvenle bool'a çevir. '1', 'true', 'evet' → True."""
    ham = os.environ.get(anahtar)
    if ham is None or ham == "":
        return varsayilan
    return str(ham).strip().lower() in ("1", "true", "yes", "evet", "on")

# ── Sürüm damgası (deploy doğrulama) ─────────────────────────────
# Bu sayıyı her önemli düzeltmede artır. Bot başlarken loglar.
# Railway logunda bu numarayı görmüyorsan → eski kod çalışıyor demektir.
SURUM = "v22.10-2026.05.31"   # Yeni yetenekler: fiyat takip, stok geri-gelme, kullanici istek, akilli rozet

# ── Telegram kimlik bilgileri ────────────────────────────────────
API_ID         = _int_env("API_ID", 0)
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")

# ── Filtre eşikleri ──────────────────────────────────────────────
MIN_INDIRIM    = _int_env("MIN_INDIRIM", 20, min_d=0, max_d=99)
MIN_KALITE     = _int_env("MIN_KALITE", 15, min_d=0, max_d=100)
KUYRUK_BEKLEME = _int_env("KUYRUK_BEKLEME", 180, min_d=0, max_d=86400)
TEST_MODE      = _bool_env("TEST_MODE", False)

# ── Sistem ───────────────────────────────────────────────────────
DATA_DIR         = os.environ.get("DATA_DIR") or ("/data" if os.path.exists("/data") else ".")
GORULMUS_FILE    = os.path.join(DATA_DIR, "gorulmus.json")
ISTATISTIK_FILE  = os.path.join(DATA_DIR, "istatistik.json")
LOGO_DOSYA       = "logo.PNG"
GORULMUS_MAX     = 3_000
GORULMUS_TTL     = 7 * 24 * 3_600   # saniye
WATCHDOG_ARALIK  = 3_600             # saniye
MARKA_SPAM_LIMIT = _int_env("MARKA_SPAM_LIMIT", 999, min_d=1)   # 999 = pratik olarak devre dışı
MARKA_SPAM_SURE  = 3_600            # saniye
KUPON_MIN_TL     = _int_env("KUPON_MIN_TL", 500, min_d=0)  # Bu TL'nin üstündeki kuponlar geçer

# ── Yeni özellik bayrakları ─────────────────────────────────────
QR_KOD_AKTIF        = _bool_env("QR_KOD_AKTIF", True)
SPIKE_MODU_AKTIF    = _bool_env("SPIKE_MODU_AKTIF", True)
ESKI_MESAJ_LIMIT_DK = _int_env("ESKI_MESAJ_LIMIT_DK", 180, min_d=1)   # Bu dakikadan eskiyse atla
STOK_KONTROL_SAAT   = _int_env("STOK_KONTROL_SAAT", 6, min_d=0)       # 0 = devre dışı
MIN_GORSEL_BOYUT    = _int_env("MIN_GORSEL_BOYUT", 400, min_d=0)     # Bu altındaki görsellere logo ekleme

# ── Duplicate engelleme (v22) ───────────────────────────────────
DUPLICATE_GUN       = _int_env("DUPLICATE_GUN", 3, min_d=0, max_d=90)  # Aynı ürün bu kadar gün içinde tekrar paylaşılmaz (0=kapalı)

# ── Otomatik DB bakımı (v22) ────────────────────────────────────
DB_BAKIM_SAAT       = _int_env("DB_BAKIM_SAAT", 24, min_d=0)          # Kaç saatte bir temizlik (0=kapalı)
OY_SAKLAMA_GUN      = _int_env("OY_SAKLAMA_GUN", 60, min_d=1)         # Oylar bu kadar gün saklanır
HAFIZA_SAKLAMA_GUN  = _int_env("HAFIZA_SAKLAMA_GUN", 120, min_d=1)    # Ürün hafızası bu kadar gün saklanır

# ── Self-healing model izleme (v22) ─────────────────────────────
MODEL_IZLEME_AKTIF  = _bool_env("MODEL_IZLEME_AKTIF", True)           # Model bozulursa otomatik sıfırla
MODEL_TEKRAR_ESIK   = _int_env("MODEL_TEKRAR_ESIK", 5, min_d=3)       # Son N paylaşım aynı kategoriyse → bozuk (v22.1: 15→5)

# ── Kategori güven eşiği (v22.7 — Sistem 2: 'emin değilim' modu) ──
# ML kategoriden bu eşiğin altında eminse YANLIŞ kategori basmak yerine
# kategorisiz (genel) paylaşır. Yanlış kategori hiç olmasın.
KATEGORI_GUVEN_ESIK = _int_env("KATEGORI_GUVEN_ESIK", 45, min_d=0, max_d=100)  # yüzde

# ── Kalite puan eşiği (v22.9 — Sistem 2) ────────────────────────
# Paylaşımın 0-100 kalite puanı bu eşiğin altındaysa paylaşılmaz.
# 0 = kapalı (varsayılan, güvenli başlangıç). 35-40 önerilir.
KALITE_PUAN_ESIK = _int_env("KALITE_PUAN_ESIK", 0, min_d=0, max_d=100)

# ── Karantina aralığı (v22.9 — Sistem 3) ────────────────────────
# Kalite puanı [KARANTINA_ALT, KARANTINA_UST) aralığındaysa → admin onayına.
# Bu aralığın ÜSTÜ direkt paylaşılır, ALTI direkt elenir.
# 0,0 = karantina kapalı (varsayılan). Örnek aktif: 30, 50
KARANTINA_ALT = _int_env("KARANTINA_ALT", 0, min_d=0, max_d=100)
KARANTINA_UST = _int_env("KARANTINA_UST", 0, min_d=0, max_d=100)

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
