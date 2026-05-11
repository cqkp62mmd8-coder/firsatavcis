import os
import asyncio
import re
import json
import hashlib
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
HEDEF_KANAL = os.environ.get("CHANNEL_ID", "")
MIN_INDIRIM = int(os.environ.get("MIN_INDIRIM", "50"))

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar",
    "@donanimhabersicakfirsatlar",
    "@firsatmerkez",
    "@yurticifirsat",
    "@indirimhabercisi",
]

GORULMUS_FILE = "gorulmus.json"
LOGO_DOSYA = "logo.png"

client = TelegramClient("indirim_session", API_ID, API_HASH)

def gorulmus_yukle():
    try:
        with open(GORULMUS_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def gorulmus_kaydet(liste):
    with open(GORULMUS_FILE, "w") as f:
        json.dump(list(liste)[-1000:], f)

def mesaj_id_olustur(metin):
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    eslesme = re.findall(r"%\s*(\d+)", metin)
    if eslesme:
        return max(int(x) for x in eslesme)
    eslesme2 = re.findall(r"(\d+)\s*%", metin)
    if eslesme2:
        return max(int(x) for x in eslesme2)
    return 0

def fiyat_bul(metin):
    eslesme = re.findall(r"([\d.,]+)\s*(?:TL|tl|lira)", metin or "")
    if len(eslesme) >= 2:
        return eslesme[-2], eslesme[-1]
    return None, None

def magaza_bul(metin):
    metin_kucuk = (metin or "").lower()
    if "trendyol" in metin_kucuk:
        return "Trendyol"
    elif "hepsiburada" in metin_kucuk:
        return "Hepsiburada"
    elif "amazon" in metin_kucuk:
        return "Amazon TR"
    elif "mediamarkt" in metin_kucuk:
        return "MediaMarkt"
    return "E-Ticaret"

def link_bul(metin):
    eslesme = re.findall(r'https?://[^\s\)\"]+', metin or "")
    return eslesme[0] if eslesme else None

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes
        
        # Urun gorseli
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        urun_genislik, urun_yukseklik = urun_img.size
        
        # Logo
        logo = Image.open(LOGO_DOSYA).convert("RGBA")
        
        # Logo boyutunu gorselin %20si yap
        logo_boyut = int(min(urun_genislik, urun_yukseklik) * 0.20)
        logo = logo.resize((logo_boyut, logo_boyut), Image.LANCZOS)
        
        # Sag alt kose pozisyonu
        bosluk = 10
        x = urun_genislik - logo_boyut - bosluk
        y = urun_yukseklik - logo_boyut - bosluk
        
        # Logoyu yapistir
        urun_img.paste(logo, (x, y), logo)
        
        # Sonucu BytesIO'ya kaydet
        cikti = BytesIO()
        urun_img.convert("RGB").save(cikti, format="JPEG", quality=90)
        cikti.seek(0)
        return cikti.read()
        
    except Exception as e:
        print("Logo ekleme hatasi: " + str(e))
        return gorsel_bytes

def sablon_olustur(metin, indirim):
    magaza = magaza_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link = link_bul(metin)

    emoji_map = {
        "Trendyol": "🛍️",
        "Hepsiburada": "🏪",
        "Amazon TR": "📦",
        "MediaMarkt": "🔴",
        "E-Ticaret": "🛒"
    }
    emoji = emoji_map.get(magaza, "🛒")

    satirlar = []
    satirlar.append("🔥 <b>%" + str(indirim) + " INDIRIM!</b>")
    satirlar.append("")
    satirlar.append(emoji + " <b>" + magaza + "</b>")
    satirlar.append("")

    if eski and yeni:
        satirlar.append("💰 <s>" + eski + " TL</s>  →  <b>" + yeni + " TL</b>")
        satirlar.append("")

    if link:
        satirlar.append("🔗 <a href='" + link + "'>Firsata Git</a>")
        satirlar.append("")

    satirlar.append("⚡ Stok sinirli olabilir!")
    kanal = HEDEF_KANAL.replace("@", "") if HEDEF_KANAL.startswith("@") else HEDEF_KANAL
    satirlar.append("📢 @" + kanal)

    return "\n".join(satirlar)

@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    try:
        metin = event.message.text or ""
        indirim = indirim_oranini_bul(metin)

        if indirim < MIN_INDIRIM:
            return

        # Duplikasyon kontrolu
        gorulmus = gorulmus_yukle()
        mid = mesaj_id_olustur(metin)
        if mid in gorulmus:
            print("Duplikat atlandi")
            return

        gorulmus.add(mid)
        gorulmus_kaydet(gorulmus)

        sablon = sablon_olustur(metin, indirim)

        if event.message.media:
            # Gorseli indir
            gorsel_bytes = await client.download_media(event.message.media, bytes)
            if gorsel_bytes:
                # Logolu gorsel olustur
                logolu_gorsel = logo_ekle(gorsel_bytes)
                gorsel_io = BytesIO(logolu_gorsel)
                gorsel_io.name = "urun.jpg"
                await client.send_message(
                    HEDEF_KANAL,
                    sablon,
                    file=gorsel_io,
                    parse_mode="html"
                )
            else:
                await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
        else:
            await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")

        print("Iletildi (%" + str(indirim) + "): " + metin[:50])

    except Exception as e:
        print("Hata: " + str(e))

async def main():
    print("FirsatPulsu Botu Baslatiliyor...")
    print("Min indirim: %" + str(MIN_INDIRIM))
    await client.start(bot_token=BOT_TOKEN)
    print("Bot aktif!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
