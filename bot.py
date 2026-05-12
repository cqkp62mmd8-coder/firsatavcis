import os
import asyncio
import re
import json
import hashlib
import unicodedata
from io import BytesIO
from datetime import datetime, timezone, timedelta
from PIL import Image
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError, UsernameInvalidError
from telethon.tl.types import MessageMediaPhoto
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

# ═══════════════════════════════════════════════════════════════
# AYARLAR
# ═══════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", "0"))
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")  # Inline buton icin ayri bot token
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))

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

GORULMUS_FILE   = "gorulmus.json"
ISTATISTIK_FILE = "istatistik.json"
GUNUN_URUNLERI_FILE = "gunun_urunleri.json"
LOGO_DOSYA      = "logo.PNG"
MESAJ_BEKLEME   = 3
GORULMUS_MAX    = 3000
GORULMUS_TTL    = 7 * 24 * 3600
WATCHDOG_ARALIK = 3600

# ═══════════════════════════════════════════════════════════════
# KATEGORI TANIMLARI
# ═══════════════════════════════════════════════════════════════
KATEGORILER = {
    "elektronik": {
        "anahtar": ["telefon", "iphone", "samsung", "laptop", "bilgisayar", "tablet", "kulaklık",
                    "kulaklık", "hoparlör", "ekran", "monitör", "klavye", "mouse", "şarj",
                    "powerbank", "akıllı saat", "smartwatch", "kamera", "fotoğraf", "tv",
                    "televizyon", "konsol", "playstation", "xbox", "nintendo", "drone",
                    "robot", "süpürge", "dyson", "philips", "xiaomi", "apple", "huawei",
                    "samsung", "sony", "lg", "lenovo", "asus", "dell", "hp", "acer"],
        "ikon": "💻",
        "hashtag": ["#Elektronik", "#Teknoloji", "#TeknoFırsat"]
    },
    "giyim": {
        "anahtar": ["tişört", "pantolon", "elbise", "ayakkabı", "bot", "çanta", "ceket",
                    "mont", "kazak", "sweatshirt", "hoodie", "gömlek", "etek", "şort",
                    "mayo", "bikini", "spor", "nike", "adidas", "puma", "zara", "mango",
                    "lcw", "koton", "defacto", "bershka", "h&m"],
        "ikon": "👗",
        "hashtag": ["#Giyim", "#Moda", "#FashionFırsat"]
    },
    "kozmetik": {
        "anahtar": ["parfüm", "krem", "serum", "makyaj", "ruj", "fondöten", "şampuan",
                    "saç", "cilt", "losyon", "deodorant", "duş", "sabun", "diş",
                    "gratis", "watsons", "rossmann", "maybelline", "loreal", "nivea"],
        "ikon": "💄",
        "hashtag": ["#Kozmetik", "#Güzellik", "#BeautyFırsat"]
    },
    "ev": {
        "anahtar": ["mobilya", "koltuk", "masa", "sandalye", "yatak", "yorgan", "yastık",
                    "perde", "halı", "mutfak", "tencere", "tava", "fırın", "çamaşır",
                    "bulaşık", "ikea", "bellona", "istikbal", "mondi"],
        "ikon": "🏠",
        "hashtag": ["#EvDekorasyon", "#EvEşyası", "#HomeDecor"]
    },
    "market": {
        "anahtar": ["gıda", "içecek", "kahve", "çay", "çikolata", "bisküvi", "atıştırmalık",
                    "süt", "peynir", "et", "tavuk", "deterjan", "temizlik", "bim", "a101",
                    "şok", "migros", "carrefour", "zeytin", "zeytinyağı"],
        "ikon": "🛒",
        "hashtag": ["#Market", "#Gıda", "#MarketFırsat"]
    },
    "spor": {
        "anahtar": ["spor", "fitness", "dumbbell", "halter", "bisiklet", "koşu", "yoga",
                    "pilates", "tenis", "futbol", "basketbol", "yüzme", "kamp", "outdoor"],
        "ikon": "⚽",
        "hashtag": ["#Spor", "#Fitness", "#SporFırsat"]
    },
    "oyun": {
        "anahtar": ["oyun", "gaming", "playstation", "xbox", "nintendo", "ps5", "ps4",
                    "controller", "joystick", "headset", "gaming chair", "lego"],
        "ikon": "🎮",
        "hashtag": ["#Gaming", "#Oyun", "#GamingFırsat"]
    },
    "bebek": {
        "anahtar": ["bebek", "çocuk", "oyuncak", "mama", "bez", "pueri", "bebe",
                    "araba koltuğu", "bisiklet", "puset"],
        "ikon": "👶",
        "hashtag": ["#Bebek", "#Çocuk", "#BebekFırsat"]
    },
    "kitap": {
        "anahtar": ["kitap", "roman", "dergi", "kalem", "defter", "kırtasiye", "puzzle"],
        "ikon": "📚",
        "hashtag": ["#Kitap", "#Kırtasiye", "#KitapFırsat"]
    },
}

MAGAZA_HASHTAG = {
    "Trendyol":    "#Trendyol",
    "Hepsiburada": "#Hepsiburada",
    "Amazon TR":   "#Amazon",
    "MediaMarkt":  "#MediaMarkt",
    "Teknosa":     "#Teknosa",
    "Gratis":      "#Gratis",
    "Boyner":      "#Boyner",
    "N11":         "#N11",
    "Çiçeksepeti": "#Çiçeksepeti",
    "Temu":        "#Temu",
}

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
gorulmus_cache    = None
istatistik_cache  = None
ist_degisim_sayac = 0
son_mesaj_zamani  = 0.0
gunun_urunleri    = []  # Gun icinde yakalanan en iyi urunler

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Inline buton gondermek icin ayri bot client
import telethon
bot_client = None

# ═══════════════════════════════════════════════════════════════
# LOGLAMA
# ═══════════════════════════════════════════════════════════════
def log(seviye, mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[" + zaman + "] [" + seviye + "] " + mesaj)

# ═══════════════════════════════════════════════════════════════
# GORULMUS
# ═══════════════════════════════════════════════════════════════
def gorulmus_yukle():
    global gorulmus_cache
    if gorulmus_cache is not None:
        return gorulmus_cache
    try:
        with open(GORULMUS_FILE, "r") as f:
            gorulmus_cache = json.load(f)
    except:
        gorulmus_cache = {}
    return gorulmus_cache

def gorulmus_kaydet():
    global gorulmus_cache
    if gorulmus_cache is None:
        return
    try:
        with open(GORULMUS_FILE, "w") as f:
            json.dump(gorulmus_cache, f)
    except Exception as e:
        log("HATA", "gorulmus kaydetme: " + str(e))

def gorulmus_temizle():
    global gorulmus_cache
    gorulmus_yukle()
    if not gorulmus_cache:
        return
    simdi = datetime.now(timezone.utc).timestamp()
    onceki = len(gorulmus_cache)
    gorulmus_cache = {k: v for k, v in gorulmus_cache.items() if simdi - v < GORULMUS_TTL}
    if len(gorulmus_cache) > GORULMUS_MAX:
        sirali = sorted(gorulmus_cache.items(), key=lambda x: x[1], reverse=True)
        gorulmus_cache = dict(sirali[:GORULMUS_MAX])
    temizlenen = onceki - len(gorulmus_cache)
    if temizlenen > 0:
        log("BILGI", str(temizlenen) + " eski kayit temizlendi")
    gorulmus_kaydet()

def gorulmus_var_mi(mid):
    return mid in gorulmus_yukle()

def gorulmus_ekle(mid):
    global gorulmus_cache
    gorulmus_yukle()
    gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()
    gorulmus_kaydet()

# ═══════════════════════════════════════════════════════════════
# ISTATISTIK
# ═══════════════════════════════════════════════════════════════
def istatistik_yukle():
    global istatistik_cache
    if istatistik_cache is not None:
        return istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "r") as f:
            istatistik_cache = json.load(f)
    except:
        istatistik_cache = {"toplam": 0, "kanallar": {}, "gunluk": {}}
    return istatistik_cache

def istatistik_kaydet():
    global istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "w") as f:
            json.dump(istatistik_cache, f)
    except:
        pass

def istatistik_guncelle(kanal_adi, magaza):
    global ist_degisim_sayac
    ist = istatistik_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    ist_degisim_sayac += 1
    if ist_degisim_sayac >= 10:
        istatistik_kaydet()
        ist_degisim_sayac = 0

# ═══════════════════════════════════════════════════════════════
# YARDIMCI
# ═══════════════════════════════════════════════════════════════
def emoji_temizle(metin):
    if not metin:
        return ""
    temiz = ""
    for k in metin:
        kat = unicodedata.category(k)
        if kat not in ("So", "Sm", "Sk"):
            temiz += k
    return temiz.strip()


def markdown_temizle(metin):
    if not metin:
        return metin
    metin = re.sub(r'[*]{1,3}([^*]+)[*]{1,3}', r'\1', metin)
    metin = re.sub(r'[_]{1,2}([^_]+)[_]{1,2}', r'\1', metin)
    metin = re.sub(r'[`]([^`]+)[`]', r'\1', metin)
    metin = re.sub(r'[~]{1,2}([^~]+)[~]{1,2}', r'\1', metin)
    metin = re.sub(r'[|]{2}([^|]+)[|]{2}', r'\1', metin)
    return metin


def mesaj_id_olustur(metin):
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    kaliplar = [
        r"-\s*%\s*(\d+)",
        r"indirim\s*:\s*-?\s*%\s*(\d+)",
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
        r"yuzde\s*(\d+)",
        r"(\d+)\s*percent",
    ]
    for kalip in kaliplar:
        eslesme = re.findall(kalip, metin.lower())
        if eslesme:
            degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
            if degerler:
                return max(degerler)
    if any(k in metin.lower() for k in ["indirim", "kampanya", "firsat", "sale", "off"]):
        eslesme = re.findall(r"%(\d+)", metin) + re.findall(r"(\d+)%", metin)
        degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
        if degerler:
            return max(degerler)
    return 0

def fiyat_parse(fiyat_str):
    try:
        temiz = fiyat_str.strip()
        if "," in temiz and "." in temiz:
            temiz = temiz.replace(".", "").replace(",", ".")
        elif "," in temiz:
            temiz = temiz.replace(",", ".")
        return float(temiz)
    except:
        return 0.0

def fiyat_bul(metin):
    eslesme = re.findall(r"([\d.,]+)\s*(?:TL|tl|₺|lira)", metin or "")
    if len(eslesme) >= 2:
        degerler = [(fiyat_parse(f), f) for f in eslesme]
        degerler = [(v, s) for v, s in degerler if v > 0]
        if len(degerler) >= 2:
            sirali = sorted(degerler, key=lambda x: x[0], reverse=True)
            eski_val, eski_str = sirali[0]
            yeni_val, yeni_str = sirali[-1]
            if eski_val > yeni_val:
                return eski_str, yeni_str, eski_val, yeni_val
    return None, None, 0, 0

def magaza_bul(metin):
    metin_k = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol",    "trendyol"),
        ("Hepsiburada", "hepsiburada"),
        ("Amazon TR",   "amazon"),
        ("MediaMarkt",  "mediamarkt"),
        ("Teknosa",     "teknosa"),
        ("Gratis",      "gratis"),
        ("Boyner",      "boyner"),
        ("Morhipo",     "morhipo"),
        ("N11",         "n11.com"),
        ("Çiçeksepeti", "ciceksepeti"),
        ("Temu",        "temu.com"),
    ]:
        if anahtar in metin_k:
            return magaza
    return "E-Ticaret"

def kategori_bul(metin):
    metin_k = (metin or "").lower()
    for kat_adi, kat_bilgi in KATEGORILER.items():
        for anahtar in kat_bilgi["anahtar"]:
            if anahtar in metin_k:
                return kat_adi, kat_bilgi["ikon"], kat_bilgi["hashtag"]
    return "genel", "🛍️", ["#Fırsat", "#İndirim"]

def stok_durumu_bul(metin):
    metin_k = (metin or "").lower()
    kritik = ["stoklar eriyor", "son stok", "tükeniyor", "stok tükeniyor",
              "son birkaç", "stok azalıyor", "hızlı bitecek", "sınırlı stok"]
    for k in kritik:
        if k in metin_k:
            return True
    return False

def indirim_turu_bul(metin, urun_adi):
    metin_k = (metin or "").lower()
    # Marka indirimi: "X markasında %Y indirim" veya "tüm ürünlerde indirim"
    marka_kalip = [
        r"\w+\s*(?:urunlerinde|markasinda|serisinde|koleksiyonunda)\s*%\d+",
        r"tum\s*\w*\s*urunlerde",
        r"secili\s*\w*\s*urunlerde",
    ]
    for kalip in marka_kalip:
        if re.search(kalip, metin_k):
            return "marka"
    return "urun"

def urun_adi_bul(metin):
    if not metin:
        return None
    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    for satir in satirlar:
        temiz = emoji_temizle(satir)
        if (len(temiz) >= 8
                and not satir.startswith("#")
                and not satir.startswith("@")
                and "http" not in satir
                and "TL" not in satir
                and "₺" not in satir
                and not re.search(r"\d+%|%\d+", satir)):
            return temiz[:80]
    return None

def link_bul(metin, buton_linkleri=None):
    oncelik = [
        "trendyol.com", "hepsiburada.com", "amazon.com.tr",
        "mediamarkt.com.tr", "teknosa.com", "ty.gl", "hb.gl",
        "vatanbilgisayar.com", "n11.com", "ciceksepeti.com",
        "aliexpress.com", "gratis.com"
    ]
    # Once butonlara bak
    if buton_linkleri:
        for bl in buton_linkleri:
            for p in oncelik:
                if p in bl:
                    return bl
        for bl in buton_linkleri:
            if "google.com" not in bl and "t.me" not in bl and "telegram" not in bl:
                return bl
    # Metinden ara
    if metin:
        linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
        for link in linkler:
            for p in oncelik:
                if p in link:
                    return link
        for link in linkler:
            if "t.me" not in link and "telegram" not in link and "google.com" not in link:
                return link
    return None

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun_img.size

        logo_ham = Image.open(LOGO_DOSYA).convert("RGBA")
        logo_w, logo_h = logo_ham.size

        # Hedef genislik: gorselin %18'i, en az 60px en fazla 160px
        hedef_genislik = max(60, min(160, int(w * 0.18)))
        # Orani koru
        oran = logo_h / logo_w
        hedef_yukseklik = int(hedef_genislik * oran)

        logo = logo_ham.resize((hedef_genislik, hedef_yukseklik), Image.LANCZOS)

        bosluk = 12
        x = w - hedef_genislik - bosluk
        y = h - hedef_yukseklik - bosluk

        # Sinir disina tasmamasi icin kontrol
        x = max(0, x)
        y = max(0, y)

        urun_img.paste(logo, (x, y), logo)
        cikti = BytesIO()
        urun_img.convert("RGB").save(cikti, format="JPEG", quality=92)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", "Logo ekleme hatasi: " + str(e))
        return gorsel_bytes

def hashtag_olustur(kategori_hashtagler, magaza):
    hashtagler = list(kategori_hashtagler)
    magaza_tag = MAGAZA_HASHTAG.get(magaza, "")
    if magaza_tag and magaza_tag not in hashtagler:
        hashtagler.append(magaza_tag)
    hashtagler.append("#FırsatPulsu")
    return " ".join(hashtagler)


def yildiz_goster(indirim):
    if indirim >= 80:
        return "⭐⭐⭐⭐⭐"
    elif indirim >= 70:
        return "⭐⭐⭐⭐"
    elif indirim >= 60:
        return "⭐⭐⭐"
    else:
        return "⭐⭐"

def sablon_olustur(metin, indirim, buton_linkleri=None):
    if indirim <= 0:
        return None, None

    magaza = magaza_bul(metin)
    urun   = urun_adi_bul(metin)
    eski_str, yeni_str, eski_val, yeni_val = fiyat_bul(metin)
    link   = link_bul(metin, buton_linkleri)
    stok_kritik = stok_durumu_bul(metin)
    indirim_turu = indirim_turu_bul(metin, urun)
    kat_adi, kat_ikon, kat_hashtagler = kategori_bul(metin)

    magaza_emoji = {
        "Trendyol":    "🛍️",
        "Hepsiburada": "🏪",
        "Amazon TR":   "📦",
        "MediaMarkt":  "🔴",
        "Teknosa":     "💻",
        "Gratis":      "💄",
        "Boyner":      "👗",
        "Morhipo":     "👒",
        "N11":         "🛒",
        "Çiçeksepeti": "🌸",
        "Temu":        "🌍",
        "E-Ticaret":   "🛒",
    }
    m_emoji = magaza_emoji.get(magaza, "🛒")

    yildiz = yildiz_goster(indirim)
    zaman  = datetime.now().strftime("%d %b, %H:%M")
    kat_yazi = {
        "elektronik": "Elektronik",
        "giyim":      "Giyim & Moda",
        "kozmetik":   "Kozmetik",
        "ev":         "Ev & Yaşam",
        "market":     "Market",
        "spor":       "Spor",
        "oyun":       "Oyun & Gaming",
        "bebek":      "Bebek & Çocuk",
        "kitap":      "Kitap & Kırtasiye",
        "genel":      "Alışveriş",
    }.get(kat_adi, "Alışveriş")

    s = []

    # Baslik
    if indirim_turu == "marka":
        s.append("🏷️ <b>MARKA İNDİRİMİ  %" + str(indirim) + " İNDİRİM!</b>  " + yildiz)
    else:
        s.append("🔥 <b>%" + str(indirim) + " İNDİRİM!</b>  " + yildiz)

    s.append("")

    # Kategori + urun
    s.append(kat_ikon + " <b>" + kat_yazi + "</b>")
    if urun:
        s.append("🏷️ " + urun)
    s.append("")

    # Magaza
    s.append(m_emoji + " <b>" + magaza + "</b>")
    s.append("")

    # Fiyat
    if eski_str and yeni_str:
        s.append("💰 <s>" + eski_str + " TL</s>  →  <b>" + yeni_str + " TL</b>")
        s.append("")

    # Stok uyarisi
    if stok_kritik:
        s.append("⚠️ <b>STOKLAR ERİYOR — Hemen yakala!</b>")
        s.append("")

    # Zaman + kanal
    kanal = HEDEF_KANAL.lstrip("@")
    s.append("🕐 " + zaman + "  •  📢 @" + kanal)
    s.append("")

    # Hashtagler
    hashtagler = hashtag_olustur(kat_hashtagler, magaza)
    s.append(hashtagler)

    # Link
    if link:
        s.append("")
        s.append("🔗 <a href='" + link + "'>Fırsata Git</a>")

    metin_sablon = "\n".join(s)
    return metin_sablon, None


# ═══════════════════════════════════════════════════════════════
# MESAJ GONDERME - Bot token varsa inline buton destekli
# ═══════════════════════════════════════════════════════════════
async def mesaj_gonder(metin, link=None, gorsel=None):
    """Bot token varsa inline butonlu gonderir, yoksa linki metne ekler"""
    global bot_client

    if link:
        from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonRow, ReplyInlineMarkup
        buton = ReplyInlineMarkup(rows=[
            KeyboardButtonRow(buttons=[
                KeyboardButtonUrl(text="🔗 Fırsata Git", url=link)
            ])
        ])
    else:
        buton = None

    # Bot client ile gonder (inline buton destekli)
    if bot_client and link:
        try:
            if gorsel:
                msg = await bot_client.send_message(
                    HEDEF_KANAL, metin,
                    parse_mode="html",
                    file=gorsel,
                    buttons=buton
                )
            else:
                msg = await bot_client.send_message(
                    HEDEF_KANAL, metin,
                    parse_mode="html",
                    buttons=buton
                )
            return msg
        except Exception as e:
            log("UYARI", "Bot ile gonderilemedi, userbot deneniyor: " + str(e))

    # Userbot ile gonder (inline buton yok, linki metne ekle)
    if link:
        metin = metin + "\n\n🔗 <a href='" + link + "'>Fırsata Git</a>"
    if gorsel:
        msg = await client.send_message(HEDEF_KANAL, metin, parse_mode="html", file=gorsel)
    else:
        msg = await client.send_message(HEDEF_KANAL, metin, parse_mode="html")
    return msg

# ═══════════════════════════════════════════════════════════════
# GUNUN EN IYI 3 URUNU - her gun 21:00
# ═══════════════════════════════════════════════════════════════
def gunun_urunune_ekle(metin, indirim, buton_linkleri):
    global gunun_urunleri
    link = link_bul(metin, buton_linkleri)
    eski_str, yeni_str, eski_val, yeni_val = fiyat_bul(metin)
    urun = urun_adi_bul(metin) or "Ürün"
    magaza = magaza_bul(metin)
    gunun_urunleri.append({
        "metin": metin,
        "indirim": indirim,
        "link": link,
        "urun": urun,
        "magaza": magaza,
        "eski": eski_str,
        "yeni": yeni_str,
        "buton_linkleri": buton_linkleri
    })
    # En yuksek indirimli 20 urunu tut
    gunun_urunleri = sorted(gunun_urunleri, key=lambda x: x["indirim"], reverse=True)[:20]

async def gunun_en_iyilerini_gonder():
    global gunun_urunleri
    if not gunun_urunleri:
        log("BILGI", "21:00 - Paylasilacak urun yok")
        return

    en_iyi = gunun_urunleri[:3]
    log("BILGI", "21:00 - Gunun en iyi " + str(len(en_iyi)) + " urunu paylasilıyor")

    baslik = "🏆 <b>GÜNÜN EN İYİ FIRSATLARI</b> 🏆\n\n"
    baslik += "Bugün yakalanan en yüksek indirimli ürünler:\n"
    await client.send_message(HEDEF_KANAL, baslik, parse_mode="html")
    await asyncio.sleep(2)

    from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonRow, ReplyInlineMarkup

    for i, urun in enumerate(en_iyi, 1):
        madalya = ["🥇", "🥈", "🥉"][i - 1]
        kat_adi, kat_ikon, _ = kategori_bul(urun["metin"])
        magaza_tag = MAGAZA_HASHTAG.get(urun["magaza"], "")

        s = []
        s.append(madalya + " <b>" + str(i) + ". FIRSAT — %" + str(urun["indirim"]) + " İNDİRİM</b>")
        s.append("")
        s.append(kat_ikon + " " + urun["urun"][:60])
        s.append("")
        if urun["eski"] and urun["yeni"]:
            s.append("💰 <s>" + urun["eski"] + " TL</s>  →  <b>" + urun["yeni"] + " TL</b>")
            s.append("")
        s.append("🏪 " + urun["magaza"])
        s.append("")
        s.append("#GününFırsatı " + magaza_tag + " #FırsatPulsu")
        s.append("📢 @" + HEDEF_KANAL.lstrip("@"))

        metin_sablon = "\n".join(s)

        if urun["link"]:
            metin_sablon += "\n\n🔗 <a href='" + urun["link"] + "'>Fırsata Git</a>"

        try:
            msg = await client.send_message(
                HEDEF_KANAL, metin_sablon,
                parse_mode="html"
            )
            await tepki_ekle(msg)
            await asyncio.sleep(3)
        except Exception as e:
            log("HATA", "Gunun urunu gonderme: " + str(e))

    # Listeyi sifirla
    gunun_urunleri = []
    log("BILGI", "21:00 - Gonderim tamamlandi, liste sifirlandi")


# ═══════════════════════════════════════════════════════════════
# GUNLUK SURPRIZ FIRSAT
# ═══════════════════════════════════════════════════════════════
async def surpriz_firsat_zamanlayici():
    import random
    while True:
        simdi = datetime.now()
        # Her gun 12:00 ile 20:00 arasi rastgele bir saat
        rastgele_saat = random.randint(12, 19)
        rastgele_dakika = random.randint(0, 59)
        hedef = simdi.replace(hour=rastgele_saat, minute=rastgele_dakika, second=0, microsecond=0)
        if simdi >= hedef:
            # Bugun gecmis, yarin rastgele saat
            yarin = simdi + timedelta(days=1)
            rastgele_saat = random.randint(12, 19)
            rastgele_dakika = random.randint(0, 59)
            hedef = yarin.replace(hour=rastgele_saat, minute=rastgele_dakika, second=0, microsecond=0)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", "Surpriz firsat: " + str(hedef.strftime("%H:%M")) + " icin " + str(int(bekle // 3600)) + "s " + str(int((bekle % 3600) // 60)) + "dk bekleniyor")
        await asyncio.sleep(bekle)
        await surpriz_firsat_gonder()

async def surpriz_firsat_gonder():
    global gunun_urunleri
    if not gunun_urunleri:
        log("BILGI", "Surpriz firsat: paylasilacak urun yok")
        return

    import random
    # Listeden rastgele bir urun sec - ama en az %60 indirimli olmali
    uygun = [u for u in gunun_urunleri if u["indirim"] >= 60]
    if not uygun:
        uygun = gunun_urunleri

    urun = random.choice(uygun)
    kat_adi, kat_ikon, _ = kategori_bul(urun["metin"])
    magaza_tag = MAGAZA_HASHTAG.get(urun["magaza"], "")

    from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonRow, ReplyInlineMarkup

    s = []
    s.append("🎰 <b>GÜNLÜK SÜRPRİZ FIRSAT!</b>")
    s.append("")
    s.append("Her gün bir sürpriz fırsat seçiyoruz — bugünkü sürpriz:")
    s.append("")
    s.append(kat_ikon + " " + urun["urun"][:60])
    s.append("")
    if urun["eski"] and urun["yeni"]:
        s.append("💰 <s>" + urun["eski"] + " TL</s>  →  <b>" + urun["yeni"] + " TL</b>")
        s.append("")
    s.append("🏪 " + urun["magaza"])
    s.append("🔥 <b>%" + str(urun["indirim"]) + " İNDİRİM</b>")
    s.append("")
    s.append("#SürprizFırsat #GünlükFırsat " + magaza_tag + " #FırsatPulsu")
    s.append("📢 @" + HEDEF_KANAL.lstrip("@"))

    metin_sablon = "\n".join(s)

    if urun["link"]:
        metin_sablon += "\n\n🔗 <a href='" + urun["link"] + "'>Sürprize Git</a>"

    try:
        msg = await client.send_message(
            HEDEF_KANAL, metin_sablon,
            parse_mode="html"
        )
        await tepki_ekle(msg)
        log("OK", "Surpriz firsat gonderildi: " + urun["urun"][:40])
    except Exception as e:
        log("HATA", "Surpriz firsat gonderme: " + str(e))

async def gunluk_zamanlayici():
    while True:
        simdi = datetime.now()
        # Bugun 21:00
        hedef = simdi.replace(hour=21, minute=0, second=0, microsecond=0)
        if simdi >= hedef:
            # Bugunku 21:00 gecmis, yarin 21:00
            hedef += timedelta(days=1)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", "Gunluk ozet icin " + str(int(bekle // 3600)) + " saat " + str(int((bekle % 3600) // 60)) + " dakika bekleniyor")
        await asyncio.sleep(bekle)
        await gunun_en_iyilerini_gonder()

# ═══════════════════════════════════════════════════════════════
# TEPKI EKLEME
# ═══════════════════════════════════════════════════════════════
async def tepki_ekle(mesaj):
    try:
        await client(SendReactionRequest(
            peer=HEDEF_KANAL,
            msg_id=mesaj.id,
            reaction=[ReactionEmoji(emoticon="🔥")]
        ))
    except Exception as e:
        log("UYARI", "Tepki eklenemedi: " + str(e))

# ═══════════════════════════════════════════════════════════════
# ADMIN BILDIRIM
# ═══════════════════════════════════════════════════════════════
async def admin_bildir(mesaj):
    if not ADMIN_ID:
        return
    try:
        await client.send_message(int(ADMIN_ID), "⚠️ FırsatPulsu:\n" + mesaj)
    except:
        pass

async def baslangic_raporu():
    ist = istatistik_yukle()
    rapor = (
        "✅ FırsatPulsu Bot Başladı\n"
        "📊 Toplam iletilen: " + str(ist.get("toplam", 0)) + "\n"
        "📡 Kaynak kanal: " + str(len(KAYNAK_KANALLAR)) + "\n"
        "🎯 Min indirim: %" + str(MIN_INDIRIM)
    )
    await admin_bildir(rapor)

async def watchdog():
    while True:
        await asyncio.sleep(WATCHDOG_ARALIK)
        ist = istatistik_yukle()
        bugun = datetime.now().strftime("%Y-%m-%d")
        bugunun_sayisi = ist.get("gunluk", {}).get(bugun, 0)
        await admin_bildir(
            "💓 Bot çalışıyor\n"
            "📊 Bugün: " + str(bugunun_sayisi) + " ürün\n"
            "📊 Toplam: " + str(ist.get("toplam", 0))
        )
        gorulmus_temizle()
        istatistik_kaydet()

# ═══════════════════════════════════════════════════════════════
# ANA HANDLER
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    global son_mesaj_zamani
    try:
        metin = markdown_temizle(event.message.text or "")
        indirim = indirim_oranini_bul(metin)
        if indirim < MIN_INDIRIM:
            return

        mid = mesaj_id_olustur(metin)
        if gorulmus_var_mi(mid):
            log("BILGI", "Duplikat atlandi")
            return
        gorulmus_ekle(mid)

        # Buton linklerini topla
        buton_linkleri = []
        try:
            if event.message.buttons:
                for satir in event.message.buttons:
                    for buton in satir:
                        if hasattr(buton, "url") and buton.url:
                            buton_linkleri.append(buton.url)
        except Exception:
            pass

        # Gunun urunleri listesine ekle
        gunun_urunune_ekle(metin, indirim, buton_linkleri)

        # Sablon ve buton
        sablon, inline_buton = sablon_olustur(metin, indirim, buton_linkleri)
        if not sablon:
            return

        # Rate limiting
        loop = asyncio.get_running_loop()
        simdi = loop.time()
        gecen = simdi - son_mesaj_zamani
        if gecen < MESAJ_BEKLEME:
            await asyncio.sleep(MESAJ_BEKLEME - gecen)
        son_mesaj_zamani = loop.time()

        kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"
        magaza = magaza_bul(metin)

        # Gonder
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            try:
                gorsel_bytes = await client.download_media(event.message.media, bytes)
                if gorsel_bytes and len(gorsel_bytes) > 1000:
                    logolu = logo_ekle(gorsel_bytes)
                    buf = BytesIO(logolu)
                    buf.name = "urun.jpg"
                    msg = await client.send_message(
                        HEDEF_KANAL, sablon,
                        file=buf,
                        parse_mode="html"
                    )
                else:
                    msg = await client.send_message(
                        HEDEF_KANAL, sablon,
                        parse_mode="html"
                    )
            except Exception as img_e:
                log("UYARI", "Gorsel hatasi: " + str(img_e))
                msg = await client.send_message(
                    HEDEF_KANAL, sablon,
                    parse_mode="html",
                    buttons=inline_buton
                )
        else:
            msg = await client.send_message(
                HEDEF_KANAL, sablon,
                parse_mode="html",
                buttons=inline_buton
            )

        # Ates tepkisi ekle
        await tepki_ekle(msg)

        istatistik_guncelle(kanal_adi, magaza)
        log("OK", "%" + str(indirim) + " [" + kanal_adi + "] [" + magaza + "] " + metin[:40].replace("\n", " "))

    except FloodWaitError as e:
        log("UYARI", "FloodWait " + str(e.seconds) + "s")
        await asyncio.sleep(e.seconds + 5)
    except ChannelPrivateError:
        log("HATA", "Kanal ozel/kapali")
    except UsernameInvalidError as e:
        log("HATA", "Gecersiz kullanici adi: " + str(e))
    except ChatWriteForbiddenError:
        log("KRITIK", "Yazma izni yok!")
        await admin_bildir("🚨 Hedef kanala yazma izni yok!")
    except Exception as e:
        log("HATA", str(e))

# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════
async def test_gonder():
    testler = [
        {
            "metin": "Philips Tiras Makinesi\n\nIndirimli Fiyat: 299,90 TL\nNormal Fiyat: 899,00 TL\nIndirim: -%66\nStoklar Eriyor!\n\nAmazon TR\nhttps://amazon.com.tr/test",
            "aciklama": "Amazon -%66 stok kritik"
        },
        {
            "metin": "Samsung 65 inc 4K TV\n\nTrendyol urunlerinde %75 indirim var\n\n1.499 TL yerine 374 TL\n\nhttps://trendyol.com/test",
            "aciklama": "Trendyol marka indirimi"
        },
        {
            "metin": "Nike Air Max Spor Ayakkabi\n\nHepsiburada 60% indirim\n\n3.200 TL - 1.280 TL\n\nhttps://hepsiburada.com/test",
            "aciklama": "Hepsiburada giyim"
        },
    ]
    log("TEST", "=== TEST BASLIYOR ===")
    for i, t in enumerate(testler, 1):
        metin = t["metin"]
        indirim = indirim_oranini_bul(metin)
        sablon, buton = sablon_olustur(metin, indirim, [])
        log("TEST", str(i) + ". " + t["aciklama"] + " -> %" + str(indirim))
        if sablon and indirim >= MIN_INDIRIM:
            msg = await client.send_message(
                HEDEF_KANAL,
                "🧪 <b>TEST " + str(i) + "/" + str(len(testler)) + "</b>\n\n" + sablon,
                parse_mode="html",
                buttons=buton
            )
            await tepki_ekle(msg)
            log("TEST", "   Gonderildi!")
        await asyncio.sleep(2)
    log("TEST", "=== TEST TAMAMLANDI ===")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
async def main():
    log("BILGI", "═══ FırsatPulsu v5 ═══")
    log("BILGI", "Min indirim : %" + str(MIN_INDIRIM))
    log("BILGI", "Kaynak kanal: " + str(len(KAYNAK_KANALLAR)))

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    while True:
        try:
            await client.start()
            log("OK", "Baglandi! Kanallar dinleniyor...")

            # Bot token varsa bot client'i da baslat
            global bot_client
            if BOT_TOKEN:
                try:
                    bot_client = TelegramClient("bot_session", API_ID, API_HASH)
                    await bot_client.start(bot_token=BOT_TOKEN)
                    log("OK", "Bot client baglandi - inline butonlar aktif!")
                except Exception as e:
                    log("UYARI", "Bot client baslanamadi: " + str(e))
                    bot_client = None
            else:
                log("BILGI", "BOT_TOKEN yok - linkler metin olarak eklenecek")
            await baslangic_raporu()

            if os.environ.get("TEST_MODE", "0") == "1":
                await test_gonder()

            asyncio.ensure_future(watchdog())
            asyncio.ensure_future(gunluk_zamanlayici())
            asyncio.ensure_future(surpriz_firsat_zamanlayici())
            await client.run_until_disconnected()
        except Exception as e:
            log("HATA", "Baglanti koptu: " + str(e))
            log("BILGI", "30s sonra yeniden baglaniliyor...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
