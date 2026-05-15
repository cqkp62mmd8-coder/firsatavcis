import os
import asyncio
import re
import json
import hashlib
import unicodedata
from io import BytesIO
from datetime import datetime, timezone, timedelta
from PIL import Image
try:
    import pytesseract # OCR için eklendi (pip install pytesseract)
except ImportError:
    pytesseract = None

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaPhoto

# ═══════════════════════════════════════════════════════════════
# AYARLAR & LOJİSTİK
# ═══════════════════════════════════════════════════════════════
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
HEDEF_KANAL    = os.environ.get("CHANNEL_ID", "")
ADMIN_ID       = int(os.environ.get("ADMIN_ID", "0"))
MIN_INDIRIM    = int(os.environ.get("MIN_INDIRIM", "50"))

KARA_LISTE = ["çorap", "kılıf", "sticker", "kalem", "defter", "ekran koruyucu", "kitap"]
YASAKLI_FILIGRANLAR = ["donanimhaber", "firsatmerkez", "indirimhabercisi", "t.me"]

KAYNAK_KANALLAR = [
    "@amazonsicakfirsatlar", "@donanimhabersicakfirsatlar", "@yurticifirsat",
    "@firsatmerkez", "@indirimhabercisi", "@firsatpaylasim",
    "@uygunlasohbet", "@firsatavcilari01"
]

mesaj_kuyrugu = asyncio.Queue()
KUYRUK_BEKLEME = 120 # 2 dakika

# Global Cache'ler
gorulmus_cache = {}
istatistik_cache = {"toplam": 0, "kanallar": {}, "gunluk": {}}
aktif_mesajlar = {} # [PRO: Özellik 1] Dinamik güncelleyici için gönderilen mesajları tutar

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ═══════════════════════════════════════════════════════════════
# [PRO ÖZELLİK 4] ŞİŞİRİLMİŞ FİYAT DEDEKTÖRÜ (SAHTE İNDİRİM KALKANI)
# ═══════════════════════════════════════════════════════════════
def sahte_indirim_mi(indirim, eski_fiyat, magaza):
    """
    Şişirilmiş fiyatları algılar. 
    Bilinmeyen mağazalardaki %85 üstü indirimleri veya 
    çok yüksek eski fiyatlı şüpheli ürünleri reddeder.
    """
    guvenilir_magazalar = ["Amazon TR", "MediaMarkt", "Teknosa"]
    
    if indirim > 85 and magaza not in guvenilir_magazalar:
        return True
    
    if eski_fiyat > 10000 and indirim > 80:
        return True # Örn: 15.000 TL'den 2.000 TL'ye düşen sahte saat/parfüm vb.
        
    return False

# ═══════════════════════════════════════════════════════════════
# [PRO ÖZELLİK 2] ALGORİTMİK FIRSAT SKORU (DEAL RATING)
# ═══════════════════════════════════════════════════════════════
def firsat_skoru_hesapla(indirim, magaza, yeni_fiyat):
    """Fırsatın kalitesini 10 üzerinden puanlar."""
    skor = 5.0
    
    # İndirim oranına göre puan
    if indirim >= 70: skor += 3.0
    elif indirim >= 50: skor += 1.5
    
    # Mağaza güvenilirliğine göre puan
    if magaza == "Amazon TR": skor += 1.0
    elif magaza in ["Trendyol", "Hepsiburada"]: skor += 0.5
    
    # Dip fiyat bonusu
    if yeni_fiyat > 0 and yeni_fiyat < 100: skor += 1.0
    
    skor = min(skor, 10.0) # Maksimum 10 olabilir
    
    if skor >= 9.0: return f"🌟 {skor}/10 (KUSURSUZ FIRSAT)"
    elif skor >= 7.5: return f"🔥 {skor}/10 (ÇOK SICAK)"
    else: return f"⭐ {skor}/10 (İYİ FIRSAT)"

# ═══════════════════════════════════════════════════════════════
# [PRO ÖZELLİK 5] GÖRSEL METİN OKUMA (OCR FILTRESI)
# ═══════════════════════════════════════════════════════════════
def gorselde_filigran_var_mi(gorsel_bytes):
    """Görseli Tesseract ile okur, rakip kanalın yazısı varsa True döner."""
    if not pytesseract or not gorsel_bytes:
        return False # OCR kütüphanesi yoksa atla
        
    try:
        img = Image.open(BytesIO(gorsel_bytes))
        okunan_metin = pytesseract.image_to_string(img).lower()
        
        for yasakli in YASAKLI_FILIGRANLAR:
            if yasakli in okunan_metin:
                return True
        return False
    except Exception as e:
        print(f"[OCR Hata] {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# LOJİSTİK VE YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════
def mesaj_uygun_mu(metin):
    metin_k = metin.lower()
    for yasakli in KARA_LISTE:
        if yasakli in metin_k: return False, f"Kara liste: {yasakli}"
    return True, "Uygun"

def benzerlik_anahtari_olustur(metin):
    # Fonksiyonun tam hali (Önceki koddan)
    temiz = re.sub(r'\s+', ' ', (metin or "").strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()

# (urun_adi_bul, fiyat_bul, link_bul, magaza_bul fonksiyonları buraya eklenecek)
# Not: Önceki sürümdeki standart parse fonksiyonlarını burada varsayıyoruz.
def varsayilan_fiyat_bul(metin): return 1000.0, 500.0 # Örnek stub
def varsayilan_link_bul(metin): return "https://link" # Örnek stub
def varsayilan_magaza_bul(metin): return "Trendyol" # Örnek stub

# ═══════════════════════════════════════════════════════════════
# [PRO ÖZELLİK 1] DİNAMİK FIRSAT GÜNCELLEYİCİ (OTOKONTROL)
# ═══════════════════════════════════════════════════════════════
async def dinamik_zaman_asimi_kontrolcusu():
    """Arka planda çalışarak 12 saati geçen mesajlara 'Fırsat Bitti' etiketi basar."""
    print("[BILGI] Dinamik zaman aşımı kontrolcüsü devrede.")
    while True:
        try:
            simdi = datetime.now()
            silinecek_id_ler = []
            
            for msg_id, data in aktif_mesajlar.items():
                zaman, metin = data
                gecen_sure = (simdi - zaman).total_seconds() / 3600 # Saat cinsinden
                
                # 12 Saat geçen fırsatları güncelle
                if gecen_sure >= 12:
                    yeni_metin = f"❌ <b>BU FIRSATIN SÜRESİ DOLDU</b> ❌\n\n<s>{metin}</s>"
                    
                    try:
                        await client.edit_message(HEDEF_KANAL, msg_id, yeni_metin, parse_mode="html")
                        print(f"[{msg_id}] Fırsat zaman aşımına uğratıldı.")
                    except Exception as edit_e:
                        print(f"[Edit Hata] {edit_e}")
                        
                    silinecek_id_ler.append(msg_id)
            
            # Güncellenenleri takip listesinden çıkar
            for mid in silinecek_id_ler:
                del aktif_mesajlar[mid]
                
        except Exception as e:
            print(f"[Dinamik Kontrol Hata] {e}")
            
        await asyncio.sleep(3600) # Her 1 saatte bir kontrol et

# ═══════════════════════════════════════════════════════════════
# KUYRUK İŞLEYİCİ
# ═══════════════════════════════════════════════════════════════
async def kuyruk_isleyici():
    print("[BILGI] Kuyruk işleyici devrede.")
    while True:
        try:
            gorev = await mesaj_kuyrugu.get()
            sablon, gorsel = gorev

            if gorsel:
                msg = await client.send_message(H
