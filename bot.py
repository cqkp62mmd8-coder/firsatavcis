import os
import json
import time
import hashlib
import requests
from datetime import datetime

# — AYARLAR —

TELEGRAM_TOKEN = os.environ.get(“TELEGRAM_TOKEN”)
CHANNEL_ID = os.environ.get(“CHANNEL_ID”)
MIN_INDIRIM = int(os.environ.get(“MIN_INDIRIM”, “50”))  # minimum indirim yüzdesi
CHECK_INTERVAL = int(os.environ.get(“CHECK_INTERVAL”, “1800”))  # 30 dakika

GORULMUS_FILE = “gorulmus.json”

# — YARDIMCI FONKSİYONLAR —

def gorulmus_yukle():
if os.path.exists(GORULMUS_FILE):
with open(GORULMUS_FILE, “r”) as f:
return json.load(f)
return []

def gorulmus_kaydet(liste):
with open(GORULMUS_FILE, “w”) as f:
json.dump(liste[-500:], f)  # son 500 ürünü sakla

def urun_id(urun):
return hashlib.md5(urun[“url”].encode()).hexdigest()

def telegram_gonder(mesaj):
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”
data = {
“chat_id”: CHANNEL_ID,
“text”: mesaj,
“parse_mode”: “HTML”,
“disable_web_page_preview”: False
}
try:
r = requests.post(url, data=data, timeout=10)
return r.status_code == 200
except Exception as e:
print(f”Telegram hatası: {e}”)
return False

def indirim_mesaji_olustur(urun):
magaza_emoji = {
“trendyol”: “🛍️”,
“amazon”: “📦”,
“hepsiburada”: “🏪”
}
emoji = magaza_emoji.get(urun[“magaza”].lower(), “🛒”)

```
simdi = datetime.now().strftime("%H:%M")

mesaj = (
    f"🔥 <b>%{urun['indirim_yuzdesi']} İNDİRİM!</b>\n\n"
    f"{emoji} <b>{urun['isim']}</b>\n\n"
    f"💰 <s>{urun['eski_fiyat']}₺</s> → <b>{urun['yeni_fiyat']}₺</b>\n"
    f"🏪 {urun['magaza'].capitalize()}\n"
    f"⏰ {simdi} itibarıyla\n\n"
    f"🔗 <a href='{urun['url']}'>Ürüne Git</a>\n\n"
    f"⚡ Stok sınırlı olabilir!"
)
return mesaj
```

# — TRENDYOL —

def trendyol_tara():
urunler = []
headers = {
“User-Agent”: “Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36”,
“Accept”: “application/json”
}

```
kategoriler = [
    "https://public.trendyol.com/discovery-web-searchgw-service/api/filter/Category?categoryId=1&storefrontId=1&culture=tr-TR&priceBucketCount=20",
]

# Trendyol kampanya ürünleri (flash sale endpoint)
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
                            "url": f"https://www.trendyol.com{p.get('url', '')}",
                            "magaza": "trendyol"
                        })
            except:
                continue
except Exception as e:
    print(f"Trendyol hatası: {e}")

return urunler
```

# — HEPSIBURADA —

def hepsiburada_tara():
urunler = []
headers = {
“User-Agent”: “Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36”,
“Accept”: “application/json”
}

```
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
                            "url": f"https://www.hepsiburada.com{p.get('url', '')}",
                            "magaza": "hepsiburada"
                        })
            except:
                continue
except Exception as e:
    print(f"Hepsiburada hatası: {e}")

return urunler
```

# — AMAZON TR —

def amazon_tara():
urunler = []
headers = {
“User-Agent”: “Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36”,
“Accept-Language”: “tr-TR,tr;q=0.9”
}

```
# Amazon TR lightning deals
url = "https://www.amazon.com.tr/deals?deals-widget=%257B%2522version%2522%253A1%252C%2522viewIndex%2522%253A0%252C%2522presetId%2522%253A%2522deals-collection-lightning-deals%2522%257D"

try:
    r = requests.get(url, headers=headers, timeout=15)
    # Amazon HTML parse gerektirir, temel kontrol
    if r.status_code == 200:
        print("Amazon TR erişimi başarılı, HTML parse gerekiyor.")
except Exception as e:
    print(f"Amazon hatası: {e}")

return urunler
```

# — ANA DÖNGÜ —

def tara():
print(f”[{datetime.now().strftime(’%H:%M:%S’)}] Tarama başlıyor…”)

```
gorulmus = gorulmus_yukle()
tum_urunler = []

tum_urunler += trendyol_tara()
tum_urunler += hepsiburada_tara()
tum_urunler += amazon_tara()

yeni_urunler = []
for u in tum_urunler:
    uid = urun_id(u)
    if uid not in gorulmus:
        yeni_urunler.append(u)
        gorulmus.append(uid)

gorulmus_kaydet(gorulmus)

# İndirim oranına göre sırala
yeni_urunler.sort(key=lambda x: x["indirim_yuzdesi"], reverse=True)

print(f"  → {len(tum_urunler)} ürün bulundu, {len(yeni_urunler)} yeni")

for urun in yeni_urunler[:10]:  # max 10 ürün paylaş
    mesaj = indirim_mesaji_olustur(urun)
    if telegram_gonder(mesaj):
        print(f"  ✓ Gönderildi: {urun['isim'][:40]}")
        time.sleep(3)  # spam önleme
```

if **name** == “**main**”:
print(“🤖 İndirim Botu Başlatıldı”)
print(f”   Min. indirim: %{MIN_INDIRIM}”)
print(f”   Kontrol aralığı: {CHECK_INTERVAL} saniye”)

```
while True:
    try:
        tara()
    except Exception as e:
        print(f"Hata: {e}")
    
    print(f"  ⏳ {CHECK_INTERVAL//60} dakika bekleniyor...")
    time.sleep(CHECK_INTERVAL)
```
