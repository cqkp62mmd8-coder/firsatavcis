"""
Mesaj analizi: indirim oranı, fiyat, mağaza, kategori, kalite & fırsat skoru.
Saf fonksiyonlar — dış bağımlılık yok (config hariç).
"""
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import config

# ════════════════════════════════════════════════════════════════
# Link temizleme — affiliate / tracking parametrelerini sil
# ════════════════════════════════════════════════════════════════

_TRACKING_PARAMS = {
    # UTM
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    # Genel affiliate/ref
    "ref", "tag", "source", "aff", "affid", "affiliate", "affiliate_id",
    "aff_id", "aff_sub", "aff_sub2", "aff_sub3", "aff_sub4", "aff_sub5",
    "tracking_id", "clickid", "click_id", "clickref", "subid",
    # Sosyal medya / reklam
    "fbclid", "gclid", "msclkid", "dclid", "yclid", "igshid", "ttclid",
    # Trendyol
    "boutiqueId", "merchantId", "campaignId",
    "sc_channel", "sc_detail", "sc_imax", "sc_min", "sc_mt",
    "sc_country", "sc_language",
    # Hepsiburada
    "magaza",
    # Amazon
    "pd_rd_r", "pd_rd_w", "pd_rd_wg",
    "pf_rd_i", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t",
    "ie", "qid", "sr",
}

# Kısa yönlendirme domainleri — zaten redirect, temizlenemez
_KISA_DOMAIN = {"ty.gl", "hb.biz", "hb.gl", "sl.n11.com", "amzn.to", "amzn.eu"}


def link_temizle(url: str) -> str:
    """URL'den affiliate ve tracking parametrelerini temizler.
    Kısa URL'lere (ty.gl, hb.biz …) dokunmaz.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if any(k in parsed.netloc for k in _KISA_DOMAIN):
            return url          # kısa URL — redirect zinciri, değiştirme
        if not parsed.query:
            return url          # parametre yok
        params = parse_qs(parsed.query, keep_blank_values=True)
        temiz  = {k: v for k, v in params.items()
                  if k.lower() not in _TRACKING_PARAMS}
        yeni_query = urlencode(temiz, doseq=True)
        return urlunparse(parsed._replace(query=yeni_query))
    except Exception:
        return url

# ════════════════════════════════════════════════════════════════
# Metin temizleme
# ════════════════════════════════════════════════════════════════

def emoji_temizle(metin: str) -> str:
    if not metin:
        return ""
    return "".join(
        k for k in metin if unicodedata.category(k) not in ("So", "Sm", "Sk")
    ).strip()


def markdown_temizle(metin: str) -> str:
    if not metin:
        return metin
    metin = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', metin)
    metin = re.sub(r'_{1,2}([^_]+)_{1,2}',   r'\1', metin)
    metin = re.sub(r'`([^`]+)`',               r'\1', metin)
    metin = re.sub(r'~{1,2}([^~]+)~{1,2}',   r'\1', metin)
    metin = re.sub(r'\|{2}([^|]+)\|{2}',      r'\1', metin)
    return metin


def benzerlik_anahtari(metin: str) -> str:
    """Duplikat tespiti için deterministik MD5 anahtarı üretir."""
    urun = urun_adi_bul(metin) or ""
    _, yeni, _, _ = fiyat_bul(metin)
    ham = (urun + (yeni or "")).lower().replace(" ", "")
    kaynak = ham if len(ham) > 5 else re.sub(r"\s+", " ", metin.strip().lower())
    return hashlib.md5(kaynak.encode()).hexdigest()


# ════════════════════════════════════════════════════════════════
# Marka spam koruması
# ════════════════════════════════════════════════════════════════

_marka_gecmis: dict[str, list[float]] = {}


def _marka_gecmis_temizle() -> None:
    """FIX: Dict sınırsız büyümesin — 500 mağazayı geçince temizle."""
    if len(_marka_gecmis) <= 500:
        return
    simdi = datetime.now(timezone.utc).timestamp()
    eskiler = [
        k for k, v in _marka_gecmis.items()
        if not v or simdi - max(v) > config.MARKA_SPAM_SURE * 2
    ]
    for k in eskiler:
        del _marka_gecmis[k]


def marka_spam_kontrol(magaza: str) -> bool:
    """True dönerse bu mağaza saatte MARKA_SPAM_LIMIT'ten fazla göndermiş."""
    _marka_gecmis_temizle()
    simdi = datetime.now(timezone.utc).timestamp()
    listesi = _marka_gecmis.setdefault(magaza, [])
    _marka_gecmis[magaza] = [t for t in listesi if simdi - t < config.MARKA_SPAM_SURE]
    if len(_marka_gecmis[magaza]) >= config.MARKA_SPAM_LIMIT:
        return True
    _marka_gecmis[magaza].append(simdi)
    return False


# ════════════════════════════════════════════════════════════════
# İndirim oranı
# ════════════════════════════════════════════════════════════════

def indirim_oranini_bul(metin: str) -> int:
    if not metin:
        return 0
    ml = metin.lower()

    # 1. Açık kalıplar
    kaliplar = [
        r"-\s*%\s*(\d+)",
        r"indirim\s*[:\-]\s*-?\s*%\s*(\d+)",
        r"%\s*(\d+)\s*(?:indirim|off|discount|ucuz)",
        r"(\d+)\s*%\s*(?:indirim|off|discount|ucuz)",
        r"(?:indirim|off|discount)[^\d]*(\d+)\s*%",
    ]
    for kalip in kaliplar:
        degerler = [int(x) for x in re.findall(kalip, ml) if 1 <= int(x) <= 99]
        if degerler:
            return max(degerler)

    # 2. "X al Y öde"
    for al_s, ode_s in re.findall(r"(\d+)\s*al\s*(\d+)\s*(?:öde|ode)", ml):
        al, ode = int(al_s), int(ode_s)
        if al > ode > 0:
            ind = round((1 - ode / al) * 100)
            if 1 <= ind <= 99:
                return ind

    # 3. Linkleri çıkar, kalan %xx
    temiz = re.sub(r'https?://\S+', '', metin)
    degerler = [int(x) for x in re.findall(r"%(\d{1,2})\b", temiz) if 1 <= int(x) <= 99]
    if degerler:
        return max(degerler)

    # 4. "X₺ Kuponla Y₺" — gerçek oranı hesapla  (ör: 900₺ Kuponla 15.099₺)
    kupon_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+([\d.,]+)\s*₺", metin)
    for k_s, f_s in kupon_fmt:
        kv, fv = _parse(k_s), _parse(f_s)
        if kv > 0 and fv > 0 and fv > kv:
            oran = round(kv / (fv + kv) * 100)
            if kv >= config.KUPON_MIN_TL:
                return max(oran, config.MIN_INDIRIM)
            return max(oran, 1)

    # 4b. "X₺ Kuponla Adedi Y₺" — adet fiyatı + kupon (ör: 100₺ Kuponla Adedi 67₺)
    adedi_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+[Aa]dedi\s*([\d.,]+)\s*₺", metin)
    for k_s, a_s in adedi_fmt:
        kv, av = _parse(k_s), _parse(a_s)
        if kv > 0 and av > 0:
            normal = av + kv
            oran = round(kv / normal * 100)
            if 1 <= oran <= 99:
                return oran

    # 4c. "X TL'ye Düştü - Piyasası Y TL" — fiyat düşüşü
    duzeltme = re.findall(r"([\d.,]+)\s*tl.*?düştü.*?piyasa[^\d]*([\d.,]+)\s*tl", ml)
    for yeni_s, eski_s in duzeltme:
        yv, ev = _parse(yeni_s), _parse(eski_s)
        if ev > yv > 0:
            oran = round((ev - yv) / ev * 100)
            if 1 <= oran <= 99:
                return oran

    # 4d. Sepette indirim (miktar bilinmiyor)
    if re.search(r"sepette\s*[\d.,]+\s*tl|sepete\s*\d+\s*adet", ml):
        return 30

    # 4e. Kupon kodu varsa (ör: "final150 Kodu İle")
    if re.search(r"\b[A-Za-z0-9]{4,20}\s+[Kk]odu\b", metin):
        return config.MIN_INDIRIM

    # 5. Stok uyarısı + fiyat birlikteliği
    stok_kelime = {"stoklar eriyor", "son stok", "dip fiyat", "en düşük", "kaçmaz", "hemen yakala"}
    if any(k in ml for k in stok_kelime) and re.search(r"[\d.,]+\s*(?:tl|₺)", ml):
        return 50

    # 6. Tanınan mağaza linki
    if any(x in ml for x in ["hb.biz", "trendyol.com", "ty.gl", "amazon.com.tr", "n11.com", "sl.n11.com"]):
        return 20

    return 0


# ════════════════════════════════════════════════════════════════
# Fiyat
# ════════════════════════════════════════════════════════════════

def _parse(s: str) -> float:
    """Türkçe fiyat stringini float'a çevirir.
    '15.099' → 15099  |  '1.299,90' → 1299.90  |  '299,90' → 299.90"""
    try:
        s = s.strip()
        if "," in s and "." in s:
            # '1.299,90' → binler noktası + ondalık virgül
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # '299,90' → ondalık virgül
            s = s.replace(",", ".")
        elif re.search(r"^\d{1,3}(\.\d{3})+$", s):
            # '15.099' veya '1.015.099' → Türkçe binler ayırıcısı
            s = s.replace(".", "")
        return float(s)
    except Exception:
        return 0.0


def fiyat_bul(metin: str) -> tuple[str | None, str | None, float, float]:
    """(eski_str, yeni_str, eski_val, yeni_val) döndürür."""
    if not metin:
        return None, None, 0, 0

    # 1. 'X₺ Kuponla Y₺' → normal = X+Y, indirimli = Y
    kupon_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+([\d.,]+)\s*₺", metin)
    if kupon_fmt:
        kv = _parse(kupon_fmt[0][0])
        fv = _parse(kupon_fmt[0][1])
        if kv > 0 and fv > 0 and fv > kv:
            eski_v = fv + kv
            eski_s = f"{int(eski_v):,}".replace(",", ".")
            return eski_s, kupon_fmt[0][1], eski_v, fv

    # 1b. 'X₺ Kuponla Adedi Y₺' → normal = X+Y, indirimli = Y
    adedi_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+[Aa]dedi\s*([\d.,]+)\s*₺", metin)
    if adedi_fmt:
        kv = _parse(adedi_fmt[0][0])
        av = _parse(adedi_fmt[0][1])
        if kv > 0 and av > 0:
            eski_v = av + kv
            eski_s = f"{int(eski_v):,}".replace(",", ".")
            return eski_s, adedi_fmt[0][1], eski_v, av

    # 2. Etiketli format: "İndirimli Fiyat / Normal Fiyat"
    ind = re.findall(r"(?:indirimli\s*fiyat|sale\s*price)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.I)
    nor = re.findall(r"(?:normal\s*fiyat|liste\s*fiyat|piyasa\s*fiyat)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.I)
    if ind and nor:
        yv, ev = _parse(ind[0]), _parse(nor[0])
        if ev > yv > 0:
            return nor[0], ind[0], ev, yv

    # 3. "X TL'ye Düştü - Piyasası Y TL" → yeni=X, eski=Y
    ml = metin.lower()
    duzeltme = re.findall(r"([\d.,]+)\s*tl.*?düştü.*?piyasa[^\d]*([\d.,]+)\s*tl", ml)
    if duzeltme:
        yv, ev = _parse(duzeltme[0][0]), _parse(duzeltme[0][1])
        if ev > yv > 0:
            return duzeltme[0][1], duzeltme[0][0], ev, yv

    # 4. ₺ ve TL fiyatları — en yüksek=eski, en düşük=yeni
    bulunan = re.findall(r"₺\s*([\d.,]+)", metin) + re.findall(r"([\d.,]+)\s*(?:TL|tl|lira)", metin)
    degerler = [((_parse(f), f)) for f in bulunan if _parse(f) > 0]
    if len(degerler) >= 2:
        sirali = sorted(degerler, reverse=True)
        (ev, es), (yv, ys) = sirali[0], sirali[-1]
        if ev > yv:
            return es, ys, ev, yv
    elif len(degerler) == 1:
        return None, degerler[0][1], 0, degerler[0][0]

    return None, None, 0, 0


# ════════════════════════════════════════════════════════════════
# Mağaza / Kategori / Stok
# ════════════════════════════════════════════════════════════════

_MAGAZA_ESLEME = [
    ("Trendyol",    "trendyol"),
    ("Hepsiburada", "hepsiburada"),
    ("Amazon TR",   "amazon"),
    ("MediaMarkt",  "mediamarkt"),
    ("Teknosa",     "teknosa"),
    ("Gratis",      "gratis"),
    ("Boyner",      "boyner"),
    ("N11",         "n11.com"),
    ("Çiçeksepeti", "ciceksepeti"),
    ("Temu",        "temu.com"),
]


def magaza_bul(metin: str) -> str:
    ml = (metin or "").lower()
    for ad, anahtar in _MAGAZA_ESLEME:
        if anahtar in ml:
            return ad
    return "E-Ticaret"


def kategori_bul(metin: str) -> tuple[str, str, list[str]]:
    """(kat_adi, ikon, hashtag_listesi) döndürür."""
    ml = (metin or "").lower()
    for kat_adi, kat in config.KATEGORILER.items():
        if any(a in ml for a in kat["anahtar"]):
            return kat_adi, kat["ikon"], kat["hashtag"]
    return "genel", "🛍️", ["#Fırsat", "#İndirim"]


def stok_kritik_mi(metin: str) -> bool:
    ml = (metin or "").lower()
    return any(k in ml for k in ["stoklar eriyor", "son stok", "tükeniyor", "sınırlı stok"])


def indirim_turu(metin: str) -> str:
    """'marka' ya da 'urun' döndürür."""
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
    _ATLA = {"linkteki", "sepette", "kampanya", "devam ediyor", "firsata git",
              "fırsata git", "google'da", "karşılaştır", "stokta var", "hemen yakala"}
    for satir in (s.strip() for s in metin.split("\n") if s.strip()):
        if satir.startswith(("#", "@")) or "http" in satir:
            continue
        if any(k in satir.lower() for k in _ATLA):
            continue

        aday = satir
        aday = re.sub(r"\s+[\d.,]+\s*₺.*$", "", aday).strip()
        aday = re.sub(r"\s+[\d.,]+\s*(?:TL|tl|lira).*$", "", aday).strip()
        aday = re.sub(r"\s+%\d+.*$", "", aday).strip()

        temiz = emoji_temizle(aday)
        if len(temiz) >= 8 and not re.search(r"\d+%|%\d+", temiz):
            return temiz[:80]
    return None


# ── Ref / affiliate link temizleme ──────────────────────────────

_KISALTILMIS = {"ty.gl", "hb.biz", "hb.gl", "sl.n11.com", "amzn.to"}

_REF_PARAMS = {
    # UTM
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    # Genel affiliate / tracking
    "ref", "referral", "aff", "affiliate", "partner", "src", "source",
    "fbclid", "gclid", "msclkid", "yclid", "_ga", "trk", "mc_eid",
    # Amazon affiliate
    "tag", "linkcode", "linkid", "ref_",
    "pf_rd_p", "pf_rd_r", "pd_rd_r", "pd_rd_w", "pd_rd_wg",
    "pf_rd_s", "pf_rd_t", "pf_rd_i",
    # Trendyol tracking
    "boutiqueid", "merchantid", "sav", "pi", "filteredsearchvalues",
    # HepsiBurada
    "magaza",
    # N11
    "searchterm",
}


def link_temizle(url: str) -> str:
    """URL'den affiliate / UTM / ref parametrelerini temizler.
    Kısaltılmış linklere (ty.gl vb.) dokunmaz."""
    if not url:
        return url
    try:
        p = urlparse(url)
        if any(k in p.netloc for k in _KISALTILMIS):
            return url
        params = parse_qs(p.query, keep_blank_values=False)
        temiz = {k: v for k, v in params.items() if k.lower() not in _REF_PARAMS}
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(temiz, doseq=True), ""))
    except Exception:
        return url


def link_bul(metin: str, buton_linkleri: list[str] | None = None) -> str | None:
    oncelik = [
        "trendyol.com", "hepsiburada.com", "amazon.com.tr", "mediamarkt.com.tr",
        "teknosa.com", "ty.gl", "hb.gl", "n11.com", "ciceksepeti.com",
        "aliexpress.com", "sl.n11.com", "hb.biz",
    ]
    gizli = {"google.com", "t.me"}

    if buton_linkleri:
        for bl in buton_linkleri:
            if any(p in bl for p in oncelik):
                return link_temizle(bl)
        for bl in buton_linkleri:
            if not any(g in bl for g in gizli):
                return link_temizle(bl)

    if metin:
        linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
        for lnk in linkler:
            if any(p in lnk for p in oncelik):
                return link_temizle(lnk)
        for lnk in linkler:
            if not any(g in lnk for g in gizli):
                return link_temizle(lnk)
    return None


def kupon_bul(metin: str) -> str | None:
    for kalip in [
        r"kupon\s*[:\-]?\s*([A-Za-z0-9]{4,20})",
        r"indirim\s*kodu?\s*[:\-]?\s*([A-Za-z0-9]{4,20})",
        r"\b([A-Za-z0-9]{4,20})\s+[Kk]odu\b",   # "final150 Kodu" formatı
    ]:
        eslesme = re.findall(kalip, metin or "")
        if eslesme:
            return eslesme[0].upper()
    return None


def min_siparis_bul(metin: str) -> str | None:
    for kalip in [
        r"(\d+)\s*adet\s*al[ıi]mda",
        r"min(?:imum)?\s*(\d+)\s*(?:tl|adet)",
        r"(\d[\d.,]*)\s*tl\s*alışverişte",
    ]:
        eslesme = re.findall(kalip, metin or "", re.I)
        if eslesme:
            return eslesme[0]
    return None


# ════════════════════════════════════════════════════════════════
# Skor hesaplama
# ════════════════════════════════════════════════════════════════

def kalite_skoru(metin: str, indirim: int, buton_linkleri: list[str]) -> int:
    """0–100 arası kalite puanı."""
    s = 0
    if indirim >= 50:   s += 40
    elif indirim >= 30: s += 25
    else:               s += 10
    if link_bul(metin, buton_linkleri): s += 20
    e, y, _, _ = fiyat_bul(metin)
    s += 20 if (e and y) else (10 if y else 0)
    if urun_adi_bul(metin):   s += 15
    if stok_kritik_mi(metin): s += 5
    return s


def sahte_indirim_mi(metin: str, indirim: int) -> bool:
    if indirim < 75:
        return False
    ml = metin.lower()
    if any(m in ml for m in config.GUVENILIR_MARKALAR):
        return False
    return indirim >= 88


def firsat_skoru(metin: str, indirim: int, buton_linkleri: list[str]) -> float:
    """0.0–10.0 arası fırsat puanı."""
    s = 0.0
    if indirim >= 80:   s += 4.0
    elif indirim >= 70: s += 3.5
    elif indirim >= 60: s += 3.0
    elif indirim >= 50: s += 2.5
    elif indirim >= 30: s += 1.5
    else:               s += 0.5

    lnk = link_bul(metin, buton_linkleri)
    if lnk:
        s += 2.0 if any(x in lnk for x in ["trendyol.com", "amazon.com.tr", "hepsiburada.com"]) else 1.0

    e, y, ev, yv = fiyat_bul(metin)
    if e and y and ev > 0 and yv > 0:
        s += 2.0 + (0.3 if ev - yv >= 100 else 0)
    elif y:
        s += 1.0

    if urun_adi_bul(metin):   s += 1.0
    if stok_kritik_mi(metin): s += 0.2
    if sahte_indirim_mi(metin, indirim): s -= 2.0

    return round(max(0.0, min(10.0, s)), 1)


def firsat_yildiz(skor: float) -> str:
    if skor >= 9:   return "🌟🌟🌟🌟🌟"
    if skor >= 7.5: return "🌟🌟🌟🌟"
    if skor >= 6:   return "🌟🌟🌟"
    if skor >= 4:   return "🌟🌟"
    return "🌟"


def indirim_yildiz(indirim: int) -> str:
    if indirim >= 80: return "⭐⭐⭐⭐⭐"
    if indirim >= 70: return "⭐⭐⭐⭐"
    if indirim >= 60: return "⭐⭐⭐"
    return "⭐⭐"


# ════════════════════════════════════════════════════════════════
# Çok ürünlü mesaj bölücü
# ════════════════════════════════════════════════════════════════

def mesaj_bolum_ayir(metin: str) -> list[str]:
    """Tek mesajda birden fazla ürün varsa en fazla 2 bloğa böler.
    Önce boş satır, bulamazsa satır-başı ürün emojisiyle bölmeye çalışır.
    Her bloğa paylaşılan link/hashtag satırları eklenir.
    """
    if not metin:
        return [metin]

    # ── Yardımcı ────────────────────────────────────────────────
    def _paylasilan_mi(blok: str) -> bool:
        return all(
            s.startswith("#") or s.startswith("http") or s.startswith("🛒") or not s.strip()
            for s in blok.split("\n")
        )

    def _link_iceriyor_mu(blok: str) -> bool:
        return bool(re.search(r"https?://|hb\.biz|ty\.gl|sl\.n11", blok))

    # ── 1. Önce boş satırla bölmeyi dene ────────────────────────
    parcalar = [p.strip() for p in re.split(r"\n\s*\n", metin.strip()) if p.strip()]
    urun_bloklari = [p for p in parcalar if not _paylasilan_mi(p)]
    paylasilan    = [p for p in parcalar if _paylasilan_mi(p)]

    # ── 2. Boş satırla bölünemediyse emoji satır bölücü ─────────
    if len(urun_bloklari) <= 1:
        # Sadece 🔥 ve 🔻 ürün başlangıcı sayılır (⚡💰📦 fiyat satırları — aynı ürün)
        emoji_pat = re.compile(r"\n(?=[🔥🔻])")
        parcalar2 = emoji_pat.split(metin.strip())
        urun_bloklari2 = [p.strip() for p in parcalar2 if p.strip() and not _paylasilan_mi(p)]
        if len(urun_bloklari2) > 1:
            urun_bloklari = urun_bloklari2

    if len(urun_bloklari) <= 1:
        return [metin]

    # En fazla 2 ürün
    urun_bloklari = urun_bloklari[:2]

    paylasilan_metin = "\n\n".join(paylasilan)
    sonuc = []
    for blok in urun_bloklari:
        # Blokta link yoksa paylaşılan metinden link ekle
        if not _link_iceriyor_mu(blok) and paylasilan_metin:
            tam = (blok + "\n\n" + paylasilan_metin).strip()
        elif paylasilan_metin and not _link_iceriyor_mu(blok):
            tam = (blok + "\n\n" + paylasilan_metin).strip()
        else:
            tam = blok
            if paylasilan_metin:
                tam = (blok + "\n\n" + paylasilan_metin).strip()
        sonuc.append(tam)
    return sonuc

