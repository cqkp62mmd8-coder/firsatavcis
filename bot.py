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
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError, UsernameInvalidError
from telethon.tl.types import MessageMediaPhoto

# ═══════════════════════════════════════════════════════════════
# AYARLAR
# ═══════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL   = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))

# ═══════════════════════════════════════════════════════════════
# KAYNAK KANALLAR (30 kanal - kategorize edilmis)
# ═══════════════════════════════════════════════════════════════
KAYNAK_KANALLAR = [
    # === KESIN AKTIF KANALLAR ===
    "@amazonsicakfirsatlar",        # Amazon TR sicak firsatlar
    "@donanimhabersicakfirsatlar",  # DH Sicak Firsatlar - teknoloji
    "@yurticifirsat",               # Yurtici Firsatlari
    "@firsatmerkez",                # Firsat Merkezi
    "@indirimhabercisi",            # Indirim kuponu + link
    "@firsatpaylasim",              # En populer kanallardan
    "@uygunlasohbet",               # Uygunla
    "@firsatavcilari01",            # Firsat Avcilari
    "@firsatvakti",                 # Firsat Vakti
    "@firsatyurdu",                 # Firsat Yurdu
    "@yurtdisifirsat",              # Yurtdisi firsatlar
]

# ═══════════════════════════════════════════════════════════════
# SABITLER
# ═══════════════════════════════════════════════════════════════
GORULMUS_FILE    = "gorulmus.json"
ISTATISTIK_FILE  = "istatistik.json"
LOGO_DOSYA       = "logo.png"
MESAJ_BEKLEME    = 3          # saniye - rate limiting
GORULMUS_TTL     = 7 * 86400  # 7 gun
GORULMUS_MAX     = 5000       # max kayit
WATCHDOG_ARALIK  = 3600       # saatlik rapor

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
gorulmus_cache    = None   # {mid: timestamp}
istatistik_cache  = None
ist_sayac         = 0
son_mesaj_zamani  = 0.0

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ═══════════════════════════════════════════════════════════════
# LOGLAMA
# ═══════════════════════════════════════════════════════════════
def log(seviye, mesaj):
    print("[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] [" + seviye + "] " + mesaj)

# ═══════════════════════════════════════════════════════════════
# GORULMUS - ZAMAN DAMGALI CACHE
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
    try:
        with open(GORULMUS_FILE, "w") as f:
            json.dump(gorulmus_cache, f)
    except Exception as e:
        log("HATA", "gorulmus kaydet: " + str(e))

def gorulmus_temizle():
    global gorulmus_cache
    gorulmus_yukle()  # None ise diskten yukle
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
    gorulmus_yukle()
    gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()
    gorulmus_kaydet()

# ═══════════════════════════════════════════════════════════════
# ISTATISTIK - MEMORY CACHE
# ═══════════════════════════════════════════════════════════════
def istatistik_yukle():
    global istatistik_cache
    if istatistik_cache is not None:
        return istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "r") as f:
            istatistik_cache = json.load(f)
    except:
        istatistik_cache = {"toplam": 0, "kanallar": {}, "gunluk": {}, "magaza": {}}
    return istatistik_cache

def istatistik_kaydet():
    try:
        with open(ISTATISTIK_FILE, "w") as f:
            json.dump(istatistik_cache, f)
    except:
        pass

def istatistik_guncelle(kanal_adi, magaza):
    global ist_sayac
    ist = istatistik_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
    ist["magaza"][magaza] = ist["magaza"].get(magaza, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    ist_sayac += 1
    if ist_sayac >= 10:
        istatistik_kaydet()
        ist_sayac = 0

# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSIYONLAR
# ═══════════════════════════════════════════════════════════════
def emoji_temizle(metin):
    if not metin:
        return ""
    return "".join(k for k in metin if unicodedata.category(k) not in ("So", "Sm", "Sk")).strip()

def mesaj_id_olustur(metin):
    # Normalize et: bosluk, kucuk harf, ozel karakter
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    # URL'leri kaldir (ayni urun farkli zamanda paylasilabilir)
    temiz = re.sub(r'https?://\S+', '', temiz).strip()
    return hashlib.sha256(temiz.encode()).hexdigest()[:32]

def indirim_oranini_bul(metin):
    if not metin:
        return 0

    indirim_kaliplari = [
        r"-\s*%\s*(\d+)",                                    # -%50 (Amazon formati)
        r"indirim\s*:\s*-?\s*%\s*(\d+)",                    # Indirim: -%50
        r"indirimde\s*:\s*(\d+)",                            # Indirimde: 50
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz|tasarruf)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz|tasarruf)",
        r"(?:indirim|off|discount|tasarruf)[^\d]*(\d+)\s*%",
        r"yuzde\s*(\d+)",
        r"(\d+)\s*percent\s*off",
    ]
    for kalip in indirim_kaliplari:
        eslesme = re.findall(kalip, metin.lower())
        if eslesme:
            degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
            if degerler:
                return max(degerler)

    # Son care: indirim kelimesi varsa genel % ara
    if any(k in metin.lower() for k in ["indirim", "kampanya", "firsat", "sale", "off", "ucuz"]):
        eslesme = re.findall(r"%(\d+)", metin) + re.findall(r"(\d+)%", metin)
        degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
        if degerler:
            return max(degerler)
    return 0

def fiyat_parse(s):
    try:
        temiz = s.strip()
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
        degerler = [(fiyat_parse(f), f) for f in eslesme if fiyat_parse(f) > 0]
        if len(degerler) >= 2:
            sirali = sorted(degerler, key=lambda x: x[0], reverse=True)
            return sirali[0][1], sirali[-1][1]  # en buyuk = eski, en kucuk = yeni
    return None, None

def magaza_bul(metin):
    metin_k = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol",     "trendyol"),
        ("Hepsiburada",  "hepsiburada"),
        ("Amazon TR",    "amazon"),
        ("MediaMarkt",   "mediamarkt"),
        ("Teknosa",      "teknosa"),
        ("Gratis",       "gratis"),
        ("Boyner",       "boyner"),
        ("Morhipo",      "morhipo"),
        ("Zara",         "zara.com"),
        ("N11",          "n11.com"),
        ("Çiçeksepeti",  "ciceksepeti"),
        ("Temu",         "temu.com"),
        ("AliExpress",   "aliexpress"),
        ("PTTAVM",       "pttavm"),
        ("Vatanbilgisayar", "vatanbilgisayar"),
        ("Watsons",      "watsons"),
        ("Karaca",       "karaca"),
        ("BIM",          "bim"),
        ("A101",         "a101"),
        ("ŞOK",          "sok.com.tr"),
    ]:
        if anahtar in metin_k:
            return magaza
    return "E-Ticaret"

def urun_adi_bul(metin):
    if not metin:
        return None
    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    for satir in satirlar:
        temiz = emoji_temizle(satir)
        if (len(temiz) >= 8
                and "http" not in satir
                and not satir.startswith("#")
                and not satir.startswith("@")
                and "TL" not in satir
                and "₺" not in satir
                and not re.search(r"\d+[%₺]|[%₺]\d+", satir)
                and not re.search(r"indirim|kampanya|firsat|fiyat", temiz.lower())):
            return temiz[:80]
    return None

def link_bul(metin):
    if not metin:
        return None
    linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
    if not linkler:
        return None
    # Urun linklerini onceliklendiren siralama
    oncelik = [
        "trendyol.com", "hepsiburada.com", "amazon.com.tr",
        "mediamarkt.com.tr", "teknosa.com", "ty.gl", "hb.gl",
        "vatanbilgisayar.com", "n11.com", "ciceksepeti.com",
        "aliexpress.com", "pttavm.com", "gratis.com"
    ]
    for link in linkler:
        for p in oncelik:
            if p in link:
                return link
    # t.me disindaki ilk link
    for link in linkler:
        if "t.me" not in link and "telegram" not in link:
            return link
    return linkler[0]

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun_img.size
        # Minimum gorsel boyutu kontrolu
        if w < 100 or h < 100:
            return gorsel_bytes
        logo = Image.open(LOGO_DOSYA).convert("RGBA")
        boyut = max(50, int(min(w, h) * 0.20))
        logo = logo.resize((boyut, boyut), Image.LANCZOS)
        urun_img.paste(logo, (w - boyut - 10, h - boyut - 10), logo)
        cikti = BytesIO()
        urun_img.convert("RGB").save(cikti, format="JPEG", quality=92)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", "Logo: " + str(e))
        return gorsel_bytes

def sablon_olustur(metin, indirim):
    if indirim <= 0:
        return None
    magaza  = magaza_bul(metin)
    urun    = urun_adi_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link    = link_bul(metin)

    emoji_map = {
        "Trendyol":     "🛍️", "Hepsiburada": "🏪",
        "Amazon TR":    "📦", "MediaMarkt":  "🔴",
        "Teknosa":      "💻", "Gratis":      "💄",
        "Boyner":       "👗", "Morhipo":     "👒",
        "Zara":         "🧥", "N11":         "🛒",
        "Çiçeksepeti":  "🌸", "Temu":        "🌍",
        "AliExpress":   "🛒", "PTTAVM":      "📮",
        "Vatanbilgisayar": "🖥️", "Watsons":  "💊",
        "Karaca":       "🍳", "BIM":         "🏬",
        "A101":         "🏬", "ŞOK":         "🏬",
        "E-Ticaret":    "🛒",
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
    s.append("📢 @" + HEDEF_KANAL.lstrip("@"))
    return "\n".join(s)

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
        "📡 Dinlenen kanal: " + str(len(KAYNAK_KANALLAR)) + "\n"
        "🎯 Min indirim: %" + str(MIN_INDIRIM) + "\n"
        "🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    await admin_bildir(rapor)

async def watchdog():
    while True:
        await asyncio.sleep(WATCHDOG_ARALIK)
        ist = istatistik_yukle()
        bugun = datetime.now().strftime("%Y-%m-%d")
        gunluk = ist.get("gunluk", {}).get(bugun, 0)
        # En aktif kanallar
        kanallar = sorted(ist.get("kanallar", {}).items(), key=lambda x: x[1], reverse=True)[:3]
        kanal_str = ", ".join(k + "(" + str(v) + ")" for k, v in kanallar)
        rapor = (
            "💓 Bot Aktif\n"
            "📊 Bugün: " + str(gunluk) + " | Toplam: " + str(ist.get("toplam", 0)) + "\n"
            "🏆 Top kanallar: " + kanal_str
        )
        await admin_bildir(rapor)
        # Temizlik
        gorulmus_temizle()
        istatistik_kaydet()

# ═══════════════════════════════════════════════════════════════
# ANA MESAJ HANDLER
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    global son_mesaj_zamani
    try:
        metin = event.message.text or ""

        # Indirim filtresi
        indirim = indirim_oranini_bul(metin)
        if indirim < MIN_INDIRIM:
            return

        # Duplikasyon - SHA256 ile guclu hash
        mid = mesaj_id_olustur(metin)
        if gorulmus_var_mi(mid):
            log("BILGI", "Duplikat atlandi [%" + str(indirim) + "]")
            return
        gorulmus_ekle(mid)

        # Sablon olustur
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

        # Kanal adi
        kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"
        magaza = magaza_bul(metin)

        # Gorsel isle - sadece foto
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            try:
                gorsel_bytes = await client.download_media(event.message.media, bytes)
                if gorsel_bytes and len(gorsel_bytes) > 1000:
                    logolu = logo_ekle(gorsel_bytes)
                    buf = BytesIO(logolu)
                    buf.name = "urun.jpg"
                    await client.send_message(HEDEF_KANAL, sablon, file=buf, parse_mode="html")
                else:
                    await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
            except Exception as img_e:
                log("UYARI", "Gorsel isleme hatasi: " + str(img_e))
                await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
        else:
            await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")

        istatistik_guncelle(kanal_adi, magaza)
        log("OK", "%" + str(indirim) + " [" + kanal_adi + "] [" + magaza + "] " + metin[:40].replace("\n", " "))

    except FloodWaitError as e:
        log("UYARI", "FloodWait " + str(e.seconds) + "s bekleniyor")
        await asyncio.sleep(e.seconds + 5)
    except ChannelPrivateError:
        log("HATA", "Kanal ozel/kapali - listeden kaldirin")
    except UsernameInvalidError as e:
        log("HATA", "Gecersiz kullanici adi - kanal bulunamadi: " + str(e))
    except ChatWriteForbiddenError:
        log("KRITIK", "Hedef kanala yazma izni yok!")
        await admin_bildir("🚨 Hedef kanala yazma izni yok! Botu admin yapın.")
    except Exception as e:
        log("HATA", str(e))


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════
async def test_gonder():
    test_mesajlari = [
        {
            "metin": "Philips Erkek Tiras Makinesi\n\nIndirimli Fiyat: 299,90 TL\nNormal Fiyat: 899,00 TL\nIndirim: -%66\nStokta var\n\nAmazon TR\nhttps://amazon.com.tr/test",
            "aciklama": "Amazon -%66 formati"
        },
        {
            "metin": "Samsung 65 inc 4K TV\n\nTrendyol urunlerinde %75 indirim var\n\n1.499 TL yerine 374 TL\n\nhttps://trendyol.com/test",
            "aciklama": "Trendyol %75 formati"
        },
        {
            "metin": "Dyson V15 Supurge\n\nHepsiburada 60% indirim kampanyasi\n\n12.000 TL - 4.800 TL\n\nhttps://hepsiburada.com/test",
            "aciklama": "Hepsiburada 60% formati"
        },
    ]
    log("TEST", "=== TEST BASLIYOR ===")
    for i, t in enumerate(test_mesajlari, 1):
        metin = t["metin"]
        indirim = indirim_oranini_bul(metin)
        sablon = sablon_olustur(metin, indirim)
        log("TEST", str(i) + ". " + t["aciklama"] + " -> %" + str(indirim))
        if sablon and indirim >= MIN_INDIRIM:
            await client.send_message(
                HEDEF_KANAL,
                "🧪 <b>TEST " + str(i) + "/" + str(len(test_mesajlari)) + "</b>\n\n" + sablon,
                parse_mode="html"
            )
            log("TEST", "   Gonderildi!")
        else:
            log("TEST", "   Atlanamadi!")
        await asyncio.sleep(2)
    log("TEST", "=== TEST TAMAMLANDI ===")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
async def main():
    log("BILGI", "═══ FirsatPulsu v4 ═══")
    log("BILGI", "Min indirim : %" + str(MIN_INDIRIM))
    log("BILGI", "Kaynak kanal: " + str(len(KAYNAK_KANALLAR)))
    log("BILGI", "Gorulmus TTL: 7 gun")

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    while True:
        try:
            await client.start()
            log("OK", "Baglandi! Kanallar dinleniyor...")
            await baslangic_raporu()

            # TEST_MODE=1 ise kanalina test mesajlari gonder
            if os.environ.get("TEST_MODE", "0") == "1":
                await test_gonder()

            asyncio.ensure_future(watchdog())
            await client.run_until_disconnected()
        except Exception as e:
            log("HATA", "Baglanti koptu: " + str(e))
            log("BILGI", "30s sonra yeniden baglaniliyor...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
