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
# Metin temizleme
# ════════════════════════════════════════════════════════════════

def emoji_temizle(metin: str) -> str:
    """Emoji, sembol, variation selector ve zero-width karakterleri çıkarır."""
    if not metin:
        return ""
    # Variation selectors (U+FE00–U+FE0F), zero-width joiner, BOM vs.
    metin = re.sub(r"[\u200b-\u200f\u2060\ufe00-\ufe0f\ufeff]", "", metin)
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

    # 1. Açık yüzde kalıpları
    kaliplar = [
        r"-\s*%\s*(\d+)",
        r"⬇️?\s*[İi]ndirim\s*[:\-]\s*-?\s*%\s*(\d+)",
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

    # 3. "Piyasası / Normal / Piyasa Değeri X" + mevcut fiyat → oran hesapla
    piyasa = re.findall(r"(?:piyasa[sı]*|normal\s*fiyat|liste\s*fiyat)[^\d]*([\d.,]+)", ml)
    yeni_f = re.findall(r"([\d.,]+)\s*tl.*?(?:düştü|indirimli|fiyatı)", ml)
    if not yeni_f:
        # TL fiyatlarından en küçüğü yeni, büyüğü eski
        tl_fiyatlar = [_parse(x) for x in re.findall(r"([\d.,]+)\s*(?:tl|₺)", metin) if _parse(x) > 10]
        yeni_f_vals = sorted(tl_fiyatlar)
    else:
        yeni_f_vals = [_parse(x) for x in yeni_f]

    for p in piyasa:
        pv = _parse(p)
        if yeni_f_vals and pv > 0:
            yv = yeni_f_vals[0]
            if pv > yv > 0:
                ind = round((pv - yv) / pv * 100)
                if 1 <= ind <= 99:
                    return ind

    # 4. Linkleri temizle, kalan %xx
    temiz = re.sub(r'https?://\S+', '', metin)
    degerler = [int(x) for x in re.findall(r"%(\d{1,2})\b", temiz) if 1 <= int(x) <= 99]
    if degerler:
        return max(degerler)

    # 5. "X₺ Kuponla Y₺" — gerçek oran
    kupon_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+([\d.,]+)\s*₺", metin)
    for k_s, f_s in kupon_fmt:
        kv, fv = _parse(k_s), _parse(f_s)
        if kv > 0 and fv > 0 and fv > kv:
            oran = round(kv / (fv + kv) * 100)
            if kv >= config.KUPON_MIN_TL:
                return max(oran, config.MIN_INDIRIM)
            return max(oran, 1)

    # 6. "X Adet Alımda Y₺ Kuponla Adedi Z₺" → kupon/ürün bazlı
    adet_kupon = re.findall(r"(\d+)\s*adet\s*alımda\s*([\d.,]+)\s*₺\s*kuponla\s*adedi\s*([\d.,]+)\s*₺", ml)
    for adet_s, kupon_s, adet_fiyat_s in adet_kupon:
        kv = _parse(kupon_s)
        af = _parse(adet_fiyat_s)
        if af > 0:
            normal = af + kv / int(adet_s)
            ind = round(kv / int(adet_s) / normal * 100)
            if 1 <= ind <= 99:
                return max(ind, config.MIN_INDIRIM if kv >= config.KUPON_MIN_TL else 1)

    # 7. Sepette indirim
    if re.search(r"sepette\s*[\d.,]+\s*tl|sepete\s*\d+\s*adet", ml):
        return 30

    # 8. Stok uyarısı + fiyat
    stok_kelime = {"stoklar eriyor", "son stok", "dip fiyat", "en düşük", "kaçmaz", "hemen yakala"}
    if any(k in ml for k in stok_kelime) and re.search(r"[\d.,]+\s*(?:tl|₺)", ml):
        return 50

    # 9. Tanınan mağaza linki
    if any(x in ml for x in ["hb.biz", "trendyol.com", "ty.gl", "amazon.com.tr", "n11.com", "sl.n11.com"]):
        return 20

    return 0


# ════════════════════════════════════════════════════════════════
# Fiyat
# ════════════════════════════════════════════════════════════════

def _parse(s: str) -> float:
    try:
        s = s.strip().rstrip("+")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def fiyat_bul(metin: str) -> tuple[str | None, str | None, float, float]:
    """(eski_str, yeni_str, eski_val, yeni_val) döndürür."""
    if not metin:
        return None, None, 0, 0

    # 1. Etiketli format (İndirimli Fiyat / Normal Fiyat)
    ind = re.findall(r"(?:indirimli\s*fiyat|sale\s*price|⚡️?\s*[İi]ndirimli\s*[Ff]iyat)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.I)
    nor = re.findall(r"(?:normal\s*fiyat|liste\s*fiyat|piyasa[sı]*|💰\s*[Nn]ormal\s*[Ff]iyat)\s*[:\-]?\s*[₺$€]?\s*([\d.,]+)", metin, re.I)
    if ind and nor:
        yv, ev = _parse(ind[0]), _parse(nor[0])
        if ev > yv > 0:
            return nor[0], ind[0], ev, yv

    # 2. "X TL'ye Düştü" + "Piyasası Y TL"
    dustu = re.findall(r"([\d.,]+)\s*TL['\u2019]?ye\s*[Dd]üştü", metin)
    piyasa = re.findall(r"[Pp]iyasa[sı]*\s*([\d.,]+)", metin)
    if dustu and piyasa:
        yv, ev = _parse(dustu[0]), _parse(piyasa[0].rstrip("+"))
        if ev > yv > 0:
            return piyasa[0], dustu[0], ev, yv

    # 3. "X₺ Kuponla Y₺" → normal=X+Y, indirimli=Y
    kupon_fmt = re.findall(r"([\d.,]+)\s*₺\s*[Kk]upon\w*\s+([\d.,]+)\s*₺", metin)
    if kupon_fmt:
        kv, fv = _parse(kupon_fmt[0][0]), _parse(kupon_fmt[0][1])
        if kv > 0 and fv > 0:
            ev = fv + kv
            return f"{ev:.0f}", kupon_fmt[0][1], ev, fv

    # 4. "X Adet Alımda Y₺ Kuponla Adedi Z₺"
    adet_kupon = re.findall(r"(\d+)\s*[Aa]det\s*[Aa]lımda\s*([\d.,]+)\s*₺\s*[Kk]uponla\s*[Aa]dedi\s*([\d.,]+)\s*₺", metin)
    if adet_kupon:
        adet, kupon_s, adet_fiyat_s = adet_kupon[0]
        kv, af = _parse(kupon_s), _parse(adet_fiyat_s)
        normal_adet = af + kv / int(adet)
        return f"{normal_adet:.0f}", adet_fiyat_s, normal_adet, af

    # 5. ₺ ve TL genel
    bulunan = re.findall(r"₺\s*([\d.,]+)", metin) + re.findall(r"([\d.,]+)\s*(?:TL|tl|lira)", metin)
    # Küçük sayıları filtrele (adet, boyut vb.) — 10₺ altını atla
    degerler = [((_parse(f), f)) for f in bulunan if _parse(f) >= 10]
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

# Kısaltılmış / yönlendirme linklerinden mağaza tespiti
_LINK_MAGAZA = [
    ("Hepsiburada", ["hb.biz", "hb.gl", "hepsiburada"]),
    ("Trendyol",    ["ty.gl", "trendyol"]),
    ("Amazon TR",   ["amzn.to", "amazon"]),
    ("N11",         ["sl.n11.com", "n11.com"]),
    ("MediaMarkt",  ["mediamarkt"]),
    ("Teknosa",     ["teknosa"]),
    ("Gratis",      ["gratis"]),
    ("Çiçeksepeti", ["ciceksepeti"]),
    ("Temu",        ["temu.com"]),
]


def magaza_bul(metin: str, link: str | None = None) -> str:
    """Metinden veya link domain'inden mağaza adını çıkarır."""
    ml = (metin or "").lower()
    # Önce metinde mağaza adı geçiyor mu?
    for ad, anahtar in _MAGAZA_ESLEME:
        if anahtar in ml:
            return ad
    # Yoksa link'ten çıkar
    if link:
        ll = link.lower()
        for ad, anahtarlar in _LINK_MAGAZA:
            if any(k in ll for k in anahtarlar):
                return ad
    return "E-Ticaret"


def kategori_bul(metin: str) -> tuple[str, str, list[str]]:
    ml = (metin or "").lower()
    for kat_adi, kat in config.KATEGORILER.items():
        if any(a in ml for a in kat["anahtar"]):
            return kat_adi, kat["ikon"], kat["hashtag"]
    return "genel", "🛍️", ["#Fırsat", "#İndirim"]


def stok_kritik_mi(metin: str) -> bool:
    ml = (metin or "").lower()
    return any(k in ml for k in ["stoklar eriyor", "son stok", "tükeniyor", "sınırlı stok", "eRİYOR"])


def indirim_turu(metin: str) -> str:
    ml = (metin or "").lower()
    kaliplar = [
        r"\w+\s*(?:urunlerinde|markasinda|serisinde)\s*%\d+",
        r"tum\s*\w*\s*urunlerde",
        r"secili\s*\w*\s*urunlerde",
    ]
    return "marka" if any(re.search(k, ml) for k in kaliplar) else "urun"


# Kampanya/promo açıklaması olduğuna işaret eden kalıplar — ürün adı sayılmaz
_KAMPANYA_KALIP = re.compile(
    r"(sepette|kampanya|al\s*\d+\s*öde|indirim\s*devam|linkteki|tüm\s*\w+\s*ürünler"
    r"|hepsiburada\s*satıcılı|markasında|ürünlerde\s*%|ürünlerinde)",
    re.I
)


# Ürün başlık emoji'leri
_URUN_BAS = re.compile(r"^[🔥🔻📦👚🎯💡🛍✅⚡🎁⭐🆕💎🏆]", re.UNICODE)


def urun_adi_bul(metin: str) -> str | None:
    """Mesajdan ürün adını çıkarır.
    Öncelik: ürün başlık emoji'si + ≥10 karakter + harf içeren satır."""
    if not metin:
        return None

    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]

    def _temizle(satir: str) -> str:
        """Fiyat / yüzde / kupon kodu / link kısımlarını ayıkla."""
        # URL'leri çıkar
        s = re.sub(r"https?://\S+", "", satir)
        # Zero-width karakterler
        s = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", s)
        # Fiyat aralıkları: "1.000₺ - 1.300₺ arasında"
        s = re.sub(r"[\d.,]+\s*₺\s*[-–—]\s*[\d.,]+\s*₺\s*aras[ıi]nda\b", "", s, flags=re.I)
        s = re.sub(r"[\d.,]+\s*(?:TL|tl)\s*[-–—]\s*[\d.,]+\s*(?:TL|tl)\s*aras[ıi]nda\b", "", s, flags=re.I)
        # "%X'a varan indirim var"
        s = re.sub(r"%\s*\d+\s*['\u2019]?\s*[aeıi]\s*varan\s*indirim\s*var\b", "", s, flags=re.I)
        s = re.sub(r"varan\s*indirim\s*var\b", "", s, flags=re.I)
        s = re.sub(r"\bindirim\s+var\b", "", s, flags=re.I)
        # Tek fiyat: 137₺, ₺1.599,99, 3.099TL, 650 TL
        s = re.sub(r"[\d.,]+\s*₺|₺\s*[\d.,]+|[\d.,]+\s*(?:TL|tl|lira)", "", s)
        # Yüzde
        s = re.sub(r"%\s*\d+|\d+\s*%", "", s)
        # "X Adet Alımda" / "X Kuponla" / "kodu ile"
        s = re.sub(r"\b\d+\s*[Aa]det\s*[Aa]l[ıi]mda\b.*", "", s)
        s = re.sub(r"\b[A-Za-z0-9]{4,20}\s*[Kk]odu?\s*(?:ile|İle).*", "", s, flags=re.I)
        s = re.sub(r"\b[Kk]uponla\b.*", "", s)
        s = re.sub(r"\b\d+\s*[Aa]l\s*\d+\s*[ÖöOo]de\b", "", s)
        # Bağlaçlar / filler
        s = re.sub(r"\b(?:yerine|ye geliyor|geliyor|düştü|fiyatı|piyasası|piyasa)\b", "", s, flags=re.I)
        # Emojileri sök, fazla boşluk + son nokta/tire'leri at
        s = emoji_temizle(s)
        s = re.sub(r"\s+", " ", s).strip(" -–—,.|").strip()
        # Sondaki tek başına "var" / "ve" gibi takıları sil
        s = re.sub(r"\s+(?:var|ve|ile)\s*$", "", s, flags=re.I).strip()
        return s

    # Öncelik 1: ürün başlık emoji'siyle başlayan satırlar (en ürünsel)
    for satir in satirlar:
        if not _URUN_BAS.match(satir):
            continue
        if satir.startswith(("#", "@")) or "http" in satir:
            continue
        if "#" in satir:                # hashtag içeren satır ürün adı sayılmaz
            continue
        if _KAMPANYA_KALIP.search(satir):
            continue
        temiz = _temizle(satir)
        if len(temiz) >= 10 and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", temiz):
            return temiz[:80]

    # Öncelik 2: emoji yok ama temiz uzun ürün adı (fiyatsız)
    for satir in satirlar:
        if "#" in satir:
            continue
        temiz = emoji_temizle(satir)
        if (
            len(temiz) >= 8
            and not satir.startswith(("#", "@", "👉", "✨", "🌟", "🔍", "✅", "💳", "💰", "⚡"))
            and "http" not in satir
            and "TL" not in satir
            and "₺" not in satir
            and not re.search(r"\d+%|%\d+", satir)
            and not _KAMPANYA_KALIP.search(satir)
        ):
            return temiz[:80]

    # Öncelik 3: fiyat içeren satır → fiyatı çıkarıp dene
    for satir in satirlar:
        if "₺" not in satir and "TL" not in satir:
            continue
        if "#" in satir:
            continue
        if _KAMPANYA_KALIP.search(satir):
            continue
        temiz = _temizle(satir)
        if (
            len(temiz) >= 8
            and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", temiz)
            and not temiz.lower().startswith(("kupon", "indirim", "sepette", "hepsipara", "premiuma"))
        ):
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
    "campaign", "creative", "channel", "campaign_id",
    # Amazon affiliate
    "tag", "linkcode", "linkid", "ref_", "ascsubtag", "smid",
    "pf_rd_p", "pf_rd_r", "pd_rd_r", "pd_rd_w", "pd_rd_wg",
    "pf_rd_s", "pf_rd_t", "pf_rd_i",
    # Trendyol tracking
    "boutiqueid", "merchantid", "sav", "pi", "filteredsearchvalues",
    # HepsiBurada
    "magaza", "wt_mc",
    # N11
    "searchterm",
}


def link_temizle(url: str) -> str:
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
        "aliexpress.com", "sl.n11.com", "hb.biz", "amzn.to",
    ]
    # Reddedilecekler — arama motorları + Telegram
    gizli = ("google.com/search", "bing.com/search", "duckduckgo.com", "t.me/")

    def _kabul(url: str) -> bool:
        ul = url.lower()
        if any(g in ul for g in gizli):
            return False
        return True

    if buton_linkleri:
        for bl in buton_linkleri:
            if _kabul(bl) and any(p in bl.lower() for p in oncelik):
                return link_temizle(bl)
        for bl in buton_linkleri:
            if _kabul(bl):
                return link_temizle(bl)

    if metin:
        linkler = re.findall(r'https?://[^\s\)\"\<\]\,]+', metin)
        for lnk in linkler:
            if _kabul(lnk) and any(p in lnk.lower() for p in oncelik):
                return link_temizle(lnk)
        for lnk in linkler:
            if _kabul(lnk):
                return link_temizle(lnk)
    return None


def kupon_bul(metin: str) -> str | None:
    kaliplar = [
        r"kupon\s*[:\-]?\s*([A-Z0-9]{4,20})",
        r"indirim\s*kodu?\s*[:\-]?\s*([A-Z0-9]{4,20})",
        r"([A-Z0-9]{4,20})\s*[Kk]odu?\s*(?:ile|İle|kullan)",
        r"([A-Z0-9]{4,20})\s*[Kk]upon",
    ]
    for kalip in kaliplar:
        eslesme = re.findall(kalip, metin or "", re.I)
        if eslesme:
            kod = eslesme[0].upper()
            # Yaygın yanlış eşleşmeleri filtrele
            if kod not in {"ADET", "KODU", "INDIRIM", "KUPON", "FIYAT"}:
                return kod
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
    s = 0
    if indirim >= 50:   s += 40
    elif indirim >= 30: s += 25
    else:               s += 10
    if link_bul(metin, buton_linkleri): s += 20
    e, y, _, _ = fiyat_bul(metin)
    s += 20 if (e and y) else (10 if y else 0)
    # Marka kampanyası ("%40'a varan", "tüm ürünlerde indirim") — fiyat eksikse bile değerli
    if indirim_turu(metin) == "marka" or _MARKA_KAMPANYA_KALIP.search(metin or ""):
        s += 10
    if urun_adi_bul(metin):   s += 15
    if stok_kritik_mi(metin): s += 5
    return s


# Marka kampanyası kalıpları — "%X varan indirim", "tüm ürünlerde", "seçili ürünlerde"
_MARKA_KAMPANYA_KALIP = re.compile(
    r"%\s*\d+\s*['\u2019]?\s*[aeıi]\s*varan|"
    r"varan\s*indirim|"
    r"tüm\s+ürünlerde|"
    r"seçili\s+ürünlerde|"
    r"sepette\s*%",
    re.I,
)


def sahte_indirim_mi(metin: str, indirim: int) -> bool:
    """Sahte indirim filtresi gevşetildi:
    - %85 altı → güvenli kabul
    - Güvenilir marka varsa → güvenli
    - Açıkça eski+yeni fiyat varsa → güvenli (hesaplanabilir)
    - Aksi halde %90+ olunca işaretle"""
    if indirim < 85:
        return False
    ml = (metin or "").lower()
    if any(m in ml for m in config.GUVENILIR_MARKALAR):
        return False
    # Hem eski hem yeni fiyat varsa, indirim doğrulanabilir → güvenli
    e, y, _, _ = fiyat_bul(metin)
    if e and y:
        return False
    return indirim >= 90


def firsat_skoru(metin: str, indirim: int, buton_linkleri: list[str]) -> float:
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

# 🔻 satır başı → kesin ürün ayırıcısı
_YENI_URUN = re.compile(r"^🔻", re.UNICODE)


def _paylasilan_mi(blok: str) -> bool:
    satirlar = [s.strip() for s in blok.split("\n") if s.strip()]
    if not satirlar:
        return True
    return all(
        s.startswith("#") or s.startswith("http")
        or s.startswith("🛒") or s.startswith("👉")
        or s.startswith("✨") or s.startswith("🔍")
        or s.lower().startswith(("ürüne git", "fırsata git"))
        for s in satirlar
    )


def _urun_paragrafi_mi(paragraf: str) -> bool:
    """Paragraf gerçek bir ürün bilgisi mi içeriyor?"""
    p = paragraf.strip()
    if len(p) < 15:
        return False
    fiyat_var = bool(
        re.search(r"[\d.,]+\s*(?:tl|₺|lira)", p, re.I)
        or re.search(r"%\s*\d+|\d+\s*%", p)
    )
    if not fiyat_var:
        return False
    ilk_satir = p.split("\n")[0].strip()
    if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", ilk_satir):
        return False
    # Sadece kampanya açıklaması ise (somut fiyat yok, sadece %X varan / tüm ürünlerde)
    # → ürün değil
    somut_fiyat = bool(re.search(r"[\d.,]+\s*(?:tl|₺|lira)\b", p, re.I))
    if not somut_fiyat:
        # Sadece % var. Eğer "varan / tüm / seçili" gibi kampanya kelimeleri varsa, ürün değil
        if re.search(r"varan|tüm\s+ürün|seçili\s+ürün|sepette\s+%|sepete\s+%", p, re.I):
            return False
    return True


def _paragraf_ici_bol(paragraf: str) -> list[str]:
    """🔻 ile başlayan satırları ayrı ürün bloğu yapar."""
    satirlar = paragraf.split("\n")
    bloklar, mevcut = [], []
    for satir in satirlar:
        if _YENI_URUN.match(satir.strip()) and mevcut:
            bloklar.append("\n".join(mevcut))
            mevcut = [satir]
        else:
            mevcut.append(satir)
    if mevcut:
        bloklar.append("\n".join(mevcut))
    return bloklar


def mesaj_bolum_ayir(metin: str) -> list[str]:
    """Tek mesajda birden fazla ürün varsa ayrı bloklara böler (max 2).
    Paylaşılan link/hashtag satırları her bloğa eklenir.
    Tek ürünlüyse [metin] döner.

    Kural: "Ne ürün ne paylaşılan" paragraf (örn. salt ürün başlığı)
    bir sonraki ürün bloğunun BAŞINA eklenir (önceki değil)."""
    if not metin or len(metin) < 30:
        return [metin]

    parcalar = [p.strip() for p in re.split(r"\n\s*\n", metin.strip()) if p.strip()]

    # Paragraf içi 🔻 ayırıcısını uygula
    genisletilmis = []
    for p in parcalar:
        genisletilmis.extend(_paragraf_ici_bol(p))

    # İki geçişli yaklaşım:
    # 1) Tüm bloklara tip ata
    # 2) "neither" tipindekileri sonraki ürün başlığı say, yoksa paylaşılan
    tipler = []   # ("urun", "paylasilan", "neither")
    for p in genisletilmis:
        if _paylasilan_mi(p):
            tipler.append("paylasilan")
        elif _urun_paragrafi_mi(p):
            tipler.append("urun")
        else:
            tipler.append("neither")

    urun_bloklari: list[str] = []
    paylasilan: list[str] = []
    bekleyen_baslik: str = ""   # Henüz ürünle eşleşmemiş "neither" paragraf

    for p, tip in zip(genisletilmis, tipler):
        if tip == "paylasilan":
            paylasilan.append(p)
        elif tip == "urun":
            if bekleyen_baslik:
                urun_bloklari.append(bekleyen_baslik + "\n\n" + p)
                bekleyen_baslik = ""
            else:
                urun_bloklari.append(p)
        else:  # neither
            # Eğer arkada bir ürün bloğu yoksa → bu sonraki ürünün başlığı
            # Eğer varsa → mevcut bloğun açıklaması olabilir
            if not urun_bloklari or bekleyen_baslik:
                bekleyen_baslik = (bekleyen_baslik + "\n\n" + p).strip() if bekleyen_baslik else p
            else:
                # Önceki ürüne eklemek mantıksız (başlık değil, açıklama)
                # → paylaşılan say
                paylasilan.append(p)

    # Artakalan başlık varsa son ürüne ekle
    if bekleyen_baslik and urun_bloklari:
        urun_bloklari[-1] = urun_bloklari[-1] + "\n\n" + bekleyen_baslik
    elif bekleyen_baslik:
        # Hiç ürün bulunamadı, bekleyeni paylaşılana koy (orijinali kaybetmemek için)
        paylasilan.append(bekleyen_baslik)

    if len(urun_bloklari) <= 1:
        return [metin]

    paylasilan_metin = "\n\n".join(paylasilan)
    sonuc = []
    for blok in urun_bloklari[:2]:
        tam = (blok + "\n\n" + paylasilan_metin).strip() if paylasilan_metin else blok
        sonuc.append(tam)
    return sonuc
