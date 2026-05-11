import os
import json
import time
import hashlib
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
MIN_INDIRIM = int(os.environ.get("MIN_INDIRIM", "50"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "1800"))

GORULMUS_FILE = "gorulmus.json"

def gorulmus_yukle():
    if os.path.exists(GORULMUS_FILE):
        with open(GORULMUS_FILE, "r") as f:
            return json.load(f)
    return []

def gorulmus_kaydet(liste):
    with open(GORULMUS_FILE, "w") as f:
        json.dump(liste[-500:], f)

def urun_id(urun):
    return hashlib.md5(urun["url"].encode()).hexdigest()

def telegram_gonder(mesaj):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    data = {
        "chat_id": CHANNEL_ID,
        "text": mesaj,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print("Telegram hatasi: " + str(e))
        return False

def indirim_mesaji_olustur(urun):
    magaza_emoji = {
        "trendyol": "Trendyol",
        "amazon": "Amazon TR",
        "hepsiburada": "Hepsiburada"
    }
    magaza_adi = magaza_emoji.get(urun["magaza"].lower(), urun["magaza"])
    simdi = datetime.now().strftime("%H:%M")
    mesaj = (
        "%" + str(urun["indirim_yuzdesi"]) + " INDIRIM!\n\n"
        + urun["isim"] + "\n\n"
        "Eski: " + str(urun["eski_fiyat"]) + " TL\n"
        "Yeni: " + str(urun["yeni_fiyat"]) + " TL\n"
        "Magaza: " + magaza_adi + "\n"
        "Saat: " + simdi + "\n\n"
        + urun["url"] + "\n\n"
        "Stok sinirli olabilir!"
    )
    return mesaj

def trendyol_tara():
    urunler = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    url = "https://public.trendyol.com/discovery-web-productgw-service/api/campaign-products?campaignId=flash-sale&storefrontId=1&culture=tr-TR"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            products = data.get("result", {}).get("products", [])
            for p in products:
                try:
                    eski = p.get("originalPrice", {}).get("value", 0)
                    yeni = p.get("price", {}).get("value", 0)
                    if eski and yeni and eski > yeni:
                        indirim = round((1 - yeni / eski) * 100)
                        if indirim >= MIN_INDIRIM:
                            urunler.append({
                                "isim": p.get("name", "")[:60],
                                "eski_fiyat": eski,
                                "yeni_fiyat": yeni,
                                "indirim_yuzdesi": indirim,
                                "url": "https://www.trendyol.com" + p.get("url", ""),
                                "magaza": "trendyol"
                            })
                except:
                    continue
    except Exception as e:
        print("Trendyol hatasi: " + str(e))
    return urunler

def hepsiburada_tara():
    urunler = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    url = "https://www.hepsiburada.com/api/sf/search?q=&groupSeller=true&itemsPerPage=48&offset=0&sort=discountRatioAsc"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            products = data.get("products", [])
            for p in products:
                try:
                    eski = p.get("originalPrice", 0)
                    yeni = p.get("finalPrice", 0)
                    if eski and yeni and eski > yeni:
                        indirim = round((1 - yeni / eski) * 100)
                        if indirim >= MIN_INDIRIM:
                            urunler.append({
                                "isim": p.get("name", "")[:60],
                                "eski_fiyat": round(eski, 2),
                                "yeni_fiyat": round(yeni, 2),
                                "indirim_yuzdesi": indirim,
                                "url": "https://www.hepsiburada.com" + p.get("url", ""),
                                "magaza": "hepsiburada"
                            })
                except:
                    continue
    except Exception as e:
        print("Hepsiburada hatasi: " + str(e))
    return urunler

def tara():
    print("[" + datetime.now().strftime("%H:%M:%S") + "] Tarama basliyor...")
    gorulmus = gorulmus_yukle()
    tum_urunler = []
    tum_urunler += trendyol_tara()
    tum_urunler += hepsiburada_tara()
    yeni_urunler = []
    for u in tum_urunler:
        uid = urun_id(u)
        if uid not in gorulmus:
            yeni_urunler.append(u)
            gorulmus.append(uid)
    gorulmus_kaydet(gorulmus)
    yeni_urunler.sort(key=lambda x: x["indirim_yuzdesi"], reverse=True)
    print("  -> " + str(len(tum_urunler)) + " urun bulundu, " + str(len(yeni_urunler)) + " yeni")
    for urun in yeni_urunler[:10]:
        mesaj = indirim_mesaji_olustur(urun)
        if telegram_gonder(mesaj):
            print("  Gonderildi: " + urun["isim"][:40])
            time.sleep(3)

if __name__ == "__main__":
    print("Indirim Botu Baslatildi")
    print("Min. indirim: %" + str(MIN_INDIRIM))
    print("Kontrol araligi: " + str(CHECK_INTERVAL) + " saniye")
    while True:
        try:
            tara()
        except Exception as e:
            print("Hata: " + str(e))
        print("  " + str(CHECK_INTERVAL // 60) + " dakika bekleniyor...")
        time.sleep(CHECK_INTERVAL)
