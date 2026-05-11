import os
import asyncio
import re
import json
import hashlib
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
    # Metni normalize edip hash al - duplikasyonu onle
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
    # "1.299 TL", "299,90 TL" gibi formatlari bul
    eslesme = re.findall(r"([\d.,]+)\s*(?:TL|tl|₺)", metin or "")
    if len(eslesme) >= 2:
        return eslesme[-2], eslesme[-1]  # eski fiyat, yeni fiyat
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
    elif "teknosa" in metin_kucuk:
        return "Teknosa"
    return "E-Ticaret"

def link_bul(metin):
    eslesme = re.findall(r'https?://[^\s\)\"]+', metin or "")
    return eslesme[0] if eslesme else None

def sablon_olustur(metin, indirim, kaynak_kanal):
    magaza = magaza_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link = link_bul(metin)

    # Magaza emoji
    emoji_map = {
        "Trendyol": "🛍️",
        "Hepsiburada": "🏪",
        "Amazon TR": "📦",
        "MediaMarkt": "🔴",
        "Teknosa": "💻",
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
    satirlar.append("📢 @" + (HEDEF_KANAL.replace("@", "") if HEDEF_KANAL.startswith("@") else HEDEF_KANAL))

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
            print("Duplikat atlandi: " + metin[:40])
            return

        gorulmus.add(mid)
        gorulmus_kaydet(gorulmus)

        # Kaynak kanal adi
        kaynak = ""
        if event.chat and hasattr(event.chat, "username") and event.chat.username:
            kaynak = event.chat.username

        # Sablon olustur
        sablon = sablon_olustur(metin, indirim, kaynak)

        if event.message.media:
            await client.send_message(
                HEDEF_KANAL,
                sablon,
                file=event.message.media,
                parse_mode="html"
            )
        else:
            await client.send_message(
                HEDEF_KANAL,
                sablon,
                parse_mode="html"
            )

        print("Iletildi (%" + str(indirim) + "): " + metin[:50])

    except Exception as e:
        print("Hata: " + str(e))

async def main():
    print("Forward Botu Baslatiliyor...")
    print("Min indirim: %" + str(MIN_INDIRIM))
    await client.start(bot_token=BOT_TOKEN)
    print("Bot aktif!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
