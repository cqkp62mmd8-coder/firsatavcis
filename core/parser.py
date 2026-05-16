"""
Mesaj ayrıştırma: indirim, fiyat, mağaza, kategori, kalite skoru.
"""
import re
from datetime import datetime, timezone
from config.settings import (
    KATEGORILER, MAGAZA_HASHTAG, MAGAZA_EMOJI,
    KATEGORI_YAZI, MARKA_SPAM_LIMIT, MARKA_SPAM_SURE,
)
from utils.text import emoji_temizle

# ─── Marka Spam Koruması ───────────────────────────────────────
_marka_son_mesaj: dict[str, list] = {}


def marka_spam_kontrol(magaza: str) -> bool:
    simdi = datetime.now(timezone.utc).timestamp()
    _marka_son_mesaj.setdefault(magaza, [])
    _marka_son_mesaj[magaza] = [
        t for t in _marka_son_mesaj[magaza] if simdi - t < MARKA_SPAM_SURE
    ]
    if len(_marka_son_mesaj[magaza]) >= MARKA_SPAM_LIMIT:
        return True
    _marka_son_mesaj[magaza].append(simdi)
    return False


# ─── İndirim Oranı ─────────────────────────────────────────────
def indirim_oranini_bul(metin: str) -> int:
    if not metin:
        return 0
    ml = metin.lower()

    kaliplar = [
        r"-\s*%\s*(\d+)",
        r"indirim\s*:\s*-?\s*%\s*(\d+)",
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
    ]
    for kalip in kaliplar:
        eslesme = re.findall(kalip, ml)
        if eslesme:
            degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
            if degerler:
                return max(degerler)

    al_ode = re.findall(r"(\d+)\s*al\s*(\d+)\s*(?:öde|ode)", ml)
    if al_ode:
        al, ode = int(al_ode[0][0]), int(al_ode[0][1])
        if al > ode > 0:
            ind = round((1 - ode / al) * 100)
            if 1 <= ind <= 99:
                return ind

    metin_linksiz = re.sub(r'https?://\S+', '', metin)
    eslesme = re.findall(r"%(\d{1,2})\b", metin_linksiz)
    degerler = [int(x) for x in eslesme if 1 <= int(x) <= 99]
    if degerler:
        return max(degerler)

    if re.search(r"kupon|sepette\s*[\d.,]+\s*tl|sepete\s*\d+\s*adet", ml):
        return 30

    stok = any(k in ml for k in ["stoklar eriyor", "son stok", "dip fiyat", "en düşük", "kaçmaz", "hemen yakala"])
    fiyat = bool(re.search(r"[\d.,]+\s*(?:tl|₺)", ml))
    if stok and fiyat:
        return 50

    if any(x in ml for x in ["hb.biz", "trendyol.com", "ty.gl", "amazon.com.tr", "n11.com", "sl.n11.com"]):
        return 20

    return 0


# ─── Fiyat ─────────────────────────────────────────────────────
def fiyat_parse(s: str) -> float:
    try:
        s = s.strip()
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def fiyat_bul(metin: str) -> tuple:
    if not metin:
        return None, None, 0, 0

    indirimli = re.findall(
        r"(?:indirimli\s*fiyat|sale\s*price)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)",
        metin, re.IGNORECASE,
    )
    normal = re.findall(
        r"(?:normal\s*fiyat|liste\s*fiyat|piyasa)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)",
        metin, re.IGNORECASE,
    )
    if indirimli and normal:
        yv = fiyat_parse(indirimli[0])
        ev = fiyat_parse(normal[0])
        if ev > yv > 0:
            return normal[0], indirimli[0], ev, yv

    bulunan = re.findall(r"₺\s*([\d.,]+)", metin) + re.findall(r"([\d.,]+)\s*(?:TL|tl|lira)", metin)
    if len(bulunan) >= 2:
        degerler = [(fiyat_parse(f), f) for f in bulunan if fiyat_parse(f) > 0]
        if len(degerler) >= 2:
            sirali = sorted(degerler, reverse=True)
            ev, es = sirali[0]
            yv, ys = sirali[-1]
            if ev > yv:
                return es, ys, ev, yv
    elif len(bulunan) == 1:
        return None, bulunan[0], 0, fiyat_parse(bulunan[0])

    return None, None, 0, 0


# ─── Mağaza / Kategori ─────────────────────────────────────────
def magaza_bul(metin: str) -> str:
    ml = (metin or "").lower()
    for magaza, anahtar in [
        ("Trendyol", "trendyol"), ("Hepsiburada", "hepsiburada"),
        ("Amazon TR", "amazon"), ("MediaMarkt", "mediamarkt"),
        ("Teknosa", "teknosa"), ("Gratis", "gratis"), ("Boyner", "boyner"),
        ("N11", "n11.com"), ("Çiçeksepeti", "ciceksepeti"), ("Temu", "temu.com"),
    ]:
        if anahtar in ml:
            return magaza
    return "E-Ticaret"


def kategori_bul(metin: str) -> tuple:
    ml = (metin or "").lower()
    for kat_adi, kat in KATEGORILER.items():
        if any(a in ml for a in kat["anahtar"]):
            return kat_adi, kat["ikon"], kat["hashtag"]
    return "genel", "🛍️", ["#Fırsat", "#İndirim"]


# ─── Diğer Ayrıştırıcılar ──────────────────────────────────────
def stok_durumu_bul(metin: str) -> bool:
    ml = (metin or "").lower()
    return any(k in ml for k in ["stoklar eriyor", "son stok", "tükeniyor", "sınırlı stok"])


def indirim_turu_bul(metin: str) -> str:
    ml = (metin or "").lower()
    kaliplar = [
        r"\w+\s*(?:urunlerinde|markasinda|serisinde)\s*%\d+",
        r"tum\s*\w*\s*urunlerde",
        r"secili\s*\w*\s*urunlerde",
    ]
    return "marka" if any(re.search(k, ml) for k in kaliplar) else "urun"


def urun_adi_bul(metin: str) -> str | None:
    if not metin:
        return None
    for satir in [s.strip() for s in metin.split("\n") if s.strip()]:
        temiz = emoji_temizle(satir)
        if (
            len(temiz) >= 8
            and not satir.startswith("#")
            and not satir.startswith("@")
            and "http" not in satir
            and "TL" not in satir
            and "₺" not in satir
            and not re.search(r"\d+%|%\d+", satir)
        ):
            return temiz[:80]
    return None


def link_bul(metin: str, buton_linkleri: list | None = None) -> str | None:
    oncelik = [
        "trendyol.com", "hepsiburada.com", "amazon.com.tr", "mediamarkt.com.tr",
        "teknosa.com", "ty.gl", "hb.gl", "n11.com", "ciceksepeti.com",
        "aliexpress.com", "sl.n11.com", "hb.biz",
    ]
    if buton_linkleri:
        for bl in buton_linkleri:
            if any(p in bl for p in oncelik):
                return bl
        for bl in buton_linkleri:
            if "google.com" not in bl and "t.me" not in bl:
                return bl
    if metin:
        linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
        for link in linkler:
            if any(p in link for p in oncelik):
                return link
        for link in linkler:
            if "t.me" not in link and "google.com" not in link:
                return link
    return None


def kupon_bul(metin: str) -> str | None:
    if not metin:
        return None
    for kalip in [
        r"kupon\s*[:\-]?\s*([A-Z0-9]{4,20})",
        r"indirim\s*kodu?\s*[:\-]?\s*([A-Z0-9]{4,20})",
    ]:
        eslesme = re.findall(kalip, metin, re.IGNORECASE)
        if eslesme:
            return eslesme[0].upper()
    return None


def minimum_siparis_bul(metin: str) -> str | None:
    if not metin:
        return None
    for kalip in [
        r"(\d+)\s*adet\s*al[ıi]mda",
        r"min(?:imum)?\s*(\d+)\s*(?:tl|adet)",
        r"(\d[\d.,]*)\s*tl\s*alışverişte",
    ]:
        eslesme = re.findall(kalip, metin, re.IGNORECASE)
        if eslesme:
            return eslesme[0]
    return None


# ─── Kalite & Fırsat Skoru ─────────────────────────────────────
def mesaj_kalite_skoru(metin: str, indirim: int, buton_linkleri: list) -> int:
    skor = 0
    if indirim >= 50:   skor += 40
    elif indirim >= 30: skor += 25
    else:               skor += 10
    if link_bul(metin, buton_linkleri): skor += 20
    e, y, ev, yv = fiyat_bul(metin)
    if e and y:   skor += 20
    elif y:       skor += 10
    if urun_adi_bul(metin): skor += 15
    if stok_durumu_bul(metin): skor += 5
    return skor


def sahte_indirim_mi(metin: str, indirim: int) -> bool:
    if indirim < 75:
        return False
    ml = metin.lower()
    guvenilir = [
        "apple", "samsung", "sony", "lg", "philips", "dyson", "nike",
        "adidas", "puma", "asus", "lenovo", "dell", "xiaomi", "huawei",
        "bosch", "siemens", "toshiba", "canon", "hp", "acer",
    ]
    for marka in guvenilir:
        if marka in ml:
            return False
    return indirim >= 88


def firsat_skoru_hesapla(metin: str, indirim: int, buton_linkleri: list) -> float:
    skor = 0.0
    if indirim >= 80:   skor += 4.0
    elif indirim >= 70: skor += 3.5
    elif indirim >= 60: skor += 3.0
    elif indirim >= 50: skor += 2.5
    elif indirim >= 30: skor += 1.5
    else:               skor += 0.5

    link = link_bul(metin, buton_linkleri)
    if link:
        if any(x in link for x in ["trendyol.com", "amazon.com.tr", "hepsiburada.com"]):
            skor += 2.0
        else:
            skor += 1.0

    e, y, ev, yv = fiyat_bul(metin)
    if e and y and ev > 0 and yv > 0:
        skor += 2.0
        if ev - yv >= 100:
            skor += 0.3
    elif y:
        skor += 1.0

    if urun_adi_bul(metin): skor += 1.0
    if stok_durumu_bul(metin): skor += 0.2
    if sahte_indirim_mi(metin, indirim): skor -= 2.0
    return round(max(0.0, min(10.0, skor)), 1)
