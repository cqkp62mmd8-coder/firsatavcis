import os
import asyncio
import re
import json
import hashlib
import unicodedata
from io import BytesIO
from datetime import datetime, timezone
from PIL import Image
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaPhoto

# === AYARLAR ===
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL  = os.environ.get("CHANNEL_ID", "")
ADMIN_ID     = os.environ.get("ADMIN_ID", "")
MIN_INDIRIM  = int(os.environ.get("MIN_INDIRIM", "50"))

KAYNAK_KANALLAR = [
    # Buyuk ve aktif kanallar
    "@amazonsicakfirsatlar",        # Amazon TR - en buyuk
    "@donanimhabersicakfirsatlar",  # DH Sicak Firsatlar - teknoloji
    "@firsatmerkez",                # Trendyol odakli
    "@yurticifirsat",               # Yurtici Firsatlari - karma
    "@indirimhabercisi",            # Indirim kuponu + link
    "@uygunlasohbet",               # Uygunla - karma
    "@indirimdeal",                 # Indirim Deal
    "@firsatmerkezi",               # Firsat Merkezi
    "@firsatavcilari01",            # Firsat Avcilari
    # Yeni eklenenler
    "@firsatpaylasim",              # Turkiye'nin en populer kanallarindan
    "@yurtdisifirsat",              # Yurtdisi + Amazon EU
    "@firsatvakti",                 # Firsat Vakti
    "@Firsaturun00",                # Firsat Urun
    "@firsatrobotu",                # Firsat Robotu - otomatik
    "@teknofirsat",                 # Teknoloji odakli
]

# Kara liste devre disi - tum mesajlar paylasilir
KARA_LISTE = []

GORULMUS_FILE    = "gorulmus.json"
ISTATISTIK_FILE  = "istatistik.json"
LOGO_DOSYA       = "logo.png"

MESAJ_BEKLEME    = 3       # saniye - rate limiting
GORULMUS_MAX     = 3000    # max kac mesaj id saklansin
GORULMUS_TTL     = 7 * 24 * 3600  # 7 gun (saniye)
WATCHDOG_ARALIK  = 3600    # her saat admin'e rapor

# === GLOBAL STATE ===
gorulmus_cache   = None    # {mid: timestamp}
istatistik_cache = None    # {"toplam": N, "kanallar": {...}}
ist_degisim_sayac = 0
son_mesaj_zamani = 0.0

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ─── LOGLAMA ────────────────────────────────────────────────────────────────
def log(seviye, mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[" + zaman + "] [" + seviye + "] " + mesaj)

# ─── GORULMUS (zaman damgali, TTL ile temizleme) ─────────────────────────────
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
    simdi = datetime.now(timezone.utc).timestamp()
    eski_sayisi = len(gorulmus_cache)
    gorulmus_cache = {k: v for k, v in gorulmus_cache.items()
                      if simdi - v < GORULMUS_TTL}
    # Yine de cok fazlaysa en yenileri tut
    if len(gorulmus_cache) > GORULMUS_MAX:
        sirali = sorted(gorulmus_cache.items(), key=lambda x: x[1], reverse=True)
        gorulmus_cache = dict(sirali[:GORULMUS_MAX])
    temizlenen = eski_sayisi - len(gorulmus_cache)
    if temizlenen:
        log("BILGI", str(temizlenen) + " eski gorulmus kaydi temizlendi")
    gorulmus_kaydet()

def gorulmus_var_mi(mid):
    return mid in gorulmus_yukle()

def gorulmus_ekle(mid):
    global gorulmus_cache
    gorulmus_yukle()
    gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()
    gorulmus_kaydet()

# ─── ISTATISTIK (memory, 10 mesajda bir diske yaz) ───────────────────────────
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

def istatistik_guncelle(kanal_adi, indirim):
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

# ─── YARDIMCI ────────────────────────────────────────────────────────────────
def emoji_temizle(metin):
    if not metin:
        return ""
    temiz = ""
    for karakter in metin:
        kategori = unicodedata.category(karakter)
        if kategori not in ("So", "Sm", "Sk"):
            temiz += karakter
    return temiz.strip()

def mesaj_id_olustur(metin):
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

def kara_liste_kontrol(metin):
    metin_kucuk = (metin or "").lower()
    for kelime in KARA_LISTE:
        if kelime.lower() in metin_kucuk:
            return True
    return False

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    indirim_kaliplari = [
        r"-\s*%\s*(\d+)",
        r"indirim\s*:\s*-?\s*%\s*(\d+)",
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
        r"yuzde\s*(\d+)",
        r"(\d+)\s*percent",
    ]
    for kalip in indirim_kaliplari:
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
    # "1.299,90" veya "1299.90" veya "299,90" -> float
    try:
        temiz = fiyat_str.strip()
        if "," in temiz and "." in temiz:
            # "1.299,90" formati
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
            degerler_sirali = sorted(degerler, key=lambda x: x[0], reverse=True)
            eski_val, eski_str = degerler_sirali[0]
            yeni_val, yeni_str = degerler_sirali[-1]
            if eski_val > yeni_val:
                return eski_str, yeni_str
    return None, None

def magaza_bul(metin):
    metin_kucuk = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol",    "trendyol"),
        ("Hepsiburada", "hepsiburada"),
        ("Amazon TR",   "amazon"),
        ("MediaMarkt",  "mediamarkt"),
        ("Teknosa",     "teknosa"),
        ("Gratis",      "gratis"),
        ("Boyner",      "boyner"),
        ("Morhipo",     "morhipo"),
        ("Zara",        "zara.com"),
        ("N11",         "n11.com"),
        ("Çiçeksepeti", "ciceksepeti"),
        ("Temu",        "temu.com"),
    ]:
        if anahtar in metin_kucuk:
            return magaza
    return "E-Ticaret"

def urun_adi_bul(metin):
    if not metin:
        return None
    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    for satir in satirlar:
        temiz = emoji_temizle(satir)
        # Fiyat, link, hashtag, @ icermeyen, 8+ karakter olan satir
        if (len(temiz) >= 8
                and not satir.startswith("#")
                and not satir.startswith("@")
                and "http" not in satir
                and "TL" not in satir
                and "₺" not in satir
                and not re.search(r"\d+%|%\d+", satir)):
            return temiz[:80]
    return None

def link_bul(metin):
    if not metin:
        return None
    linkler = re.findall(r'https?://[^\s\)\"\<\]]+', metin)
    if not linkler:
        return None
    # Urun linklerini onceliklendiren siralama
    oncelikli = ["trendyol.com", "hepsiburada.com", "amazon.com.tr",
                 "mediamarkt.com.tr", "teknosa.com", "ty.gl", "hb.gl"]
    for link in linkler:
        for oncelik in oncelikli:
            if oncelik in link:
                return link
    # Yoksa t.me disindaki ilk linki don
    for link in linkler:
        if "t.me" not in link:
            return link
    return linkler[0]

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun_img.size
        logo = Image.open(LOGO_DOSYA).convert("RGBA")
        boyut = int(min(w, h) * 0.20)
        logo = logo.resize((boyut, boyut), Image.LANCZOS)
        bosluk = 10
        urun_img.paste(logo, (w - boyut - bosluk, h - boyut - bosluk), logo)
        cikti = BytesIO()
        urun_img.convert("RGB").save(cikti, format="JPEG", quality=92)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", "Logo ekleme hatasi: " + str(e))
        return gorsel_bytes

def sablon_olustur(metin, indirim):
    if indirim <= 0:
        return None
    magaza  = magaza_bul(metin)
    urun    = urun_adi_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link    = link_bul(metin)
    emoji_map = {
        "Trendyol":    "🛍️",
        "Hepsiburada": "🏪",
        "Amazon TR":   "📦",
        "MediaMarkt":  "🔴",
        "Teknosa":     "💻",
        "Gratis":      "💄",
        "Boyner":      "👗",
        "Morhipo":     "👒",
        "Zara":        "🧥",
        "N11":         "🛒",
        "Çiçeksepeti": "🌸",
        "Temu":        "🌍",
        "E-Ticaret":   "🛒",
    }
    emoji = emoji_map.get(magaza, "🛒")
    s = []
    s.append("🔥 <b>%" + str(indirim) + " İNDİRİM!</b>")
    s.append("")
    if urun:
        s.append("🏷️ " + urun)
        s.append("")
    s.append(emoji + " <b>" + magaza + "</b>")
    s.append("")
    if eski and yeni:
        s.append("💰 <s>" + eski + " TL</s>  →  <b>" + yeni + " TL</b>")
        s.append("")
    if link:
        s.append("🔗 <a href='" + link + "'>Fırsata Git</a>")
        s.append("")
    s.append("⚡ Stok sınırlı olabilir!")
    kanal = HEDEF_KANAL.lstrip("@")
    s.append("📢 @" + kanal)
    return "\n".join(s)

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
        "📡 Dinlenen kanal: " + str(len(KAYNAK_KANALLAR)) + "\n"
        "🎯 Min indirim: %" + str(MIN_INDIRIM)
    )
    await admin_bildir(rapor)

async def watchdog():
    while True:
        await asyncio.sleep(WATCHDOG_ARALIK)
        ist = istatistik_yukle()
        bugun = datetime.now().strftime("%Y-%m-%d")
        bugunun_sayisi = ist.get("gunluk", {}).get(bugun, 0)
        mesaj = (
            "💓 Bot çalışıyor\n"
            "📊 Bugün iletilen: " + str(bugunun_sayisi) + "\n"
            "📊 Toplam: " + str(ist.get("toplam", 0))
        )
        await admin_bildir(mesaj)
        gorulmus_temizle()
        istatistik_kaydet()

# ─── ANA HANDLER ─────────────────────────────────────────────────────────────
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    global son_mesaj_zamani
    try:
        metin = event.message.text or ""

        # Kara liste kontrolu
        if kara_liste_kontrol(metin):
            log("BILGI", "Kara liste - atlandi")
            return

        indirim = indirim_oranini_bul(metin)
        if indirim < MIN_INDIRIM:
            return

        # Duplikasyon
        mid = mesaj_id_olustur(metin)
        if gorulmus_var_mi(mid):
            log("BILGI", "Duplikat atlandi")
            return
        gorulmus_ekle(mid)

        sablon = sablon_olustur(metin, indirim)
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

        # Sadece fotografi isle
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            gorsel_bytes = await client.download_media(event.message.media, bytes)
            if gorsel_bytes:
                logolu = logo_ekle(gorsel_bytes)
                buf = BytesIO(logolu)
                buf.name = "urun.jpg"
                await client.send_message(HEDEF_KANAL, sablon, file=buf, parse_mode="html")
            else:
                await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
        else:
            await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")

        istatistik_guncelle(kanal_adi, indirim)
        log("OK", "%" + str(indirim) + " [" + kanal_adi + "] " + metin[:50].replace("\n", " "))

    except FloodWaitError as e:
        log("UYARI", "FloodWait " + str(e.seconds) + "s")
        await asyncio.sleep(e.seconds + 5)
    except ChannelPrivateError:
        log("HATA", "Kanal ozel/kapali")
    except ChatWriteForbiddenError:
        log("HATA", "Yazma izni yok")
        await admin_bildir("Hedef kanala yazma izni yok! Botu admin yapın.")
    except Exception as e:
        log("HATA", str(e))

# ─── MAIN ────────────────────────────────────────────────────────────────────
async def main():
    log("BILGI", "FirsatPulsu v3 baslatiliyor...")
    log("BILGI", "Min indirim : %" + str(MIN_INDIRIM))
    log("BILGI", "Kaynak kanal: " + str(len(KAYNAK_KANALLAR)))

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    while True:
        try:
            await client.start()
            log("OK", "Baglandi! Kanallar dinleniyor...")
            await baslangic_raporu()
            asyncio.ensure_future(watchdog())
            await client.run_until_disconnected()
        except Exception as e:
            log("HATA", "Baglanti koptu: " + str(e))
            log("BILGI", "30s sonra yeniden baglaniliyor...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
