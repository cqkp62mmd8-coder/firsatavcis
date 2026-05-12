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
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = os.environ.get("ADMIN_ID", "")
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar", "@donanimhabersicakfirsatlar", "@yurticifirsat",
    "@firsatmerkez", "@indirimhabercisi", "@firsatpaylasim", "@uygunlasohbet",
    "@firsatavcilari01", "@firsatvakti", "@firsatyurdu", "@yurtdisifirsat"
]

GORULMUS_FILE    = "gorulmus.json"
ISTATISTIK_FILE  = "istatistik.json"
LOGO_DOSYA       = "logo.PNG"
MESAJ_BEKLEME    = 3          
GORULMUS_TTL     = 7 * 86400  
GORULMUS_MAX     = 5000       
WATCHDOG_ARALIK  = 3600       

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE & LOGGING
# ═══════════════════════════════════════════════════════════════
gorulmus_cache = None
istatistik_cache = None
ist_sayac = 0
son_mesaj_zamani = 0.0

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def log(seviye, mesaj):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{seviye}] {mesaj}")

# ═══════════════════════════════════════════════════════════════
# PERSISTENCE (GORULMUS & ISTATISTIK)
# ═══════════════════════════════════════════════════════════════
def gorulmus_yukle():
    global gorulmus_cache
    if gorulmus_cache is not None: return gorulmus_cache
    try:
        with open(GORULMUS_FILE, "r") as f: gorulmus_cache = json.load(f)
    except: gorulmus_cache = {}
    return gorulmus_cache

def gorulmus_kaydet():
    try:
        with open(GORULMUS_FILE, "w") as f: json.dump(gorulmus_cache, f)
    except Exception as e: log("HATA", f"gorulmus kaydet: {e}")

def gorulmus_var_mi(mid):
    return mid in gorulmus_yukle()

def gorulmus_ekle(mid):
    gorulmus_yukle()
    gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()
    gorulmus_kaydet()

def istatistik_yukle():
    global istatistik_cache
    if istatistik_cache is not None: return istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "r") as f: istatistik_cache = json.load(f)
    except: istatistik_cache = {"toplam": 0, "kanallar": {}, "gunluk": {}, "magaza": {}}
    return istatistik_cache

def istatistik_kaydet():
    try:
        with open(ISTATISTIK_FILE, "w") as f: json.dump(istatistik_cache, f)
    except: pass

def istatistik_guncelle(kanal_adi, magaza):
    global ist_sayac
    ist = istatistik_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
    ist["magaza"][magaza] = ist["magaza"].get(magaza, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    ist_sayac += 1
    if ist_sayac >= 5:
        istatistik_kaydet()
        ist_sayac = 0

# ═══════════════════════════════════════════════════════════════
# CORE LOGIC (PARSING & IMAGE)
# ═══════════════════════════════════════════════════════════════
def emoji_temizle(metin):
    return "".join(k for k in metin if unicodedata.category(k) not in ("So", "Sm", "Sk")).strip()

def mesaj_id_olustur(metin):
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    temiz = re.sub(r'https?://\S+', '', temiz).strip()
    return hashlib.sha256(temiz.encode()).hexdigest()[:32]

def indirim_oranini_bul(metin):
    if not metin: return 0
    kaliplar = [r"-\s*%\s*(\d+)", r"%\s*(\d+)", r"(\d+)\s*%"]
    for k in kaliplar:
        eslesme = re.findall(k, metin)
        if eslesme:
            degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
            if degerler: return max(degerler)
    return 0

def fiyat_parse(s):
    try:
        temiz = s.strip()
        if "," in temiz and "." in temiz: temiz = temiz.replace(".", "").replace(",", ".")
        elif "," in temiz: temiz = temiz.replace(",", ".")
        return float(temiz)
    except: return 0.0

def fiyat_bul(metin):
    eslesme = re.findall(r"([\d.,]+)\s*(?:TL|tl|₺|lira)", metin or "")
    if len(eslesme) >= 2:
        degerler = [(fiyat_parse(f), f) for f in eslesme if fiyat_parse(f) > 0]
        if len(degerler) >= 2:
            sirali = sorted(degerler, key=lambda x: x[0], reverse=True)
            return sirali[0][1], sirali[-1][1]
    return None, None

def magaza_bul(metin):
    metin_k = (metin or "").lower()
    mapping = [("Trendyol", "trendyol"), ("Hepsiburada", "hepsiburada"), ("Amazon TR", "amazon"), 
               ("MediaMarkt", "mediamarkt"), ("Teknosa", "teknosa"), ("Gratis", "gratis"),
               ("Boyner", "boyner"), ("N11", "n11.com"), ("Temu", "temu.com")]
    for magaza, anahtar in mapping:
        if anahtar in metin_k: return magaza
    return "E-Ticaret"

def urun_adi_bul(metin):
    if not metin: return None
    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    for satir in satirlar:
        temiz = emoji_temizle(satir)
        if (len(temiz) >= 8 and "http" not in satir and "TL" not in satir and "₺" not in satir
            and not re.search(r"indirim|kampanya|firsat", temiz.lower())):
            return temiz # Sadeleştirme yok, olduğu gibi döner
    return None

def link_bul(metin):
    if not metin: return None
    linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
    resim_uzantilari = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    temiz_linkler = [l for l in linkler if not l.lower().endswith(resim_uzantilari) and "t.me" not in l.lower()]
    
    if not temiz_linkler: return None
    oncelik = ["trendyol.com", "hepsiburada.com", "amazon.com.tr", "ty.gl", "hb.gl", "amzn.to"]
    for link in temiz_linkler:
        for o in oncelik:
            if o in link: return link
    return temiz_linkler[0]

def logo_ekle(gorsel_bytes):
    try:
        if not os.path.exists(LOGO_DOSYA):
            log("UYARI", "Logo dosyası bulunamadı!")
            return gorsel_bytes
        urun_img = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun_img.size
        logo = Image.open(LOGO_DOSYA).convert("RGBA")
        boyut = int(min(w, h) * 0.18)
        logo = logo.resize((boyut, boyut), Image.LANCZOS)
        urun_img.paste(logo, (w - boyut - 20, h - boyut - 20), logo)
        cikti = BytesIO()
        urun_img.convert("RGB").save(cikti, format="JPEG", quality=95)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("HATA", f"Logo işleme hatası: {e}")
        return gorsel_bytes

def sablon_olustur(metin, indirim):
    if indirim <= 0: return None
    magaza = magaza_bul(metin)
    urun = urun_adi_bul(metin)
    eski, yeni = fiyat_bul(metin)
    link = link_bul(metin)

    s = [f"🔥 <b>%{indirim} İNDİRİM!</b>", ""]
    if urun: s.append(f"🏷️ <b>{urun}</b>"); s.append("")
    s.append(f"🏪 <b>{magaza}</b>"); s.append("")

    # Marka mı ürün mü kontrolü: Sadece ürün fiyatı varsa fiyat satırı eklenir
    if eski and yeni:
        s.append(f"💰 <s>{eski} TL</s>  →  <b>{yeni} TL</b>")
        s.append("")
    
    if link: s.append(f"🔗 <a href='{link}'>Fırsata Git</a>"); s.append("")
    s.append("⚡ Stok sınırlı olabilir!"); s.append(f"📢 @{HEDEF_KANAL.lstrip('@')}")
    return "\n".join(s)

# ═══════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(chats=KAYNAK_KANALLAR))
async def mesaj_geldi(event):
    global son_mesaj_zamani
    try:
        metin = event.message.text or ""
        indirim = indirim_oranini_bul(metin)
        if indirim < MIN_INDIRIM: return

        mid = mesaj_id_olustur(metin)
        if gorulmus_var_mi(mid): return
        gorulmus_ekle(mid)

        sablon = sablon_olustur(metin, indirim)
        if not sablon: return

        # Rate Limiting
        loop = asyncio.get_running_loop()
        gecen = loop.time() - son_mesaj_zamani
        if gecen < MESAJ_BEKLEME: await asyncio.sleep(MESAJ_BEKLEME - gecen)
        son_mesaj_zamani = loop.time()

        if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
            gorsel_bytes = await client.download_media(event.message.media, bytes)
            if gorsel_bytes:
                islenmis_gorsel = logo_ekle(gorsel_bytes)
                buf = BytesIO(islenmis_gorsel)
                buf.name = "urun.jpg"
                await client.send_message(HEDEF_KANAL, sablon, file=buf, parse_mode="html")
            else:
                await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")
        else:
            await client.send_message(HEDEF_KANAL, sablon, parse_mode="html")

        istatistik_guncelle(getattr(event.chat, "username", "bilinmiyor"), magaza_bul(metin))
    except Exception as e: log("HATA", str(e))

async def main():
    if not SESSION_STRING: log("KRITIK", "SESSION_STRING eksik!"); return
    await client.start()
    log("OK", "Bot çalışıyor...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
