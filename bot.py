import os
import asyncio
import re
from telethon import TelegramClient, events

# --- AYARLAR (Railway'de Variable olarak ekleyin) ---
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
HEDEF_KANAL = os.environ.get("CHANNEL_ID", "")
MIN_INDIRIM = int(os.environ.get("MIN_INDIRIM", "50"))

# Takip edilecek kaynak kanallar
KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar",
    "@donanimhabersicakfirsatlar",
    "@firsatmerkez",
    "@yurticifirsat",
    "@indirimhabercisi",
    "@firsatavcilari01",
    "@uygunlasohbet",
    "@indirimdeal",
    "@firsatmerkezi",
]

# Telethon client (kullanici hesabi ile dinleme)
client = TelegramClient("indirim_session", API_ID, API_HASH)

def indirim_oranini_bul(metin):
    if not metin:
        return 0
    # %85, %85 gibi kaliplari bul
    eslesme = re.findall(r"%\s*(\d+)", metin)
    if eslesme:
        return max(int(x) for x in eslesme)
    # "85%" formatini da dene
    eslesme2 = re.findall(r"(\d+)\s*%", metin)
    if eslesme2:
        return max(int(x) for x in eslesme2)
    return 0

def anahtar_kelime_var_mi(metin):
    if not metin:
        return False
    metin_kucuk = metin.lower()
    anahtar = ["indirim", "firsat", "tl", "kampanya", "ucuz", "sale", "%"]
    return any(k in metin_kucuk for k in anahtar)

@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    try:
        metin = event.message.text or ""
        indirim = indirim_oranini_bul(metin)

        # Indirim orani yeterliyse veya anahtar kelime varsa ilet
        if indirim >= MIN_INDIRIM or (indirim == 0 and anahtar_kelime_var_mi(metin)):
            # Kaynagi belirt
            kaynak = ""
            if event.chat and hasattr(event.chat, "username") and event.chat.username:
                kaynak = "\n\nKaynak: @" + event.chat.username

            if event.message.media:
                # Medya varsa medyayi da ilet
                await client.send_message(
                    HEDEF_KANAL,
                    metin + kaynak,
                    file=event.message.media,
                    parse_mode="html"
                )
            else:
                await client.send_message(
                    HEDEF_KANAL,
                    metin + kaynak,
                    parse_mode="html"
                )

            print("Iletildi: " + metin[:60])

    except Exception as e:
        print("Hata: " + str(e))

async def main():
    print("Forward Botu Baslatiliyor...")
    print("Min indirim: %" + str(MIN_INDIRIM))
    print("Kaynak kanallar: " + str(KAYNAK_KANALLAR))

    await client.start(bot_token=BOT_TOKEN)
    print("Bot aktif! Mesajlar bekleniyor...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
