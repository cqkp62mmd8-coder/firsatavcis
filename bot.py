import os
import asyncio
import re
import json
import hashlib
from io import BytesIO
from datetime import datetime
from PIL import Image
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# === AYARLAR ===
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL = os.environ.get("CHANNEL_ID", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")  # Hata bildirim icin kendi Telegram ID'niz
MIN_INDIRIM = int(os.environ.get("MIN_INDIRIM", "50"))

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar",
    "@donanimhabersicakfirsatlar",
    "@firsatmerkez",
    "@yurticifirsat",
    "@indirimhabercisi",
    "@uygunlasohbet",
    "@indirimdeal",
    "@firsatmerkezi",
    "@firsatavcilari01",
]

GORULMUS_FILE = "gorulmus.json"
LOGO_DOSYA = "logo.png"
ISTATISTIK_FILE = "istatistik.json"

# === MEMORY CACHE (disk okuma minimize) ===
gorulmus_cache = None
son_mesaj_zamani = 0
MESAJ_BEKLEME = 3  # saniye - rate limiting

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# === LOGLAMA ===
def log(seviye, mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[" + zaman + "] [" + seviye + "] " + mesaj)

# === GORULMUS CACHE ===
def gorulmus_yukle():
    global gorulmus_cache
    if gorulmus_cache is not None:
        return gorulmus_cache
    try:
        with open(GORULMUS_FILE, "r") as f:
            gorulmus_cache = set(json.load(f))
    except:
        gorulmus_cache = set()
    return gorulmus_cache

def gorulmus_kaydet():
    global gorulmus_cache
    if gorulmus_cache is None:
        return
    try:
        with open(GORULMUS_FILE, "w") as f:
            json.dump(list(gorulmus_cache)[-2000:], f)
    except Exception as e:
        log("HATA", "gorulmus kaydetme hatasi: " + str(e))

def gorulmus_ekle(mid):
    global gorulmus_cache
    gorulmus_yukle()
    gorulmus_cache.add(mid)
    gorulmus_kaydet()

def gorulmus_var_mi(mid):
    return mid in gorulmus_yukle()

# === ISTATISTIK ===
def istatistik_guncelle(kanal_adi):
    try:
        try:
            with open(ISTATISTIK_FILE, "r") as f:
                ist = json.load(f)
        except:
            ist = {"toplam": 0, "kanallar": {}}
        ist["toplam"] = ist.get("toplam", 0) + 1
        ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
        with open(ISTATISTIK_FILE, "w") as f:
            json.dump(ist, f)
    except:
        pass

# === YARDIMCI FONKSIYONLAR ===
def mesaj_id_olustur(metin):
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    indirim_kaliplari = [
        # "-%50", "- %50" formati (Amazon tarz)
        r"-\s*%\s*(\d+)",
        r"indirim\s*:\s*-?\s*%\s*(\d+)",
        # "%50 indirim" formati
        r"%\s*(\d+)\s*(?:indirim|off|discount)",
        r"(\d+)\s*%\s*(?:indirim|off|discount)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
        # "%50 ucuz" veya "yuzde 50"
        r"yuzde\s*(\d+)",
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

def fiyat_bul(metin):
    eslesme = re.findall(r"([\d.,]+)\s*(?:TL|tl|₺|lira)", metin or "")
    if len(eslesme) >= 2:
        try:
            eski = float(eslesme[-2].replace(".", "").replace(",", "."))
            yeni = float(eslesme[-1].replace(".", "").replace(",", "."))
            if eski > yeni:  # mantikli sirada mi kontrol
                return eslesme[-2], eslesme[-1]
            elif yeni > eski:
                return eslesme[-1], eslesme[-2]
        except:
            pass
    return None, None

def magaza_bul(metin):
    metin_kucuk = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol", "trendyol"),
        ("Hepsiburada", "hepsiburada"),
        ("Amazon TR", "amazon"),
        ("MediaMarkt", "mediamarkt"),
        ("Teknosa", "teknosa"),
        ("Gratis", "gratis"),
        ("Boyner", "boyner"),
        ("N11", "n11.com"),
    ]:
        if anahtar in metin_kucuk:
            return magaza
    return "E-Ticaret"

def urun_adi_bul(metin):
    # Ilk anlamli satiri urun adi olarak al
    if not metin:
        return None
    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    for satir in satirlar:
        # Emoji, # veya @ ile baslamayan, 10+ karakter olan ilk satir
        temiz = re.sub(r'[^\w\s]', '', satir).strip()
        if len(temiz) > 10 and not satir.startswith("#") and not satir.startswith("@"):
            return satir[:80]
    return None

def link_bul(metin):
    eslesme = re.findall(r'https?://[^\s\)\"\<]+', metin or "")
    # En uzun ve anlamli linki sec
    if eslesme:
        return sorted(eslesme, key=len, reverse=True)[0]
    return None

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        urun_genislik, urun_yukseklik = urun_img.size
        logo = Image.open(LOGO_DOSYA).convert("RGBA")
        logo_boyut = int(min(urun_genislik, urun_yukseklik) * 0.20)
        logo = logo.resize((logo_boyut, logo_boyut), Image.LANCZOS)
        bosluk = 10
        x = urun_genislik - logo_boyut - bosluk
        y = urun_yukseklik - logo_boyut - bosluk
        urun_img.paste(logo, (x, y), logo)
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
    magaza = magaza_bul(metin)
    urun_adi = urun_adi_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link = link_bul(metin)
    emoji_map = {
        "Trendyol": "🛍️",
        "Hepsiburada": "🏪",
        "Amazon TR": "📦",
        "MediaMarkt": "🔴",
        "Teknosa": "💻",
        "Gratis": "💄",
        "Boyner": "👗",
        "N11": "🛒",
        "E-Ticaret": "🛒"
    }
    emoji = emoji_map.get(magaza, "🛒")
    satirlar = []
    satirlar.append("🔥 <b>%" + str(indirim) + " İNDİRİM!</b>")
    satirlar.append("")
    if urun_adi:
        satirlar.append("📦 " + urun_adi)
        satirlar.append("")
    satirlar.append(emoji + " <b>" + magaza + "</b>")
    satirlar.append("")
    if eski and yeni:
        satirlar.append("💰 <s>" + eski + " TL</s>  →  <b>" + yeni + " TL</b>")
        satirlar.append("")
    if link:
        satirlar.append("🔗 <a href='" + link + "'>Fırsata Git</a>")
        satirlar.append("")
    satirlar.append("⚡ Stok sınırlı olabilir!")
    kanal = HEDEF_KANAL.replace("@", "") if HEDEF_KANAL.startswith("@") else HEDEF_KANAL
    satirlar.append("📢 @" + kanal)
    return "\n".join(satirlar)

async def admin_bildir(mesaj):
    if ADMIN_ID:
        try:
            await client.send_message(int(ADMIN_ID), "⚠️ FırsatPulsu Bot:\n" + mesaj)
        except:
            pass

# === ANA MESAJ HANDLER ===
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    global son_mesaj_zamani
    try:
        metin = event.message.text or ""
        indirim = indirim_oranini_bul(metin)

        if indirim < MIN_INDIRIM:
            return

        # Duplikasyon kontrolu (RAM'den)
        mid = mesaj_id_olustur(metin)
        if gorulmus_var_mi(mid):
            log("BILGI", "Duplikat atlandi")
            return

        gorulmus_ekle(mid)

        sablon = sablon_olustur(metin, indirim)
        if not sablon:
            return

        # Rate limiting
        simdi = asyncio.get_event_loop().time()
        gecen = simdi - son_mesaj_zamani
        if gecen < MESAJ_BEKLEME:
            await asyncio.sleep(MESAJ_BEKLEME - gecen)
        son_mesaj_zamani = asyncio.get_event_loop().time()

        # Kanal adi
        kanal_adi = "bilinmiyor"
        if event.chat and hasattr(event.chat, "username") and event.chat.username:
            kanal_adi = event.chat.username

        # Sadece foto medyasini isle
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            gorsel_bytes = await client.download_media(event.message.media, bytes)
            if gorsel_bytes:
                logolu = logo_ekle(gorsel_bytes)
                gorsel_io = BytesIO(logolu)
                gorsel_io.name = "urun.jpg"
                await client.send_message(HEDEF_KANAL, sablon, file=gorsel_io, parse_mode="html")
            else:
                await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
        else:
            await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")

        istatistik_guncelle(kanal_adi)
        log("OK", "Iletildi (%" + str(indirim) + ") [" + kanal_adi + "]: " + metin[:50])

    except FloodWaitError as e:
        log("UYARI", "FloodWait: " + str(e.seconds) + " saniye bekleniyor")
        await asyncio.sleep(e.seconds + 5)
    except ChannelPrivateError:
        log("HATA", "Kanal ozel/kapali - erisim yok")
    except ChatWriteForbiddenError:
        log("HATA", "Hedef kanala yazma izni yok")
        await admin_bildir("Hedef kanala yazma izni yok! Botu admin yapın.")
    except Exception as e:
        log("HATA", str(e))

# === ANA DONGU ===
async def main():
    log("BILGI", "FirsatPulsu Botu Baslatiliyor...")
    log("BILGI", "Min indirim: %" + str(MIN_INDIRIM))
    log("BILGI", "Kaynak kanal sayisi: " + str(len(KAYNAK_KANALLAR)))

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    # Otomatik yeniden baglanti dongusu
    while True:
        try:
            await client.start()
            log("OK", "Bot aktif! Kanallar dinleniyor...")
            await client.run_until_disconnected()
        except Exception as e:
            log("HATA", "Baglanti koptu: " + str(e))
            log("BILGI", "30 saniye sonra yeniden baglaniliyor...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
