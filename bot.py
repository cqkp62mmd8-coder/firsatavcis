import os
import asyncio
import re
import hashlib
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto

# ═══════════════════════════════════════════════════════════════
# PROFESYONEL AYARLAR & LOJİSTİK
# ═══════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = int(os.environ.get("ADMIN_ID", "0"))

MIN_INDIRIM    = 50
KUYRUK_BEKLEME = 180 
KARA_LISTE     = ["çorap", "kılıf", "sticker", "kalem", "defter", "ekran koruyucu"]

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar", "@donanimhabersicakfirsatlar", "@yurticifirsat",
    "@firsatmerkez", "@indirimhabercisi", "@firsatpaylasim",
    "@uygunlasohbet", "@firsatavcilari01", "@firsatvakti",
    "@firsatyurdu", "@yurtdisifirsat"
]

mesaj_kuyrugu = asyncio.Queue()
gorulmus_cache = {}

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ═══════════════════════════════════════════════════════════════
# SAĞLAMLAŞTIRILMIŞ ANALİZ MOTORU
# ═══════════════════════════════════════════════════════════════

def log(seviye, mesaj):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{seviye}] {mesaj}")

def indirim_oranini_bul(metin):
    # Linklerin içindeki url karakterlerini (%20, %28 vb.) yoksay, sadece 1 ve 99 arasını al.
    bulunanlar = re.findall(r'%(\d{1,2})\b', metin)
    gecerli_indirimler = [int(i) for i in bulunanlar if 1 <= int(i) <= 99]
    if gecerli_indirimler:
        return max(gecerli_indirimler)
    return 0

def fiyat_bul(metin):
    # Hem "₺100", hem "100 TL", hem de "1.500,50 TL" formatlarını kusursuz yakalar.
    fiyatlar = re.findall(r'([\d\.,]+)\s?(?:TL|₺|tl)|(?:TL|₺|tl)\s?([\d\.,]+)', metin)
    temiz_fiyatlar = []
    
    for f_tuple in fiyatlar:
        for f in f_tuple:
            if f:
                temiz_fiyatlar.append(f.strip())
                
    if len(temiz_fiyatlar) >= 2:
        return temiz_fiyatlar[0], temiz_fiyatlar[-1] # İlk bulduğu eski, son bulduğu yeni
    elif len(temiz_fiyatlar) == 1:
        return None, temiz_fiyatlar[0]
    return None, None

def urun_adi_bul(metin):
    # Markdown yıldızlarını ve gereksiz karakterleri temizle
    metin = metin.replace('**', '').replace('*', '').replace('__', '')
    satirlar = [s.strip() for s in metin.split('\n') if s.strip() and len(s) > 5 and "http" not in s]
    
    if satirlar:
        ad = satirlar[0].replace('📦', '').replace('🔥', '').replace('📌', '').strip()
        # Eğer satırın sonunda gereksiz virgüller kaldıysa temizle
        ad = ad.rstrip(',').rstrip('-').strip()
        return ad[:65]
    return "Fırsat Ürünü"

def benzerlik_anahtari(metin):
    urun = urun_adi_bul(metin)
    _, yeni = fiyat_bul(metin)
    ham = f"{urun}{yeni}".lower().replace(" ", "")
    return hashlib.md5(ham.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════
# KUYRUK İŞLEYİCİ (WORKER)
# ═══════════════════════════════════════════════════════════════
async def kuyruk_worker():
    log("BILGI", "Kuyruk Worker aktif, bekliyor...")
    while True:
        try:
            sablon, gorsel_medya, link, magaza = await mesaj_kuyrugu.get()
            
            final_mesaj = f"{sablon}\n\n🔗 <a href='{link}'>ÜRÜNE GİTMEK İÇİN TIKLAYIN</a>"
            
            # gorsel_medya doğrudan Telegram Media objesidir, dosya olarak inmez, anında foto olarak gider!
            if gorsel_medya:
                await client.send_message(HEDEF_KANAL, final_mesaj, file=gorsel_medya, parse_mode="html", link_preview=False)
            else:
                await client.send_message(HEDEF_KANAL, final_mesaj, parse_mode="html", link_preview=False)
                
            log("OK", "Paylaşım başarılı.")
            await asyncio.sleep(KUYRUK_BEKLEME)
            mesaj_kuyrugu.task_done()
            
        except Exception as e:
            log("HATA", f"Worker hatası: {e}")
            await asyncio.sleep(5)

# ═══════════════════════════════════════════════════════════════
# ANA OLAY DÖNGÜSÜ
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_dinle(event):
    try:
        ham_metin = event.message.text or ""
        indirim = indirim_oranini_bul(ham_metin)
        
        if indirim < MIN_INDIRIM: return
        
        for yasak in KARA_LISTE:
            if yasak in ham_metin.lower():
                return

        anahtar = benzerlik_anahtari(ham_metin)
        if anahtar in gorulmus_cache:
            return
        gorulmus_cache[anahtar] = datetime.now()

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
        
        if not link: return 

        urun = urun_adi_bul(ham_metin)
        eski, yeni = fiyat_bul(ham_metin)
        
        # Fiyatı bulamadıysa mesajı çöpe at (Hatalı çıktı vermesini engeller)
        if not yeni: return
        
        magaza = "Amazon" if "amazon" in ham_metin.lower() else "Hepsiburada" if "hepsi" in ham_metin.lower() else "Mağaza"
        
        sablon = (
            f"📦 <b>{urun.upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏪 Mağaza: <b>{magaza}</b>\n"
            f"💰 Piyasa: <s>{eski if eski else 'Belirtilmedi'} TL</s>\n"
            f"🔥 <b>Fırsat: {yeni} TL</b>\n\n"
            f"📉 İndirim: <b>%{indirim}</b>\n"
            f"🎁 Durum: <b>Stokta Var</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📢 @{HEDEF_KANAL.replace('@','')} | #İndirim"
        )

        # Görseli bayt olarak indirmek yerine objeyi doğrudan alıyoruz (Dosya sorununu çözer)
        gorsel_medya = None
        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            gorsel_medya = event.message.media

        await mesaj_kuyrugu.put((sablon, gorsel_medya, link, magaza))

    except Exception as e:
        log("HATA", f"Mesaj işleme hatası: {e}")

# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════
async def main():
    log("SISTEM", "Bot başlatılıyor...")
    await client.start()
    asyncio.create_task(kuyruk_worker())
    log("SISTEM", "--- FırsatPulsu Hatasız Sürüm Yayında ---")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
