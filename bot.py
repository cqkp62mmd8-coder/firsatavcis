import os
import asyncio
import re
import json
import hashlib
import unicodedata
from io import BytesIO
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import MessageMediaPhoto

# ═══════════════════════════════════════════════════════════════
# PROFESYONEL AYARLAR & LOJİSTİK
# ═══════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = int(os.environ.get("ADMIN_ID", "0"))

# Dinamik Ayarlar (Admin komutlarıyla değişebilir)
MIN_INDIRIM    = 50
KUYRUK_BEKLEME = 180 # 3 dakika (spam önleme)
KARA_LISTE     = ["çorap", "kılıf", "sticker", "kalem", "defter", "ekran koruyucu"]

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar", "@donanimhabersicakfirsatlar", "@yurticifirsat",
    "@firsatmerkez", "@indirimhabercisi", "@firsatpaylasim",
    "@uygunlasohbet", "@firsatavcilari01", "@firsatvakti",
    "@firsatyurdu", "@yurtdisifirsat"
]

# Bellek ve Kuyruk
mesaj_kuyrugu = asyncio.Queue()
gorulmus_cache = {} # Tekrar engelleme için

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ═══════════════════════════════════════════════════════════════
# ANALİZ MOTORU & YARDIMCILAR
# ═══════════════════════════════════════════════════════════════

def log(seviye, mesaj):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{seviye}] {mesaj}")

def indirim_oranini_bul(metin):
    bulunan = re.findall(r'%(\d+)', metin)
    if bulunan:
        return max([int(i) for i in bulunan])
    return 0

def fiyat_bul(metin):
    # Basit bir fiyat yakalayıcı (₺ veya TL içeren sayıları bulur)
    fiyatlar = re.findall(r'(?:₺|TL)\s?(\d+(?:[\.,]\d+)?)', metin)
    if len(fiyatlar) >= 2:
        return fiyatlar[0], fiyatlar[1] # Eski, Yeni
    elif len(fiyatlar) == 1:
        return None, fiyatlar[0]
    return None, None

def urun_adi_bul(metin):
    satirlar = [s.strip() for s in metin.split('\n') if s.strip()]
    if satirlar:
        # Genelde ilk satır ürün adıdır, temizleyelim
        ad = satirlar[0].replace('📦', '').replace('🔥', '').strip()
        return ad[:60] # Çok uzunsa kes
    return "Fırsat Ürünü"

def benzerlik_anahtari(metin):
    urun = urun_adi_bul(metin)
    _, yeni = fiyat_bul(metin)
    # Ürün adı ve fiyatı birleştirip hash oluşturur (Tekrar engelleme)
    ham = f"{urun}{yeni}".lower().replace(" ", "")
    return hashlib.md5(ham.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════
# KUYRUK İŞLEYİCİ (WORKER)
# ═══════════════════════════════════════════════════════════════
async def kuyruk_worker():
    log("BILGI", "Kuyruk Worker aktif, bekliyor...")
    while True:
        try:
            sablon, gorsel, link, magaza = await mesaj_kuyrugu.get()
            
            log("GÖNDERİM", f"Kuyruktan paylaşılıyor: {magaza}")
            
            # Linki metne ekle
            final_mesaj = f"{sablon}\n\n🔗 <a href='{link}'>ÜRÜNE GİTMEK İÇİN TIKLAYIN</a>"
            
            try:
                if gorsel:
                    await client.send_message(HEDEF_KANAL, final_mesaj, file=gorsel, parse_mode="html", link_preview=False)
                else:
                    await client.send_message(HEDEF_KANAL, final_mesaj, parse_mode="html", link_preview=False)
                
                log("OK", "Paylaşım başarılı.")
            except Exception as e:
                log("HATA", f"Gönderim sırasında hata: {e}")

            # Kuyruklar arası bekleme
            await asyncio.sleep(KUYRUK_BEKLEME)
            mesaj_kuyrugu.task_done()
            
        except Exception as e:
            log("KRITIK", f"Worker hatası: {e}")
            await asyncio.sleep(5)

# ═══════════════════════════════════════════════════════════════
# ANA OLAY DÖNGÜSÜ
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_dinle(event):
    try:
        ham_metin = event.message.text or ""
        indirim = indirim_oranini_bul(ham_metin)
        
        # 1. Filtre: İndirim Oranı
        if indirim < MIN_INDIRIM: return
        
        # 2. Filtre: Kara Liste
        for yasak in KARA_LISTE:
            if yasak in ham_metin.lower():
                log("FILTRE", f"Kara listedeki ürün atlandı: {yasak}")
                return

        # 3. Filtre: Tekrar Engelleme
        anahtar = benzerlik_anahtari(ham_metin)
        if anahtar in gorulmus_cache:
            log("FILTRE", "Aynı ürün zaten paylaşıldı/kuyrukta.")
            return
        gorulmus_cache[anahtar] = datetime.now()

        # Link Bulma (Buton veya Metin)
        link = ""
        if event.message.buttons:
            for row in event.message.buttons:
                for btn in row:
                    if hasattr(btn, 'url') and btn.url:
                        link = btn.url
                        break
        if not link:
            links = re.findall(r'(https?://\S+)', ham_metin)
            if links: link = links[0]
        
        if not link: return # Link yoksa fırsat değildir

        # Şablon Oluşturma
        urun = urun_adi_bul(ham_metin)
        eski, yeni = fiyat_bul(ham_metin)
        magaza = "Amazon" if "amazon" in ham_metin.lower() else "Hepsiburada" if "hepsi" in ham_metin.lower() else "Mağaza"
        
        sablon = (
            f"📦 <b>{urun.upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏪 Mağaza: <b>{magaza}</b>\n"
            f"💰 Piyasa: <s>{eski if eski else '---'} TL</s>\n"
            f"🔥 <b>Fırsat: {yeni} TL</b>\n\n"
            f"📉 İndirim: <b>%{indirim}</b>\n"
            f"🎁 Durum: <b>Stokta Var</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📢 @{HEDEF_KANAL.replace('@','')} | #İndirim"
        )

        # Görsel İndirme
        gorsel = None
        if event.message.media:
            gorsel = await client.download_media(event.message.media, bytes)

        # Kuyruğa Ekle
        await mesaj_kuyrugu.put((sablon, gorsel, link, magaza))
        log("KUYRUK", f"Sıraya alındı: {urun[:30]} (%{indirim})")

    except Exception as e:
        log("HATA", f"Mesaj işleme hatası: {e}")

# ═══════════════════════════════════════════════════════════════
# ADMIN PANELİ (TELEGRAM ÜZERİNDEN)
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(from_users=ADMIN_ID))
async def admin_panel(event):
    global MIN_INDIRIM, KUYRUK_BEKLEME
    text = event.message.text.lower()
    
    if text.startswith("/set_indirim"):
        val = int(text.split()[1])
        MIN_INDIRIM = val
        await event.reply(f"✅ Minimum indirim %{val} yapıldı.")
        
    elif text.startswith("/set_bekleme"):
        val = int(text.split()[1])
        KUYRUK_BEKLEME = val
        await event.reply(f"✅ Kuyruk bekleme süresi {val} saniye yapıldı.")

    elif text == "/durum":
        await event.reply(f"📊 **FırsatPulsu Durum**\nKuyrukta: {mesaj_kuyrugu.qsize()} ürün\nMin İndirim: %{MIN_INDIRIM}\nBekleme: {KUYRUK_BEKLEME}s")

# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════
async def main():
    log("SISTEM", "Bot başlatılıyor...")
    await client.start()
    
    # Arka plan işçisini başlat
    asyncio.create_task(kuyruk_worker())
    
    log("SISTEM", "--- FırsatPulsu Yayında ---")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
