import os
import asyncio
import re
import json
import hashlib
import unicodedata
import random
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
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))
MIN_KALITE     = int(os.environ.get("MIN_KALITE", "15"))
KUYRUK_BEKLEME = int(os.environ.get("KUYRUK_BEKLEME", "180"))

# Kara liste - bu kelimeleri iceren urunleri atla
KARA_LISTE = [
    "corap", "çorap", "kilif", "kılıf", "sticker",
    "ekran koruyucu", "defter", "kalem", "ase"
]

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
LOGO_DOSYA      = "logo.PNG"
GORULMUS_MAX    = 3000
GORULMUS_TTL    = 7 * 24 * 3600
WATCHDOG_ARALIK = 3600
MARKA_SPAM_LIMIT = 3
MARKA_SPAM_SURE  = 3600

# ═══════════════════════════════════════════════════════════════
# KATEGORİ TANIMLARI
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
gorulmus_cache    = None
istatistik_cache  = None
ist_degisim_sayac = 0
gunun_urunleri    = []
marka_son_mesaj   = {}
bot_client        = None
mesaj_kuyrugu     = None  # asyncio.Queue - main'de baslatilir

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ═══════════════════════════════════════════════════════════════
# LOGLAMA
# ═══════════════════════════════════════════════════════════════
def log(seviye, mesaj):
    print("[" + datetime.now().strftime("%H:%M:%S") + "] [" + seviye + "] " + mesaj)

# ═══════════════════════════════════════════════════════════════
# GÖRÜLMÜŞ (duplikat önleme)
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
        log("BILGI", str(temizlenen) + " eski gorulmus kaydi temizlendi")
    gorulmus_kaydet()

def gorulmus_var_mi(mid):
    return mid in gorulmus_yukle()

def gorulmus_ekle(mid):
    global gorulmus_cache
    gorulmus_yukle()
    gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()
    gorulmus_kaydet()

# ═══════════════════════════════════════════════════════════════
# İSTATİSTİK
# ═══════════════════════════════════════════════════════════════
def istatistik_yukle():
    global istatistik_cache
    if istatistik_cache is not None:
        return istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "r") as f:
            istatistik_cache = json.load(f)
    except:
        istatistik_cache = {"toplam": 0, "kanallar": {}, "gunluk": {}, "kategoriler": {}, "magazalar": {}}
    return istatistik_cache

def istatistik_kaydet():
    global istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "w") as f:
            json.dump(istatistik_cache, f)
    except:
        pass

def istatistik_guncelle(kanal_adi, magaza, kategori):
    global ist_degisim_sayac
    ist = istatistik_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
    ist["magazalar"][magaza] = ist["magazalar"].get(magaza, 0) + 1
    ist["kategoriler"][kategori] = ist["kategoriler"].get(kategori, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    ist_degisim_sayac += 1
    if ist_degisim_sayac >= 10:
        istatistik_kaydet()
        ist_degisim_sayac = 0

# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════
def emoji_temizle(metin):
    if not metin:
        return ""
    return "".join(k for k in metin if unicodedata.category(k) not in ("So", "Sm", "Sk")).strip()

def markdown_temizle(metin):
    if not metin:
        return metin
    metin = re.sub(r'[*]{1,3}([^*]+)[*]{1,3}', r'\1', metin)
    metin = re.sub(r'[_]{1,2}([^_]+)[_]{1,2}', r'\1', metin)
    metin = re.sub(r'[`]([^`]+)[`]', r'\1', metin)
    metin = re.sub(r'[~]{1,2}([^~]+)[~]{1,2}', r'\1', metin)
    metin = re.sub(r'[|]{2}([^|]+)[|]{2}', r'\1', metin)
    return metin

def benzerlik_anahtari(metin):
    # Hem metin hash'i hem de urun+fiyat hash'i ile duplikat yakala
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

def marka_spam_kontrol(magaza):
    global marka_son_mesaj
    simdi = datetime.now(timezone.utc).timestamp()
    if magaza not in marka_son_mesaj:
        marka_son_mesaj[magaza] = []
    marka_son_mesaj[magaza] = [t for t in marka_son_mesaj[magaza] if simdi - t < MARKA_SPAM_SURE]
    if len(marka_son_mesaj[magaza]) >= MARKA_SPAM_LIMIT:
        return True
    marka_son_mesaj[magaza].append(simdi)
    return False

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    ml = metin.lower()

    # 1. Standart kaliplar
    kaliplar = [
        r"-\s*%\s*(\d+)",
        r"indirim\s*:\s*-?\s*%\s*(\d+)",
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
    ]
    for kalip in kaliplar:
        eslesme = re.findall(kalip, ml)
        if eslesme:
            degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
            if degerler:
                return max(degerler)

    # 2. X al Y ode
    al_ode = re.findall(r"(\d+)\s*al\s*(\d+)\s*(?:öde|ode)", ml)
    if al_ode:
        al, ode = int(al_ode[0][0]), int(al_ode[0][1])
        if al > ode > 0:
            ind = round((1 - ode / al) * 100)
            if 1 <= ind <= 99:
                return ind

    # 3. Linklerin icindeki %xx'leri yoksayarak genel % ara
    metin_linksiz = re.sub(r'https?://\S+', '', metin)
    eslesme = re.findall(r"%(\d{1,2})\b", metin_linksiz)
    degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
    if degerler:
        return max(degerler)

    # 4. Kupon / sepette indirim
    if re.search(r"kupon|sepette\s*[\d.,]+\s*tl|sepete\s*\d+\s*adet", ml):
        return 30

    # 5. Stok uyarisi + fiyat
    stok = any(k in ml for k in ["stoklar eriyor", "son stok", "dip fiyat", "en düşük", "kaçmaz", "hemen yakala"])
    fiyat = bool(re.search(r"[\d.,]+\s*(?:tl|₺)", ml))
    if stok and fiyat:
        return 50

    # 6. Magaza linki
    if any(x in ml for x in ["hb.biz", "trendyol.com", "ty.gl", "amazon.com.tr", "n11.com", "sl.n11.com"]):
        return 20

    return 0

def fiyat_parse(s):
    try:
        s = s.strip()
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def fiyat_bul(metin):
    if not metin:
        return None, None, 0, 0

    # 1. Etiketli format: "Indirimli Fiyat: X TL / Normal Fiyat: Y TL"
    indirimli = re.findall(r"(?:indirimli\s*fiyat|sale\s*price)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.IGNORECASE)
    normal = re.findall(r"(?:normal\s*fiyat|liste\s*fiyat|piyasa)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.IGNORECASE)
    if indirimli and normal:
        yv = fiyat_parse(indirimli[0])
        ev = fiyat_parse(normal[0])
        if ev > yv > 0:
            return normal[0], indirimli[0], ev, yv

    # 2. ₺ sembolu ve TL
    bulunan = re.findall(r"₺\s*([\d.,]+)", metin) + re.findall(r"([\d.,]+)\s*(?:TL|tl|lira)", metin)
    if len(bulunan) >= 2:
        degerler = [(fiyat_parse(f), f) for f in bulunan if fiyat_parse(f) > 0]
        if len(degerler) >= 2:
            sirali = sorted(degerler, reverse=True)
            ev, es = sirali[0]
            yv, ys = sirali[-1]
            if ev > yv:
                return es, ys, ev, yv
    elif len(bulunan) == 1:
        return None, bulunan[0], 0, fiyat_parse(bulunan[0])

    return None, None, 0, 0

def magaza_bul(metin):
    ml = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol", "trendyol"), ("Hepsiburada", "hepsiburada"),
        ("Amazon TR", "amazon"), ("MediaMarkt", "mediamarkt"),
        ("Teknosa", "teknosa"), ("Gratis", "gratis"), ("Boyner", "boyner"),
        ("N11", "n11.com"), ("Çiçeksepeti", "ciceksepeti"), ("Temu", "temu.com"),
    ]:
        if anahtar in ml:
            return magaza
    return "E-Ticaret"

def kategori_bul(metin):
    ml = (metin or "").lower()
    for kat_adi, kat in KATEGORILER.items():
        if any(a in ml for a in kat["anahtar"]):
            return kat_adi, kat["ikon"], kat["hashtag"]
    return "genel", "🛍️", ["#Fırsat", "#İndirim"]

def stok_durumu_bul(metin):
    ml = (metin or "").lower()
    return any(k in ml for k in ["stoklar eriyor", "son stok", "tükeniyor", "sınırlı stok"])

def indirim_turu_bul(metin):
    ml = (metin or "").lower()
    kaliplar = [r"\w+\s*(?:urunlerinde|markasinda|serisinde)\s*%\d+", r"tum\s*\w*\s*urunlerde", r"secili\s*\w*\s*urunlerde"]
    return "marka" if any(re.search(k, ml) for k in kaliplar) else "urun"

def urun_adi_bul(metin):
    if not metin:
        return None
    for satir in [s.strip() for s in metin.split("\n") if s.strip()]:
        temiz = emoji_temizle(satir)
        if (len(temiz) >= 8 and not satir.startswith("#") and not satir.startswith("@")
                and "http" not in satir and "TL" not in satir and "₺" not in satir
                and not re.search(r"\d+%|%\d+", satir)):
            return temiz[:80]
    return None

def link_bul(metin, buton_linkleri=None):
    oncelik = ["trendyol.com", "hepsiburada.com", "amazon.com.tr", "mediamarkt.com.tr",
               "teknosa.com", "ty.gl", "hb.gl", "n11.com", "ciceksepeti.com",
               "aliexpress.com", "sl.n11.com", "hb.biz"]
    if buton_linkleri:
        for bl in buton_linkleri:
            if any(p in bl for p in oncelik):
                return bl
        for bl in buton_linkleri:
            if "google.com" not in bl and "t.me" not in bl:
                return bl
    if metin:
        linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
        for link in linkler:
            if any(p in link for p in oncelik):
                return link
        for link in linkler:
            if "t.me" not in link and "google.com" not in link:
                return link
    return None

def kupon_bul(metin):
    if not metin:
        return None
    for kalip in [r"kupon\s*[:\-]?\s*([A-Z0-9]{4,20})", r"indirim\s*kodu?\s*[:\-]?\s*([A-Z0-9]{4,20})"]:
        eslesme = re.findall(kalip, metin, re.IGNORECASE)
        if eslesme:
            return eslesme[0].upper()
    return None

def minimum_siparis_bul(metin):
    if not metin:
        return None
    for kalip in [r"(\d+)\s*adet\s*al[ıi]mda", r"min(?:imum)?\s*(\d+)\s*(?:tl|adet)", r"(\d[\d.,]*)\s*tl\s*alışverişte"]:
        eslesme = re.findall(kalip, metin, re.IGNORECASE)
        if eslesme:
            return eslesme[0]
    return None

def mesaj_kalite_skoru(metin, indirim, buton_linkleri):
    skor = 0
    if indirim >= 50:   skor += 40
    elif indirim >= 30: skor += 25
    else:               skor += 10
    if link_bul(metin, buton_linkleri): skor += 20
    e, y, ev, yv = fiyat_bul(metin)
    if e and y:   skor += 20
    elif y:       skor += 10
    if urun_adi_bul(metin): skor += 15
    if stok_durumu_bul(metin): skor += 5
    return skor

def ozel_etiket(metin, indirim):
    ml = metin.lower()
    if any(k in ml for k in ["flash", "anlık", "saatlik"]):   return "⚡ FLASH SALE"
    if any(k in ml for k in ["hediye", "ücretsiz kargo"]):    return "🎁 HEDİYE KAMPANYA"
    if any(k in ml for k in ["son gün", "bugün bitiyor"]):    return "⏰ SON GÜN"
    if indirim >= 70:                                          return "🏆 SÜPER FIRSAT"
    return None

def yildiz_goster(indirim):
    if indirim >= 80: return "⭐⭐⭐⭐⭐"
    if indirim >= 70: return "⭐⭐⭐⭐"
    if indirim >= 60: return "⭐⭐⭐"
    return "⭐⭐"

def akilli_baslik(indirim, indirim_turu):
    if indirim_turu == "marka":
        return "🏷️ <b>MARKA İNDİRİMİ — %" + str(indirim) + "</b>"
    if indirim >= 70:   return "🔥 <b>YANGIN FİYAT — %" + str(indirim) + " İNDİRİM</b>"
    if indirim >= 50:   return "🔥 <b>BÜYÜK İNDİRİM — %" + str(indirim) + "</b>"
    if indirim >= 30:   return "💰 <b>FIRSAT — %" + str(indirim) + " İNDİRİM</b>"
    return "💰 <b>%" + str(indirim) + " İNDİRİM</b>"

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun_img.size
        logo_ham = Image.open(LOGO_DOSYA).convert("RGBA")
        lw, lh = logo_ham.size
        hedef_w = max(60, min(160, int(w * 0.18)))
        hedef_h = int(hedef_w * (lh / lw))
        logo = logo_ham.resize((hedef_w, hedef_h), Image.LANCZOS)
        bosluk = 12
        x = max(0, w - hedef_w - bosluk)
        y = max(0, h - hedef_h - bosluk)
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
    mt = MAGAZA_HASHTAG.get(magaza, "")
    if mt and mt not in hashtagler:
        hashtagler.append(mt)
    hashtagler.append("#FırsatPulsu")
    return " ".join(hashtagler)

# ═══════════════════════════════════════════════════════════════
# ŞABLON OLUŞTURMA
# ═══════════════════════════════════════════════════════════════
def sablon_olustur(metin, indirim, buton_linkleri=None):
    if indirim <= 0:
        return None

    magaza       = magaza_bul(metin)
    urun         = urun_adi_bul(metin)
    eski_str, yeni_str, _, _ = fiyat_bul(metin)
    link         = link_bul(metin, buton_linkleri)
    stok_kritik  = stok_durumu_bul(metin)
    indirim_turu = indirim_turu_bul(metin)
    kat_adi, kat_ikon, kat_hashtagler = kategori_bul(metin)
    kupon        = kupon_bul(metin)
    min_siparis  = minimum_siparis_bul(metin)
    etiket       = ozel_etiket(metin, indirim)
    m_emoji      = MAGAZA_EMOJI.get(magaza, "🛒")
    kat_yazi     = KATEGORI_YAZI.get(kat_adi, "Alışveriş")
    kanal        = HEDEF_KANAL.lstrip("@")
    hashtagler   = hashtag_olustur(kat_hashtagler, magaza)
    baslik       = akilli_baslik(indirim, indirim_turu)
    zaman        = datetime.now().strftime("%H:%M")
    yildiz       = yildiz_goster(indirim)

    s = []

    if indirim_turu == "marka":
        s.append(baslik)
        s.append("")
        s.append(m_emoji + " <b>" + magaza + "</b>  •  " + kat_ikon + " " + kat_yazi)
        s.append("")
        s.append("Seçili ürünlerde <b>%" + str(indirim) + "'ye varan</b> indirim")
        if etiket:
            s.append(etiket)
        s.append("")
        if kupon:
            s.append("🎟️ Kupon: <code>" + kupon + "</code>")
        if min_siparis:
            s.append("🛒 Min. " + min_siparis + " alışverişte geçerli")
        s.append("⏰ Sınırlı süre!  •  🕐 " + zaman)
    else:
        s.append(baslik + "  " + yildiz)
        if etiket:
            s.append(etiket)
        s.append("")
        if urun:
            s.append("📌 <b>" + urun + "</b>")
        s.append(kat_ikon + " " + kat_yazi)
        s.append("")
        if eski_str and yeni_str:
            s.append("🏷️ Normal Fiyat:    <s>" + eski_str + " TL</s>")
            s.append("💰 İndirimli Fiyat: <b>" + yeni_str + " TL</b>")
        elif yeni_str:
            s.append("💰 Fiyat: <b>" + yeni_str + " TL</b>")
        s.append("")
        s.append(m_emoji + " <b>" + magaza + "</b>  •  🕐 " + zaman)
        if stok_kritik:
            s.append("⚠️ <b>Son stoklar!</b>")
        if kupon:
            s.append("🎟️ Kupon: <code>" + kupon + "</code>")
        if min_siparis:
            s.append("🛒 Min. " + min_siparis + " alımda geçerli")

    s.append("")
    s.append("──────────────────────")
    s.append(hashtagler)
    s.append("📢 @" + kanal)

    return "\n".join(s)

# ═══════════════════════════════════════════════════════════════
# KUYRUK SİSTEMİ (3 dakika arayla gönderim)
# ═══════════════════════════════════════════════════════════════
async def kuyruk_worker():
    global mesaj_kuyrugu, bot_client
    log("BILGI", "Kuyruk worker aktif")
    while True:
        try:
            sablon, gorsel_medya, link, magaza, kat_adi, kanal_adi, indirim = await mesaj_kuyrugu.get()

            # Inline buton
            buton = None
            if link:
                from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonRow, ReplyInlineMarkup
                buton = ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[
                    KeyboardButtonUrl(text="🔗 Fırsata Git", url=link)
                ])])

            final_metin = sablon
            if link and not buton:
                final_metin = sablon + "\n\n🔗 <a href='" + link + "'>Fırsata Git</a>"

            msg = None

            # Gorsel gonder
            if gorsel_medya:
                try:
                    # Once bytes olarak indir, logo ekle
                    gorsel_bytes = await client.download_media(gorsel_medya, bytes)
                    if gorsel_bytes and len(gorsel_bytes) > 1000:
                        logolu = logo_ekle(gorsel_bytes)
                        buf = BytesIO(logolu)
                        buf.name = "urun.jpg"
                        if bot_client and link:
                            msg = await bot_client.send_message(HEDEF_KANAL, final_metin, file=buf, parse_mode="html", buttons=buton)
                        else:
                            msg = await client.send_message(HEDEF_KANAL, final_metin, file=buf, parse_mode="html")
                    else:
                        raise Exception("Gorsel cok kucuk")
                except Exception as img_e:
                    log("UYARI", "Gorsel: " + str(img_e))
                    if bot_client and link:
                        msg = await bot_client.send_message(HEDEF_KANAL, final_metin, parse_mode="html", buttons=buton)
                    else:
                        msg = await client.send_message(HEDEF_KANAL, final_metin, parse_mode="html")
            else:
                if bot_client and link:
                    msg = await bot_client.send_message(HEDEF_KANAL, final_metin, parse_mode="html", buttons=buton)
                else:
                    msg = await client.send_message(HEDEF_KANAL, final_metin, parse_mode="html")

            if msg:
                await tepki_ekle(msg)

            istatistik_guncelle(kanal_adi, magaza, kat_adi)
            log("OK", "Gonderildi [" + magaza + "] %" + str(indirim) + " | Kuyrukta: " + str(mesaj_kuyrugu.qsize()))

            mesaj_kuyrugu.task_done()
            await asyncio.sleep(KUYRUK_BEKLEME)

        except Exception as e:
            log("HATA", "Worker: " + str(e))
            await asyncio.sleep(5)

# ═══════════════════════════════════════════════════════════════
# TEPKİ EKLEME
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
# GÜNÜN EN İYİ 3 ÜRÜNÜ (21:00)
# ═══════════════════════════════════════════════════════════════
def gunun_urunune_ekle(metin, indirim, buton_linkleri):
    global gunun_urunleri
    e, y, _, _ = fiyat_bul(metin)
    gunun_urunleri.append({
        "metin": metin, "indirim": indirim,
        "link": link_bul(metin, buton_linkleri),
        "urun": urun_adi_bul(metin) or "Ürün",
        "magaza": magaza_bul(metin),
        "eski": e, "yeni": y,
    })
    gunun_urunleri.sort(key=lambda x: x["indirim"], reverse=True)
    gunun_urunleri[:] = gunun_urunleri[:20]

async def gunun_en_iyilerini_gonder():
    global gunun_urunleri
    if not gunun_urunleri:
        log("BILGI", "21:00 - Urun yok")
        return
    en_iyi = gunun_urunleri[:3]
    log("BILGI", "21:00 - " + str(len(en_iyi)) + " urun paylasilıyor")
    try:
        await client.send_message(HEDEF_KANAL,
            "🏆 <b>GÜNÜN EN İYİ FIRSATLARI</b> 🏆\n\nBugün yakalanan en yüksek indirimli ürünler:",
            parse_mode="html")
        await asyncio.sleep(3)
    except Exception as e:
        log("HATA", "Baslik: " + str(e))
    for i, u in enumerate(en_iyi, 1):
        madalya = ["🥇", "🥈", "🥉"][i-1]
        _, kat_ikon, _ = kategori_bul(u["metin"])
        mt = MAGAZA_HASHTAG.get(u["magaza"], "")
        s = [madalya + " <b>" + str(i) + ". FIRSAT — %" + str(u["indirim"]) + " İNDİRİM</b>", ""]
        s.append(kat_ikon + " " + u["urun"][:60])
        s.append("")
        if u["eski"] and u["yeni"]:
            s.append("🏷️ Normal:    <s>" + u["eski"] + " TL</s>")
            s.append("💰 İndirimli: <b>" + u["yeni"] + " TL</b>")
            s.append("")
        s.append("🏪 " + u["magaza"])
        s.append("")
        s.append("#GününFırsatı " + mt + " #FırsatPulsu")
        s.append("📢 @" + HEDEF_KANAL.lstrip("@"))
        if u.get("link"):
            s.append("\n🔗 <a href='" + u["link"] + "'>Fırsata Git</a>")
        try:
            msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
            if msg:
                await tepki_ekle(msg)
            await asyncio.sleep(5)
        except Exception as e:
            log("HATA", "Gunun urunu: " + str(e))
    gunun_urunleri.clear()
    log("BILGI", "21:00 - Tamamlandi")

async def gunluk_zamanlayici():
    while True:
        simdi = datetime.now()
        hedef = simdi.replace(hour=21, minute=0, second=0, microsecond=0)
        if simdi >= hedef:
            hedef += timedelta(days=1)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", "Gunluk ozet: " + str(int(bekle//3600)) + "s " + str(int((bekle%3600)//60)) + "dk sonra")
        await asyncio.sleep(bekle)
        await gunun_en_iyilerini_gonder()

# ═══════════════════════════════════════════════════════════════
# SÜRPRİZ FIRSAT
# ═══════════════════════════════════════════════════════════════
async def surpriz_firsat_gonder():
    if not gunun_urunleri:
        return
    uygun = [u for u in gunun_urunleri if u["indirim"] >= 60] or gunun_urunleri
    u = random.choice(uygun)
    _, kat_ikon, _ = kategori_bul(u["metin"])
    mt = MAGAZA_HASHTAG.get(u["magaza"], "")
    s = ["🎰 <b>GÜNLÜK SÜRPRİZ FIRSAT!</b>", "", "Her gün bir sürpriz fırsat — bugünkü sürpriz:", ""]
    s.append(kat_ikon + " <b>" + u["urun"][:60] + "</b>")
    s.append("")
    if u["eski"] and u["yeni"]:
        s.append("🏷️ Normal:    <s>" + u["eski"] + " TL</s>")
        s.append("💰 İndirimli: <b>" + u["yeni"] + " TL</b>")
        s.append("")
    s.append("🏪 " + u["magaza"] + "  •  🔥 <b>%" + str(u["indirim"]) + " İNDİRİM</b>")
    s.append("")
    s.append("#SürprizFırsat #GünlükFırsat " + mt + " #FırsatPulsu")
    s.append("📢 @" + HEDEF_KANAL.lstrip("@"))
    if u.get("link"):
        s.append("\n🔗 <a href='" + u["link"] + "'>Fırsata Git</a>")
    try:
        msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
        if msg:
            await tepki_ekle(msg)
        log("OK", "Surpriz firsat: " + u["urun"][:40])
    except Exception as e:
        log("HATA", "Surpriz firsat: " + str(e))

async def surpriz_firsat_zamanlayici():
    while True:
        simdi = datetime.now()
        saat = random.randint(12, 19)
        dakika = random.randint(0, 59)
        hedef = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
        if simdi >= hedef:
            hedef = (simdi + timedelta(days=1)).replace(
                hour=random.randint(12, 19), minute=random.randint(0, 59), second=0, microsecond=0)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", "Surpriz firsat: " + hedef.strftime("%H:%M") + " icin bekleniyor")
        await asyncio.sleep(bekle)
        await surpriz_firsat_gonder()

# ═══════════════════════════════════════════════════════════════
# HAFTALIK RAPOR (Pazar 20:00)
# ═══════════════════════════════════════════════════════════════
async def haftalik_rapor_gonder():
    ist = istatistik_yukle()
    istatistik_kaydet()
    simdi = datetime.now()
    haftalik = sum(ist.get("gunluk", {}).get((simdi - timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(7))
    kategoriler = ist.get("kategoriler", {})
    en_kat = max(kategoriler, key=kategoriler.get) if kategoriler else "genel"
    magazalar = ist.get("magazalar", {})
    en_mag = max(magazalar, key=magazalar.get) if magazalar else "Bilinmiyor"
    kanal = HEDEF_KANAL.lstrip("@")
    s = [
        "📊 <b>HAFTALIK FIRSAT RAPORU</b>", "",
        "Bu hafta <b>" + str(haftalik) + " fırsat</b> paylaştık!", "",
        "🏆 En popüler kategori: <b>" + KATEGORI_YAZI.get(en_kat, en_kat) + "</b>",
        "🏪 En çok paylaşılan: <b>" + en_mag + "</b>",
        "📈 Toplam: <b>" + str(ist.get("toplam", 0)) + " fırsat</b>", "",
        "Bildirimleri açık tutun! 🔔", "",
        "#HaftalıkRapor #FırsatPulsu",
        "📢 @" + kanal,
    ]
    try:
        msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
        if msg:
            await tepki_ekle(msg)
        log("OK", "Haftalik rapor gonderildi")
    except Exception as e:
        log("HATA", "Haftalik rapor: " + str(e))

async def haftalik_zamanlayici():
    while True:
        simdi = datetime.now()
        gunler_pazar = (6 - simdi.weekday()) % 7
        if gunler_pazar == 0 and simdi.hour >= 20:
            gunler_pazar = 7
        hedef = (simdi + timedelta(days=gunler_pazar)).replace(hour=20, minute=0, second=0, microsecond=0)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", "Haftalik rapor: " + str(int(bekle//3600)) + "s sonra")
        await asyncio.sleep(bekle)
        await haftalik_rapor_gonder()

# ═══════════════════════════════════════════════════════════════
# KANAL DOĞRULAMA
# ═══════════════════════════════════════════════════════════════
async def kanallari_dogrula():
    global KAYNAK_KANALLAR
    gecerli = []
    log("BILGI", str(len(KAYNAK_KANALLAR)) + " kanal dogrulanıyor...")
    for kanal in KAYNAK_KANALLAR:
        try:
            await client.get_entity(kanal)
            gecerli.append(kanal)
            log("OK", kanal + " aktif")
        except Exception as e:
            log("UYARI", kanal + " bulunamadi: " + str(e))
    KAYNAK_KANALLAR = gecerli
    log("BILGI", str(len(gecerli)) + " kanal aktif")

# ═══════════════════════════════════════════════════════════════
# ADMİN & WATCHDOG
# ═══════════════════════════════════════════════════════════════
async def admin_bildir(mesaj):
    if not ADMIN_ID:
        return
    try:
        await client.send_message(int(ADMIN_ID), "FırsatPulsu:\n" + mesaj)
    except:
        pass

async def watchdog():
    while True:
        await asyncio.sleep(WATCHDOG_ARALIK)
        ist = istatistik_yukle()
        bugun = datetime.now().strftime("%Y-%m-%d")
        kuyruk_boyut = mesaj_kuyrugu.qsize() if mesaj_kuyrugu else 0
        await admin_bildir(
            "Bot calisiyor\n"
            "Bugun: " + str(ist.get("gunluk", {}).get(bugun, 0)) + "\n"
            "Toplam: " + str(ist.get("toplam", 0)) + "\n"
            "Kuyruk: " + str(kuyruk_boyut)
        )
        gorulmus_temizle()
        istatistik_kaydet()

# ═══════════════════════════════════════════════════════════════
# ANA HANDLER
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_dinle(event):
    try:
        ham_metin = markdown_temizle(event.message.text or "")

        # Kara liste kontrolu
        for yasak in KARA_LISTE:
            if yasak in ham_metin.lower():
                return

        indirim = indirim_oranini_bul(ham_metin)
        if indirim < MIN_INDIRIM:
            return

        # Duplikat kontrolu
        mid = benzerlik_anahtari(ham_metin)
        if gorulmus_var_mi(mid):
            return
        gorulmus_ekle(mid)

        # Buton linklerini topla
        buton_linkleri = []
        try:
            if event.message.buttons:
                for row in event.message.buttons:
                    for btn in row:
                        if hasattr(btn, "url") and btn.url:
                            buton_linkleri.append(btn.url)
        except:
            pass

        # Link zorunlu
        link = link_bul(ham_metin, buton_linkleri)
        if not link:
            return

        # Kalite skoru
        skor = mesaj_kalite_skoru(ham_metin, indirim, buton_linkleri)
        if skor < MIN_KALITE:
            log("BILGI", "Dusuk kalite (skor:" + str(skor) + ") atlandi")
            return

        # Marka spam kontrolu
        magaza = magaza_bul(ham_metin)
        if marka_spam_kontrol(magaza):
            log("BILGI", magaza + " spam limiti - atlandi")
            return

        # Sablon olustur
        sablon = sablon_olustur(ham_metin, indirim, buton_linkleri)
        if not sablon:
            return

        # Gorsel (direkt obje olarak al - bayt indirme yok, hizli!)
        gorsel_medya = None
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            gorsel_medya = event.message.media

        # Gunun urunlerine ekle
        gunun_urunune_ekle(ham_metin, indirim, buton_linkleri)

        kat_adi, _, _ = kategori_bul(ham_metin)
        kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"

        # Kuyruga ekle
        await mesaj_kuyrugu.put((sablon, gorsel_medya, link, magaza, kat_adi, kanal_adi, indirim))
        log("BILGI", "Kuyruga eklendi [" + magaza + "] %" + str(indirim) + " | Kuyruk: " + str(mesaj_kuyrugu.qsize()))

    except Exception as e:
        log("HATA", str(type(e).__name__) + ": " + str(e))

# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════
async def test_gonder():
    testler = [
        {"metin": "Philips Tiras Makinesi\n\nIndirimli Fiyat: 299,90 TL\nNormal Fiyat: 899,00 TL\nIndirim: -%66\nStoklar Eriyor!\n\nAmazon TR\nhttps://amazon.com.tr/test", "aciklama": "Amazon %66"},
        {"metin": "Samsung 65 inc 4K TV\n\nTrendyol urunlerinde %75 indirim var\n\n1.499 TL yerine 374 TL\n\nhttps://trendyol.com/test", "aciklama": "Trendyol marka"},
        {"metin": "Nike Air Max Spor Ayakkabi\n\nHepsiburada 60% indirim\n\n3.200 TL - 1.280 TL\n\nhttps://hepsiburada.com/test", "aciklama": "Hepsiburada giyim"},
    ]
    log("TEST", "=== TEST BASLIYOR ===")
    for i, t in enumerate(testler, 1):
        metin = t["metin"]
        indirim = indirim_oranini_bul(metin)
        skor = mesaj_kalite_skoru(metin, indirim, [])
        sablon = sablon_olustur(metin, indirim, [])
        link = link_bul(metin)
        log("TEST", str(i) + ". " + t["aciklama"] + " -> %" + str(indirim) + " skor:" + str(skor))
        if sablon and link:
            gunun_urunune_ekle(metin, indirim, [])
            await mesaj_kuyrugu.put((sablon, None, link, magaza_bul(metin), kategori_bul(metin)[0], "test", indirim))
            log("TEST", "   Kuyruga eklendi")
        await asyncio.sleep(1)
    await asyncio.sleep(5)
    await gunun_en_iyilerini_gonder()
    await asyncio.sleep(3)
    await surpriz_firsat_gonder()
    await asyncio.sleep(3)
    await haftalik_rapor_gonder()
    log("TEST", "=== TUM TESTLER TAMAMLANDI ===")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
async def main():
    global mesaj_kuyrugu, bot_client
    log("SISTEM", "FırsatPulsu v7 FINAL baslatiliyor...")
    log("SISTEM", "Min indirim: %" + str(MIN_INDIRIM) + " | Min kalite: " + str(MIN_KALITE) + " | Kuyruk bekleme: " + str(KUYRUK_BEKLEME) + "s")

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    mesaj_kuyrugu = asyncio.Queue()

    while True:
        try:
            await client.start()
            log("OK", "Baglandi!")

            if BOT_TOKEN:
                try:
                    bot_client = TelegramClient("bot_session", API_ID, API_HASH)
                    await bot_client.start(bot_token=BOT_TOKEN)
                    log("OK", "Bot client aktif - inline butonlar calisiyor")
                except Exception as e:
                    log("UYARI", "Bot client: " + str(e))
                    bot_client = None

            await kanallari_dogrula()

            await admin_bildir(
                "Bot Basladi v7\n"
                "Kanal: " + str(len(KAYNAK_KANALLAR)) + "\n"
                "Min indirim: %" + str(MIN_INDIRIM)
            )

            if os.environ.get("TEST_MODE", "0") == "1":
                await test_gonder()

            asyncio.ensure_future(kuyruk_worker())
            asyncio.ensure_future(watchdog())
            asyncio.ensure_future(gunluk_zamanlayici())
            asyncio.ensure_future(surpriz_firsat_zamanlayici())
            asyncio.ensure_future(haftalik_zamanlayici())

            await client.run_until_disconnected()

        except Exception as e:
            log("HATA", "Baglanti koptu: " + str(e))
            log("BILGI", "30s sonra yeniden baglaniliyor...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())