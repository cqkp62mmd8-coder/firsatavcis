"""
Mesaj analizi: indirim oranı, fiyat, mağaza, kategori, kalite & fırsat skoru.
Saf fonksiyonlar — dış bağımlılık yok (config hariç).
"""
import hashlib
import re
import unicodedata
import functools
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
        adet_n = int(adet_s) if adet_s.isdigit() and int(adet_s) > 0 else 1
        if af > 0:
            normal = af + kv / adet_n
            ind = round(kv / adet_n / normal * 100)
            if 1 <= ind <= 99:
                return max(ind, config.MIN_INDIRIM if kv >= config.KUPON_MIN_TL else 1)

    # v23.23 — İNDİRİM UYDURAN KURALLAR KALDIRILDI.
    # Eskiden aciliyet kelimesi ("stoklar eriyor", "kaçmaz") + fiyat varsa
    # sabit %50, sepette indirim varsa %30, tanınan mağaza linki varsa %20
    # UYDURULUYORDU. Bu, gerçek indirim olmayan ürünlere sahte oran basıyordu
    # (canlıda çok sayıda ürün yanlış %50 gösteriyordu). Artık indirim
    # SADECE metinde açıkça yazılı veya iki fiyattan HESAPLANABİLİR ise verilir.
    # Oran bulunamazsa 0 döner → şablon "FIRSAT ÜRÜNÜ" başlığı kullanır.

    return 0

    return 0


# ════════════════════════════════════════════════════════════════
# Fiyat
# ════════════════════════════════════════════════════════════════

def _parse(s: str) -> float:
    """Türkçe sayı formatını float'a çevirir.

    Kurallar:
      • "1.499,00" → 1499.0   (TR: . binlik, , ondalık)
      • "299,90"   → 299.9
      • "15.099"   → 15099.0  (TR binlik — ondalıkta 3 hane olmaz)
      • "15.99"    → 15.99    (ondalık — 2 hane)
      • "1.499"    → 1499.0   (3 hane → binlik)
    """
    try:
        s = s.strip().rstrip("+")
        if "," in s and "." in s:
            # TR: nokta binlik, virgül ondalık
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # Sadece virgül → TR ondalık
            s = s.replace(",", ".")
        elif "." in s:
            # Sadece nokta → ambiguous. 3 haneli sonek varsa binlik, değilse ondalık.
            # "15.099" → 3 haneli → binlik → 15099
            # "15.99"  → 2 haneli → ondalık → 15.99
            son_nokta = s.rfind(".")
            kalan = s[son_nokta + 1:]
            if len(kalan) == 3:
                s = s.replace(".", "")
        return float(s)
    except Exception:
        return 0.0


def fiyat_bul(metin: str) -> tuple[str | None, str | None, float, float]:
    """(eski_str, yeni_str, eski_val, yeni_val) döndürür."""
    if not metin:
        return None, None, 0, 0

    # v23.17 — KUPON DEĞERİ TEMİZLİĞİ: "Sepette 100 TL indirim", "100 TL kupon"
    # gibi ifadelerdeki sayı bir İNDİRİM MİKTARIDIR, ürün fiyatı DEĞİL.
    # ÖNEMLİ: kalıplar satır-içi (\n GEÇMEZ) — yoksa fiyat satırı + sonraki
    # "kupon" kelimesi birlikte silinip gerçek fiyat kayboluyordu.
    _kupon_deger_kaliplari = [
        r"sepette[ \t]+[\d.,]+[ \t]*TL",
        r"(?:indirim|kupon|hediye)[ \t]*[:\-]?[ \t]*[\d.,]+[ \t]*TL",
        r"[\d.,]+[ \t]*TL['\u2019]?[ \t]*(?:luk|lik|lık)?[ \t]*(?:indirim|kupon|hediye)",
        r"[\d.,]+[ \t]*/[ \t]*[\d.,]+[ \t]*TL",   # "5000/500TL" indirim mekaniği
    ]
    temiz = metin
    for kp in _kupon_deger_kaliplari:
        temiz = re.sub(kp, " ", temiz, flags=re.I)
    metin = temiz

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
        adet_n = int(adet) if adet.isdigit() and int(adet) > 0 else 1
        normal_adet = af + kv / adet_n
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
    """ML-only hiyerarşik kategori tespiti.

    Mantık:
      • ML modelinden 'ana:alt' formatı tahmin al
      • Yüksek güven (>= 0.35) → ML sonucu kullan
      • Düşük güven → 'genel' kategorisi (belirsiz kuyruğa eklenir)

    Döner: (ana_kategori, ikon, hashtag_listesi)

    Not: Tam tahmin sonucu (ana:alt) için kategori_bul_tam() kullanın."""
    if not metin:
        return "genel", "🛍️", ["#Fırsat", "#İndirim"]

    try:
        from utils import ml_kategori
        from utils.ml_kategoriler import KATEGORI_AGAC

        tam_kat, guven = ml_kategori.tahmin(metin)
        if not tam_kat or tam_kat == "genel":
            return "genel", "🛍️", ["#Fırsat", "#İndirim"]

        # Hiyerarşik formatı parse et
        ana = tam_kat.split(":", 1)[0]

        # v22.7 Sistem 2: Güven eşiği config'ten. Düşük güvende YANLIŞ kategori
        # basmaktansa 'genel' (kategorisiz) paylaş — yanlış kategori hiç olmasın.
        import config as _cfg
        _esik = _cfg.KATEGORI_GUVEN_ESIK / 100.0
        if guven < _esik:
            try:
                ml_kategori.belirsiz_kaydet(metin, tam_kat, guven)
            except Exception:
                pass
            return "genel", "🛍️", ["#Fırsat", "#İndirim"]

        if ana not in KATEGORI_AGAC:
            return "genel", "🛍️", ["#Fırsat", "#İndirim"]

        bilgi = KATEGORI_AGAC[ana]
        return ana, bilgi["ikon"], bilgi["hashtag"]

    except Exception as e:
        # ML modülü yoksa veya hata varsa
        try:
            from utils.log import log
            log("UYARI", f"ML kategori hata: {e}")
        except Exception:
            pass
        return "genel", "🛍️", ["#Fırsat", "#İndirim"]


def kategori_bul_tam(metin: str) -> tuple[str, str, float]:
    """Tam hiyerarşik kategori tahmini.
    Döner: (ana_kategori, alt_kategori, güven_skoru)
    Alt yoksa veya genel ise alt='' döner."""
    if not metin:
        return "genel", "", 0.0
    try:
        from utils import ml_kategori
        return ml_kategori.tahmin_hiyerarsik(metin)
    except Exception:
        return "genel", "", 0.0


def stok_kritik_mi(metin: str) -> bool:
    ml = (metin or "").lower()
    return any(k in ml for k in ["stoklar eriyor", "son stok", "tükeniyor", "sınırlı stok", "eRİYOR"])


def indirim_turu(metin: str) -> str:
    """'marka' (geniş kampanya) ya da 'urun' (tek ürün) döndürür."""
    ml = (metin or "").lower()
    # Türkçe karakterli de ASCII'li de yakalansın
    kaliplar = [
        r"\b\w+\s*(?:ürünlerinde|urunlerinde|markasında|markasinda|serisinde|kategorisinde)\b",
        r"\btüm\s*\w*\s*ürünlerde\b", r"\btum\s*\w*\s*urunlerde\b",
        r"\bseçili\s*\w*\s*ürünlerde\b", r"\bsecili\s*\w*\s*urunlerde\b",
        r"\bsepette\s*%",
        r"%\s*\d+\s*['\u2019]?\s*[aeıi]\s*varan",      # "%60'a varan"
        r"\b\w+\s+markasında\s+%",
    ]
    return "marka" if any(re.search(k, ml) for k in kaliplar) else "urun"


# Kampanya/promo açıklaması olduğuna işaret eden kalıplar — ürün adı sayılmaz
_KAMPANYA_KALIP = re.compile(
    # NOT: "sepette" sadece KAMPANYA bağlamında eşleşmeli:
    #   ✓ "Sepette %20 indirim" → kampanya
    #   ✓ "Sepette ek indirim"  → kampanya
    #   ✗ "Sepette 228 TL"      → gerçek fiyat (eşleşmemeli)
    r"(sepette\s*(?:%|ek|ekstra|kampanya|indirim)|kampanya|al\s*\d+\s*öde|indirim\s*devam|linkteki|tüm\s*\w+\s*ürünler"
    r"|hepsiburada\s*satıcılı|markasında|ürünlerde\s*%|ürünlerinde)",
    re.I
)


# Ürün başlık emoji'leri
_URUN_BAS = re.compile(r"^[🔥🔻📦👚🎯💡🛍✅⚡🎁⭐🆕💎🏆]", re.UNICODE)


# ═══════════════════════════════════════════════════════════════
# v22.2 — P3: MESAJ-BAZLI ÖNBELLEK
# Aynı mesaj birkaç fonksiyon tarafından paralel çağrılıyor olabilir
# (urun_adi_bul, kategori_bul, kategori_bul_tam). Mesajın hash'iyle
# sonuçları cache'le — aynı mesaj için tek hesap.
# ═══════════════════════════════════════════════════════════════

_mesaj_cache: dict = {}
_MESAJ_CACHE_MAX = 1024


def _mesaj_anahtar(metin: str, fonk_adi: str) -> tuple:
    """Mesaj-fonk anahtarı. İlk 300 karakter yeter (çoğu mesaj kısa)."""
    return (fonk_adi, (metin or "")[:300])


def _cache_al(metin: str, fonk_adi: str):
    """Cache'ten al, yoksa None."""
    return _mesaj_cache.get(_mesaj_anahtar(metin, fonk_adi))


def _cache_koy(metin: str, fonk_adi: str, sonuc) -> None:
    """Cache'e ekle, FIFO eviction."""
    if len(_mesaj_cache) >= _MESAJ_CACHE_MAX:
        # En eski 128'i at
        for k in list(_mesaj_cache.keys())[:128]:
            del _mesaj_cache[k]
    _mesaj_cache[_mesaj_anahtar(metin, fonk_adi)] = sonuc


def _ilk_satir_urun_adi(metin: str) -> str | None:
    """Mesajın ilk satırından ürün adını çıkar (📦 işareti ve gürültü temiz).

    v23.8 — Kaynak kanallar ürün adını ilk satıra koyar. Bu satır yeterince
    uzun + ürün adı niteliğindeyse (fiyat/indirim satırı değilse) döndürülür.
    """
    if not metin:
        return None
    ilk = metin.split("\n", 1)[0].strip()
    # Baştaki emoji/işaretleri temizle (📦 🔥 ⚡ vb.)
    ilk = re.sub(r"^[\W_]*(📦|🛍|🔥|⚡|🎯|🟢|💰|🆕|✨|�run)?\s*", "", ilk).strip()
    ilk = re.sub(r"^[^\w]+", "", ilk).strip()
    if len(ilk) < 8:
        return None
    # Fiyat/indirim/stok satırıysa ürün adı değil
    low = ilk.replace("İ","i").replace("I","ı").lower()
    if any(x in low for x in ["indirimli fiyat", "normal fiyat", "stokta",
                               "indirim:", "fiyat:", "google'da", "karşılaştır"]):
        return None
    # v23.8 — Slogan/CTA satırı ürün adı değil ("Stoklar ERİYOR hemen yakala")
    _slogan_kelime = ["eriyor", "yakala", "kaçırma", "kacirma", "acele",
                      "tükeniyor", "tukeniyor", "son fırsat", "son firsat",
                      "hemen al", "kaçmaz", "bitiyor", "stoklar"]
    if any(x in low for x in _slogan_kelime):
        return None
    # Sadece rakam/sembol ise değil
    if not re.search(r"[a-zçğıöşü]{3,}", low):
        return None
    # "Google'da Karşılaştır #İşbirliği" gibi kuyrukları kes
    ilk = re.split(r"\s*🔍|\s*#İşbirliği|\s*Google'da", ilk)[0].strip()
    # Çok uzunsa makul yere kadar kısalt (ilk ~12 kelime yeter)
    kelimeler = ilk.split()
    if len(kelimeler) > 14:
        ilk = " ".join(kelimeler[:14])
    return ilk if len(ilk) >= 8 else None


def urun_adi_bul(metin: str) -> str | None:
    """Mesajdan ürün adını çıkarır. v22.2: cache eklendi (P3).

    BİRİNCİL: öğrenen model (utils.urun_taniyici) — her kelimeyi
    ÜRÜN/FILLER olarak sınıflandırır, slogan/dolgu cümlelerini eler.
    YEDEK: model yüklenemezse aşağıdaki yapısal yöntem devreye girer.
    """
    if not metin:
        return None
    # Cache kontrol
    onbellek = _cache_al(metin, "urun_adi")
    if onbellek is not None:
        # onbellek (None,) tuple olarak saklanırsa "yok" demek
        return onbellek if onbellek != "__NONE__" else None

    sonuc = _urun_adi_bul_hesapla(metin)

    # v23.8 — İLK SATIR ÖNCELİĞİ: Kaynak kanallar ürün adını HER ZAMAN ilk
    # satıra (📦 ...) koyar. ML/yapısal yöntem uzun virgüllü adlarda bazen
    # ortadan kopuk parça çıkarıyor ("Apple iPad: ... — Gümüş" → "Gün Süren
    # Pil Ömrü Gümüş"). İlk satır temiz bir ürün adıysa onu tercih et.
    try:
        ilk_satir = _ilk_satir_urun_adi(metin)
        if ilk_satir:
            if not sonuc:
                sonuc = ilk_satir
            elif sonuc != ilk_satir:
                _il = ilk_satir.replace("İ","i").replace("I","ı").lower()
                _so = sonuc.replace("İ","i").replace("I","ı").lower()
                # v23.20 — İlk satır temizken ham'ı reddet eğer ham:
                #  (a) ilk satırın başıyla örtüşmüyor (kopuk parça), VEYA
                #  (b) fiyat/satış kelimeleri içeriyor (fiyat satırına taşmış),
                #      örn "...ye Düştü Piyasası", "...TL'ye", VEYA
                #  (c) ilk satırdan belirgin uzun (kelime sayısı +3) → taşma
                _fiyat_kelime = ("düştü", "dustu", "piyasası", "piyasasi",
                                 "indirimli", "normal fiyat", " tl", "'ye", "ye düştü")
                _tasma = len(_so.split()) > len(_il.split()) + 2
                _fiyat_bulasmis = any(fk in _so for fk in _fiyat_kelime)
                if (not _il.startswith(_so[:12])) or _fiyat_bulasmis or _tasma:
                    sonuc = ilk_satir
    except Exception:
        pass

    # v23.0 — TEK MERKEZİ KAPI: ML/yapısal sonuç da buradan geçer.
    # "Amazon", "İndirimli Fiyat" gibi çöp burada kesinlikle elenir.
    if sonuc is not None:
        try:
            from services.urun_kapisi import gecerli_urun_adi
            sonuc = gecerli_urun_adi(sonuc, metin)
        except Exception:
            pass
    _cache_koy(metin, "urun_adi", sonuc if sonuc is not None else "__NONE__")
    return sonuc


def _urun_adi_bul_hesapla(metin: str) -> str | None:
    """urun_adi_bul'un asıl gövdesi (cache MISS yolu).

    v22.9 — Sistem 1: 3-KATMAN OYLAMA.
    Üç bağımsız yöntem ürün adı çıkarır, sonuçlar karşılaştırılır:
      1. ML (urun_taniyici) — öğrenen sınıflandırıcı
      2. Yapısal — regex/konum tabanlı
      3. Sözlük teyidi — çıkan adın kelimeleri sözlükte ürün kelimesi mi
    En güvenilir sonuç seçilir. Hiçbiri makul değilse None.
    """
    if not metin:
        return None

    temiz_metin = _karsilastir_ctasi_temizle(metin)

    # Katman 1: ML
    ml_ad = None
    try:
        from utils import urun_taniyici
        aday = urun_taniyici.urun_adi_cikar(temiz_metin)
        if aday and _urun_adi_makul(aday):
            ml_ad = _ad_son_temizlik(aday)
    except Exception:
        pass

    # Katman 2: Yapısal
    yapisal_ad = None
    aday2 = _urun_adi_bul_yapisal(temiz_metin)
    if aday2 and _urun_adi_makul(aday2):
        yapisal_ad = _ad_son_temizlik(aday2)

    # Karar mantığı (oylama):
    # a) İkisi de aynı/çok benzer → en güvenilir, direkt döndür
    if ml_ad and yapisal_ad:
        if ml_ad.lower() == yapisal_ad.lower():
            return ml_ad
        # Biri diğerini içeriyorsa, daha uzun olan (daha bilgili) kazanır
        if ml_ad.lower() in yapisal_ad.lower():
            return yapisal_ad
        if yapisal_ad.lower() in ml_ad.lower():
            return ml_ad
        # Çelişki → sözlük hakemliği: hangisinin kelimeleri sözlükte daha çok
        secim = _sozluk_hakem(ml_ad, yapisal_ad)
        return secim or ml_ad   # hakem kararsızsa ML'e güven

    # b) Sadece biri sonuç verdi
    if ml_ad:
        return ml_ad
    if yapisal_ad:
        return yapisal_ad
    return None


def _sozluk_hakem(ad1: str, ad2: str) -> str | None:
    """İki aday ürün adından, kelimeleri sözlükte daha çok 'ürün kelimesi'
    olarak bilineni seç. Sözlük yoksa/eşitse None."""
    try:
        from utils import sozluk
        def skor(ad: str) -> int:
            return sum(1 for k in ad.split() if sozluk.urun_kelimesi_mi(k))
        s1, s2 = skor(ad1), skor(ad2)
        if s1 > s2:
            return ad1
        if s2 > s1:
            return ad2
    except Exception:
        pass
    return None


def _ad_son_temizlik(ad: str) -> str:
    """Ürün adının BAŞINDAN ve SONUNDAN fiyat-bağlam takılarını temizler.
    'Defacto Tişört yerine' → 'Defacto Tişört'
    'iPhone 15 indirimli fiyat' → 'iPhone 15'"""
    if not ad:
        return ad
    _TAKILAR = {
        "yerine", "fiyat", "fiyatı", "indirimli", "indirim", "normal",
        "sadece", "şimdi", "tl", "₺", "lira", "kupon", "kuponla",
        "sepette", "sepete", "düşüyor", "kargo", "ücretsiz",
    }
    def _trl(s): return s.replace("İ", "i").replace("I", "ı").lower()
    kelimeler = ad.split()
    # Sondan temizle
    while kelimeler and _trl(kelimeler[-1].strip(".,:;-")) in _TAKILAR:
        kelimeler.pop()
    # Baştan temizle
    while kelimeler and _trl(kelimeler[0].strip(".,:;-")) in _TAKILAR:
        kelimeler.pop(0)
    sonuc = " ".join(kelimeler).strip()
    return sonuc if len(sonuc) >= 3 else ad


def _karsilastir_ctasi_temizle(metin: str) -> str:
    """ÜRÜN ADI ÖN-TEMİZLEME SİSTEMİ.

    Ürün adını çıkarmadan ÖNCE, mesajdaki tüm "gürültüyü" temizler:
      • Markdown linkleri:        [metin](url)
      • Karşılaştırma CTA'ları:   🔍 Google'da Karşılaştır
      • Hashtag etiketleri:       #İşbirliği #sponsorlu #reklam
      • Uzun teknik parantezler:  (1.700 MB/s okuma, 4K, XQD...)
      • Yönlendirme ifadeleri:    stoklar eriyor, hemen yakala

    Amaç: Geriye SADECE gerçek ürün adı kalsın.
    'SanDisk CFexpress kartı (uzun teknik...) 🔍 Karşılaştır #İşbirliği'
      → 'SanDisk CFexpress kartı'
    """
    if not metin:
        return metin
    s = metin
    # 1. Markdown link: [metin](url) → sil (CTA linkleri)
    s = re.sub(r"\[[^\]]*\]\((https?://[^)]+)\)", " ", s)
    # 1b. v22.13 KÖK ÇÖZÜM: Çıplak URL'ler ve domain'ler → sil.
    #     "amazon.com.tr/dp/B0XYZ" gibi linkler ürün adı sanılıyordu.
    s = re.sub(r"https?://\S+", " ", s)                       # http(s):// linkler
    s = re.sub(r"\bwww\.\S+", " ", s)                          # www. linkler
    # Çıplak domain + yol: "amazon.com.tr/dp/...", "hepsiburada.com/...", "amzn.to/..."
    s = re.sub(r"\b[\w-]+\.(?:com|net|org|tr|gl|to|co|biz)(?:\.\w+)?(?:/\S*)?",
               " ", s, flags=re.IGNORECASE)
    # 2. Köşeli parantezli CTA: [🔍 Google'da Karşılaştır] → sil
    s = re.sub(r"\[[^\]]*(?:karşılaştır|karsilastir|google|compare)[^\]]*\]",
               " ", s, flags=re.IGNORECASE)
    # 3. "Google'da Karşılaştır" düz metin → sil
    s = re.sub(r"🔍?\s*google'?\s*da\s+karşılaştır", " ", s, flags=re.IGNORECASE)
    # 4. Hashtag etiketleri (#İşbirliği, #sponsorlu, #reklam vb) → sil
    #    Ürün adında hashtag olmaz; bunlar reklam/etiket gürültüsü.
    s = re.sub(r"#\w+", " ", s)
    # 5. Uzun teknik parantez içeriği (>25 karakter) → sil
    #    "(1.700 MB/s okuma, 1.200 MB/s yazma, RescuePRO...)" gibi.
    #    Kısa parantezler korunur ("(2'li paket)" gibi faydalı olabilir).
    s = re.sub(r"\([^)]{25,}\)", " ", s)
    # 6. Yönlendirme/aciliyet ifadeleri → sil (ürün adı değil)
    s = re.sub(
        r"(stoklar?\s+(eriyor|tükenmeden|bitmeden)[^\n]*|hemen\s+yakala[^\n]*"
        r"|son\s+\d+\s+adet[^\n]*|kaçırma[^\n]*)",
        " ", s, flags=re.IGNORECASE)
    # 7. Fazla boşlukları temizle
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _urun_adi_makul(ad: str) -> bool:
    """Çıkarılan ürün adı makul mü?

    v23.1 SADELEŞTİRME: Asıl doğrulama services.urun_kapisi.gecerli_urun_adi
    içinde (TEK merkezi nokta). Bu fonksiyon sadece o kapıya delege eder +
    geriye dönük uyumluluk sağlar. Eskiden buradaki şişkin kara liste
    (mağaza/jenerik/kampanya kelimeleri) merkezi kapıyla tekrar ediyordu.
    """
    if not ad or len(ad) < 4:
        return False
    try:
        from services.urun_kapisi import gecerli_mi
        return gecerli_mi(ad)
    except Exception:
        # Kapı yüklenemezse temel güvenlik: salt rakam/çok kısa reddet
        harf = sum(1 for c in ad if c.isalpha())
        return harf >= 3


def _urun_adi_bul_yapisal(metin: str) -> str | None:
    """Yedek yöntem — model yoksa yapısal kurallar."""
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
        s = re.sub(r"\b(?:yerine|ye geliyor|geliyor|düştü|fiyatı|piyasası|piyasa|sepette|sepete)\b", "", s, flags=re.I)
        # Kargo / teslimat / üyelik takıları (ürün adının parçası değil)
        s = re.sub(r"\b(?:ücretsiz|bedava)\s*kargo\b", "", s, flags=re.I)
        s = re.sub(r"\bkargo\s*(?:bedava|ücretsiz|dahil)\b", "", s, flags=re.I)
        s = re.sub(r"\b(?:premium|plus|pro)\s*üyelik(?:le)?\b", "", s, flags=re.I)
        s = re.sub(r"\baynı\s*gün\s*(?:kargo|teslimat)\b", "", s, flags=re.I)
        s = re.sub(r"\bhızlı\s*(?:kargo|teslimat)\b", "", s, flags=re.I)
        s = re.sub(r"\bstokta\b", "", s, flags=re.I)
        # Emojileri sök, fazla boşluk + son nokta/tire'leri at
        s = emoji_temizle(s)
        s = re.sub(r"\s+", " ", s).strip(" -–—,.|").strip()
        # Sondaki tek başına "var" / "ve" / "indirim" / "kampanya" gibi takıları sil
        s = re.sub(r"\s+(?:var|ve|ile|indirim|kampanya|fırsat)\s*$", "", s, flags=re.I).strip()
        return s

    # Etiket-only satırları reddet (örn. "İndirimli Fiyat:", "Normal Fiyat:")
    # Hem ":" ile bitenler hem fiyatı kaldırıldıktan sonra etiket kalanlar
    _ETIKET_KELIME = re.compile(
        r"^(?:indirimli\s*fiyat|normal\s*fiyat|liste\s*fiyat|piyasa\s*fiyat|sale\s*price|"
        r"sepet|kupon|hediye|stokta\s*var|son\s*stok|tükendi|kargo|ücretsiz\s*kargo|"
        r"fiyat|indirim)\s*[:\-]?\s*$",
        re.I,
    )

    # E-ticaret SİTELERİ — ürün adı sayılmaz (Amazon, Trendyol gibi)
    _SITE_ADLARI = re.compile(
        r"^(?:amazon(?:\s*tr)?|trendyol|hepsiburada|mediamarkt|teknosa|"
        r"n11|gratis|boyner|çiçeksepeti|cicek\s*sepeti|aliexpress|temu|"
        r"e-ticaret|migros|carrefour|a101|bim|şok)\s*[®©™]?\s*$",
        re.I,
    )

    # Slogan / CTA cümleleri — ürün adı DEĞİL (pazarlama lafları)
    _SLOGAN_KALIP = re.compile(
        r"(stoklar?\s*eri|hemen\s*(?:yakala|al|koş|tıkla|sipariş)|kaçırma|"
        r"son\s*(?:fırsat|şans|gün|saat|dakika)|fırsatı?\s*kaçırma|"
        r"acele\s*et|tükenmeden|bitmeden|sınırlı\s*(?:stok|sayıda|süre)|"
        r"süper\s*fiyat|inanılmaz\s*(?:fiyat|fırsat)|kaçmaz|"
        r"şok\s*fiyat|büyük\s*indirim|dev\s*kampanya|"
        r"sadece\s*bugün|bugüne\s*özel|sepete\s*at)",
        re.I,
    )

    def _etiket_satiri_mi(satir: str) -> bool:
        """'İndirimli Fiyat:' veya 'Amazon TR' gibi 'gerçek ürün adı değil' satırı mı."""
        temiz = emoji_temizle(satir).strip(" -–—,.:|🛒🏪🛍️").strip()
        if not temiz:
            return True
        if _ETIKET_KELIME.match(temiz):
            return True
        if _SITE_ADLARI.match(temiz):
            return True
        if _SLOGAN_KALIP.search(temiz):
            return True
        return False

    # Anlamsız tek-kelime ürün adlarını engelle (fiyat çıkınca kalan filler)
    _GENEL_KELIME = frozenset({
        "için", "adet", "yeni", "süper", "harika", "muhteşem", "kaçırma",
        "ürün", "fırsat", "kampanya", "indirim", "tane", "paket", "set",
        "model", "renk", "beden", "boyut", "stok", "stokta", "bugün",
        "şimdi", "hemen", "özel", "sınırlı", "son", "büyük", "küçük",
        "fiyat", "fiyatı", "ucuz", "pahalı", "kaliteli", "orjinal", "orijinal",
    })

    def _gecerli_urun_adi(temiz: str) -> bool:
        """Temizlenmiş metin gerçek bir ürün adı mı?
        Tek kelimeyse ve genel/filler kelimeyse reddet.
        Çoğunlukla rakam/fiyat ifadesi olan çöpü de reddet."""
        if len(temiz) < 4:
            return False
        if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", temiz):
            return False
        kelimeler = temiz.split()
        # Tek kelime VE genel filler ise ürün adı değil
        if len(kelimeler) == 1 and kelimeler[0].lower() in _GENEL_KELIME:
            return False
        # Fiyat/indirim bağlamı kelimeleri — bunlardan oluşan ad gerçek ürün değil
        # ("490 04 İndirim İndirimli", "Normal Fiyat İndirimli" gibi)
        _FIYAT_BAGLAM = {
            "fiyat", "fiyatı", "indirim", "indirimli", "normal", "tl", "₺",
            "lira", "ucuz", "kampanya", "fırsat", "fırsatı", "tasarruf",
        }
        anlamli = [
            k for k in kelimeler
            if k.lower() not in _FIYAT_BAGLAM and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2,}", k)
        ]
        # Anlamlı (fiyat-dışı, harf içeren) kelime kalmadıysa → çöp
        if not anlamli:
            return False
        # Rakam oranı çok yüksekse (>%50) → fiyat çöpü
        rakam_say = sum(1 for c in temiz if c.isdigit())
        if rakam_say > len(temiz.replace(" ", "")) * 0.5:
            return False
        return True

    # Öncelik 1: ürün başlık emoji'siyle başlayan satırlar (en ürünsel)
    for satir in satirlar:
        if not _URUN_BAS.match(satir):
            continue
        if satir.startswith(("#", "@")) or "http" in satir:
            continue
        if "#" in satir:
            continue
        if _KAMPANYA_KALIP.search(satir):
            continue
        if _etiket_satiri_mi(satir):
            continue
        temiz = _temizle(satir)
        # _temizle sonrası ortaya çıkan da hâlâ etiket olabilir
        if _etiket_satiri_mi(temiz):
            continue
        if _gecerli_urun_adi(temiz):
            return temiz[:80]

    # Öncelik 2: emoji yok ama temiz uzun ürün adı (fiyatsız)
    for satir in satirlar:
        if "#" in satir:
            continue
        if _etiket_satiri_mi(satir):
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
        if _etiket_satiri_mi(satir):
            continue
        temiz = _temizle(satir)
        if _etiket_satiri_mi(temiz):
            continue
        # Fiyat çıkarıldıktan sonra ≥4 karakter + ≥3 harfli kelime kaldıysa
        # gerçek ürün adı say (örn. "Çorap", "Kettle", "Lego" gibi kısa adlar).
        # Eşik 8→4: kısa ama geçerli ürün adlarını kaybetme.
        if (
            _gecerli_urun_adi(temiz)
            and not temiz.lower().startswith(("kupon", "indirim", "sepette", "hepsipara", "premiuma",
                                              "fiyat", "normal", "liste", "indirimli", "piyasa"))
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


@functools.lru_cache(maxsize=2048)
def urun_kimligi(url: str) -> str:
    """URL'den ürün kimliği çıkar. Aynı ürünün farklı linkleri (farklı
    affiliate tag, ref param) aynı kimliği döner. İki FARKLI ürün ise
    iki farklı kimlik döner.

    Kullanım: bir mesajda toplanan linklerin kaç farklı ürüne ait
    olduğunu tespit etmek için.

    NOT: Saf fonksiyon (sadece url'ye bağlı) → LRU cache ile hızlandırıldı.
    1000+ mesajda aynı linkler tekrar geldiğinde yeniden hesaplanmaz.
    """
    if not url:
        return ""
    u = url.lower()
    # Amazon: /dp/XXXXXXXXXX veya /gp/product/XXXXXXXXXX
    m = re.search(r'/(?:dp|gp/product)/([a-z0-9]{10})', u)
    if m:
        return f"amazon:{m.group(1)}"
    # Trendyol: -p-NNNNNN
    m = re.search(r'-p-(\d+)', u)
    if m:
        return f"trendyol:{m.group(1)}"
    # Hepsiburada: -pNNNNNNNN, -p-XXXX
    m = re.search(r'-p-?([a-z0-9]{6,})', u)
    if m:
        return f"hb:{m.group(1)}"
    # N11: /urun/... veya /NNNNNN
    m = re.search(r'/urun/([a-z0-9\-]+)', u)
    if m:
        return f"n11:{m.group(1)[:40]}"
    # Kısa linkler: tam path kimlik sayılır (çözülemez, ayrı tut)
    try:
        p = urlparse(url)
        if any(k in p.netloc for k in ("ty.gl", "hb.gl", "amzn.to", "sl.n11", "hb.biz", "dlvr.it", "bit.ly")):
            return f"kisa:{p.netloc}{p.path}"
        return f"{p.netloc}{p.path}"
    except Exception:
        return url


def urun_kimligine_gore_grupla(linkler: list[str]) -> list[str]:
    """Bir link listesini ürün kimliğine göre grupla.
    Her benzersiz ürün için TEK temsilci link döner (öncelikli olanı).
    Arama motoru / fiyat karşılaştırma linkleri ürün DEĞİLDİR — elenir.

    Örnek:
      ['amazon.com.tr/dp/X?tag=a', 'amazon.com.tr/dp/X?ref=b', 'trendyol.com/y-p-2']
      → ['amazon.com.tr/dp/X', 'trendyol.com/y-p-2']   (2 ürün)
    """
    if not linkler:
        return []
    # Arama/karşılaştırma/sosyal linkler ürün linki sayılmaz
    _eleme = ("google.com/search", "bing.com/search", "duckduckgo.com",
              "akakce.com", "cimri.com", "epey.com", "t.me/", "/search?")
    gorulen: dict[str, str] = {}   # kimlik → temsilci link
    for lnk in linkler:
        ll = (lnk or "").lower()
        if any(e in ll for e in _eleme):
            continue   # arama/karşılaştırma linki — atla
        kimlik = urun_kimligi(lnk)
        if kimlik and kimlik not in gorulen:
            gorulen[kimlik] = link_temizle(lnk)
    sonuc = list(gorulen.values())
    # Gerçek ürün sayfalarını (kimlikli: -p-, /dp/, /urun/) öne al; kampanya/
    # ana sayfa linklerini sona koy → çoklu üründe doğru link eşleşmesi.
    def _gercek_urun_mu(u: str) -> int:
        ul = (u or "").lower()
        if re.search(r'/(?:dp|gp/product)/[a-z0-9]{10}', ul): return 0
        if re.search(r'-p-?\d', ul): return 0
        if '/urun/' in ul: return 0
        if any(k in ul for k in ("ty.gl", "hb.gl", "amzn.to", "sl.n11", "hb.biz")): return 0
        return 1   # kimliksiz (kampanya/ana sayfa) → sona
    sonuc.sort(key=_gercek_urun_mu)
    return sonuc


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
    gizli = ("google.com/search", "bing.com/search", "duckduckgo.com", "t.me/",
             "akakce.com", "cimri.com", "epey.com", "/search?")

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
    # v23.17 — Kupon KODU en az bir HARF içermeli (HAZIRAN1000, INDIRIM50).
    # "100TL", "500" gibi salt-rakam değerler kupon KODU değil, indirim
    # MİKTARIDIR — bunları kod sanma (kanal hatasıydı).
    kaliplar = [
        r"kupon\s*kodu?\s*[:\-]?\s*([A-Z][A-Z0-9]{3,19})",   # "Kupon kodu: INDIRIM50"
        r"indirim\s*kodu?\s*[:\-]?\s*([A-Z][A-Z0-9]{3,19})",
        r"kupon\s*[:\-]?\s*([A-Z][A-Z0-9]{3,19})",
        r"([A-Z][A-Z0-9]{3,19})\s*[Kk]odu?\s*(?:ile|İle|kullan)",
        r"([A-Z][A-Z0-9]{3,19})\s*[Kk]upon",
        r"kodu?\s*[:\-]\s*([A-Z][A-Z0-9]{3,19})",   # "Kodu: KETTLE50"
    ]
    for kalip in kaliplar:
        eslesme = re.findall(kalip, metin or "", re.I)
        if eslesme:
            kod = eslesme[0].upper()
            # En az bir harf İÇERMELİ (salt rakam = indirim değeri, kod değil)
            if not any(c.isalpha() for c in kod):
                continue
            # Yaygın yanlış eşleşmeleri filtrele
            if kod not in {"ADET", "KODU", "INDIRIM", "KUPON", "FIYAT",
                           "SEPETTE", "SEPET", "HEDIYE", "TL"}:
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
_YENI_URUN = re.compile(
    # ürün başlığı sayılan işaretlerden biriyle başlıyor:
    #  - ürün emojileri (🔻🔥📦...)
    #  - v23.16: numaralı emojiler (1️⃣2️⃣...), ✅🔑 (kupon satırları),
    #    madde işaretleri (•, ►, ▪, ‣) ve "1)" "2." gibi numaralı liste
    r"^(?:[🔻🔥📦🛍️⚡🎯💎🆕✅🔑🔸🔹▪️◾•►‣]|[0-9]️⃣|[0-9]{1,2}[\).]\s)\s*\S",
    re.UNICODE,
)


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
    # ✅ ile başlayan + ürün adı içermeyen salt açıklama/fiyat paragrafı
    # ("✅Plus'a Özel İndirim + Kupon İle Sepette 462TL'ye Düşüyor") → ürün DEĞİL,
    # önceki ürünün açıklamasıdır. Bu, çoklu üründe yanlış bölmeyi önler.
    ilk_kar = p.lstrip()[:1]
    if ilk_kar in ("✅", "☑", "✔"):
        return False   # ✅ ile başlayan satır = fiyat/kupon açıklaması, ürün değil
    return True


# Satır içi ürün ayırıcı desen:
#   "Ürün adı 285TL - Başka Ürün adı Sepette 228TL"
_SATIR_ICI_AYIRICI = re.compile(
    r"""
    (?P<sol>[^\-–|]+?\b\d[\d.,]*\s*(?:TL|₺|lira))   # sol ürün + fiyat
    \s*[\-–|]\s*                                     # ayırıcı
    (?P<sag>[A-Za-zÇĞİÖŞÜçğıöşü][^\-–|]{8,}\d[\d.,]*\s*(?:TL|₺|lira))  # sağ ürün + fiyat
    """,
    re.IGNORECASE | re.VERBOSE,
)
# İki ayrı fiyat+TL var mı? (hızlı önkontrol)
_IKI_FIYAT_TL = re.compile(r"\d[\d.,]*\s*(?:TL|₺|lira).{2,80}?\d[\d.,]*\s*(?:TL|₺|lira)", re.I)


def _satir_ici_iki_urun_var_mi(satir: str) -> bool:
    """Tek satırda iki ürün+fiyat ifadesi var mı?
    ✅/☑/✔ ile başlayan satırlar fiyat/kupon AÇIKLAMASIDIR — ürün değil,
    bölünmemeli (önceki ürünün fiyat detayı)."""
    s = satir.lstrip()
    if s[:1] in ("✅", "☑", "✔"):
        return False
    if not _IKI_FIYAT_TL.search(satir):
        return False
    if not _SATIR_ICI_AYIRICI.search(satir):
        return False
    return True


def _satir_ici_bol(satir: str) -> list[str]:
    """Tek satırı 'ürün+fiyat - ürün+fiyat' deseninde böl."""
    if not _satir_ici_iki_urun_var_mi(satir):
        return [satir]
    parcalar: list[str] = []
    kalan = satir
    while True:
        m = _SATIR_ICI_AYIRICI.search(kalan)
        if not m:
            break
        # Sol parça: satırın başından "sol" grubunun sonuna kadar
        sol = (kalan[: m.start("sol")] + m.group("sol")).strip()
        if sol:
            parcalar.append(sol)
        # Kalan: "sag" grubu + sonrası → bir sonraki turda işlenir
        kalan = m.group("sag") + kalan[m.end("sag"):]
    if kalan.strip():
        parcalar.append(kalan.strip())
    return parcalar if len(parcalar) >= 2 else [satir]


def _paragraf_ici_bol(paragraf: str) -> list[str]:
    """Aynı paragrafta birden fazla ürün başlığı varsa ayır.

    İki seviyeli bölme — sıralı şekilde her satıra uygulanır:
      1) Satırlar arası: yeni ürün-emoji ile başlayan satırda öncekini kapat
      2) Satır içi: 'ürün X TL - ürün Y TL' deseninde bu satırı da böl
    """
    satirlar = paragraf.split("\n")
    bloklar: list[str] = []
    mevcut: list[str] = []

    def _commit():
        nonlocal mevcut
        if mevcut:
            bloklar.append("\n".join(mevcut))
            mevcut = []

    for satir in satirlar:
        s_strip = satir.strip()

        # 1) Satırlar arası bölme: yeni ürün-emoji ile başlayan satırda öncekini kapat
        if _YENI_URUN.match(s_strip) and mevcut:
            onceki = "\n".join(mevcut)
            if re.search(r"[\d.,]+\s*(?:TL|₺|lira)", onceki, re.I) or re.search(r"%\d+|\d+%", onceki):
                temizSatir = re.sub(r"[🔻🔥📦🛍️⚡🎯💎🆕\s]+", "", s_strip)
                if len(temizSatir) >= 5 and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", temizSatir):
                    _commit()
                    # NOT: continue YOK — bu satırın kendisi de satır içi bölmeye girebilir

        # 2) Satır içi bölme: tek satırda 'ürün X TL - ürün Y TL'
        ic_parcalar = _satir_ici_bol(satir)
        if len(ic_parcalar) >= 2:
            mevcut.append(ic_parcalar[0])
            _commit()
            for p in ic_parcalar[1:-1]:
                bloklar.append(p)
            mevcut.append(ic_parcalar[-1])
        else:
            mevcut.append(satir)

    _commit()
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
    # Çoklu ürün desteği — max 5 ürüne kadar
    for blok in urun_bloklari[:5]:
        tam = (blok + "\n\n" + paylasilan_metin).strip() if paylasilan_metin else blok
        sonuc.append(tam)
    return sonuc
