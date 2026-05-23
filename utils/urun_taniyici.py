"""
═══════════════════════════════════════════════════════════════════════
Ürün Adı Tanıma — Token Sınıflandırıcı (gerçek ML, regex listesi DEĞİL)

Bir mesajdaki HER kelimeyi sınıflandırır:
    URUN    → ürün adının parçası (iPhone, Çorap, Süpürge, 256GB)
    FILLER  → anlamsız dolgu/slogan (hemen, kaçırma, süper, için)

Model: Logistic Regression. Her kelime için BAĞLAMSAL özellikler:
  • Büyük harfle mi başlıyor? (markalar/ürünler genelde başlar)
  • Tamamı büyük harf mi? (SLOGAN/CTA işareti: "ERİYOR", "ŞOK")
  • Alfanümerik mi? (model kodu: 256GB, V15, XL)
  • Karakter n-gram'ları (ek bilgi)
  • Önceki/sonraki kelime ipuçları
  • Kelime uzunluğu, rakam içeriyor mu

EĞİTİM VERİSİ otomatik üretilir:
  • POZİTİF (URUN): mevcut 3200 ürün adındaki kelimeler
  • NEGATİF (FILLER): slogan/CTA/dolgu cümlelerinden kelimeler

Bot çalıştıkça yeni örneklerle güncellenebilir (self-supervised).
Pure Python, harici bağımlılık yok.
═══════════════════════════════════════════════════════════════════════
"""
import json
import math
import os
import random
import re
from typing import Optional

import config
from utils.log import log

_MODEL_FILE = os.path.join(config.DATA_DIR, "urun_taniyici.json")
_LR_LR = 0.1
_LR_L2 = 0.0005
_LR_EPOCH = 12

# Eğitilmiş ağırlıklar: özellik → skor (URUN olma yönünde)
_agirliklar: dict[str, float] = {}
_bias: float = 0.0
_yuklendi = False


# ── Negatif (FILLER) eğitim cümleleri — slogan/CTA/dolgu ──
# Bunlar ürün adı DEĞİL. Modele "böyle kelimeler ürün değil" diye öğretir.
# Pozitif örnekler 14000+ kelime olduğundan, negatifleri de zengin tutuyoruz
# (her cümle birkaç kez farklı kombinasyonda — model dengeli öğrensin).
_NEGATIF_CUMLELER = [
    "stoklar eriyor hemen yakala",
    "stoklar eriyor son fırsat",
    "stoklar eriyor acele edin",
    "son fırsat kaçırma acele et",
    "son fırsat kaçırmayın hemen",
    "süper fiyat şok indirim büyük kampanya",
    "şok fiyat müthiş indirim dev kampanya",
    "sadece bugün bugüne özel sınırlı süre",
    "sadece bugün geçerli kaçırmayın",
    "hemen al hemen tıkla sepete at",
    "hemen al hemen koş hemen sipariş ver",
    "hemen yakala hemen kap fırsatı kaçırma",
    "inanılmaz fırsat muhteşem fiyat kaçmaz",
    "inanılmaz indirim harika fırsat müthiş",
    "tükenmeden bitmeden son saat son dakika",
    "tükenmeden alın bitmeden yetişin",
    "indirimli fiyat normal fiyat liste fiyatı piyasa fiyatı",
    "kanalımıza katıl abone ol bizi takip et",
    "kanalımıza gel grubumuza katıl üye ol",
    "çekiliş hediye kazan yarışma ödül",
    "çekilişe katıl hediye kazanma şansı",
    "ücretsiz kargo bedava kargo hızlı teslimat",
    "premium üyelik plus üyelik avantajları",
    "için ile veya ve ama fakat çünkü",
    "tüm ürünlerde seçili ürünlerde indirim var",
    "günün fırsatları en iyi fırsatlar burada",
    "tıkla gör incele detaylar açıklamada",
    "yeni geldi yeni sezon yeni koleksiyon",
    "kaçırılmayacak fırsat sınırlı sayıda stok",
    "alışverişe başla şimdi al sonra öde",
    "fiyatına inanamayacaksınız mutlaka bakın",
    "büyük indirim müthiş kampanya dev fırsat",
    "acele edin stoklar sınırlı tükeniyor",
    "kaçırma yakala koş al sipariş ver tıkla",
    "süper harika muhteşem müthiş inanılmaz",
    "özel fırsat sınırlı süre son şans",
    "şimdi hemen acele bugün özel günlük",
    "indirim kampanya fırsat fiyat ucuz bedava",
    "takip et abone ol katıl üye gel bekliyoruz",
    "linkten al açıklamadan tıkla profilden bak",
    "kanalımıza katıl abone ol takip et bizi",
    "günün fırsatları en iyi fiyatlar burada bizde",
    "yeni geldi yeni ürünler stoklarda",
    "abone ol takip et katıl gel bekliyoruz seni",
    "en iyi en ucuz en uygun fiyat garantisi",
]

# Bu tek kelimeler net FILLER (kuvvetli negatif sinyal)
_FILLER_TEK_KELIMELER = [
    "hemen", "kaçırma", "yakala", "acele", "süper", "şok", "müthiş",
    "inanılmaz", "harika", "muhteşem", "için", "ile", "veya", "fakat",
    "çünkü", "bugün", "şimdi", "özel", "sınırlı", "tükeniyor", "eriyor",
    "kampanya", "indirim", "indirimli", "fırsat", "ucuz", "bedava",
    "abone", "katıl", "takip", "çekiliş", "hediye", "yeni", "tıkla",
    "koş", "fiyat", "fiyatı", "stokta", "stok", "sepette", "sepete",
    "kargo", "ücretsiz", "normal", "liste", "piyasa", "var", "satışta",
    "geldi", "kazanın", "kazan", "premium", "üyelik", "ürün", "ürünler",
    "adet", "tane", "paket", "set", "model", "renk", "beden",
    # Kazanç/ödül kavramı — bunlar SATILAN değil KAZANILAN şeyler (reklam işareti)
    "bonus", "puan", "ödül", "hediye", "kazanç", "çekiliş", "davet",
    "kupon", "kod", "şans", "bilet", "kazanmak", "kazanma",
    # İşbirliği/duyuru kavramı — satılan ürün değil, tanıtım (reklam işareti)
    "işbirliği", "isbirligi", "sponsor", "sponsorlu", "reklam", "duyuru",
    "varan", "varana", "kadar", "tüm", "seçili", "geçerli",
]
_FILLER_SET = frozenset(_FILLER_TEK_KELIMELER)

# Pozitif örnekleri ml_dataset'ten alacağız (3200 gerçek ürün adı)


def _temizle_fiyat(metin: str) -> str:
    """Fiyat/yüzde/url kısımlarını çıkar — kelimelere ayırmadan önce."""
    s = re.sub(r"https?://\S+", " ", metin)
    s = re.sub(r"[\d.,]+\s*(?:₺|tl|lira)", " ", s, flags=re.I)
    s = re.sub(r"%\s*\d+|\d+\s*%", " ", s)
    return s


def _kelime_ozellikleri(kelime: str, onceki: str, sonraki: str) -> dict[str, float]:
    """Bir kelime için bağlamsal özellik vektörü (regex listesi değil — öğrenilen sinyaller).

    Bu özellikler modele veriliyor; model hangi özelliğin ÜRÜN/FILLER
    işareti olduğunu eğitim verisinden ÖĞRENİYOR.
    """
    oz: dict[str, float] = {}
    k = kelime
    kl = kelime.lower()

    # ── Biçimsel özellikler ──
    oz["BIAS"] = 1.0
    if k and k[0].isupper():
        oz["BASLANGIC_BUYUK"] = 1.0
    if len(k) >= 3 and k.isupper():
        oz["TAMAMI_BUYUK"] = 1.0          # "ERİYOR", "ŞOK" → slogan işareti
    if any(c.isdigit() for c in k) and any(c.isalpha() for c in k):
        oz["ALFANUMERIK"] = 1.0           # "256GB", "V15", "5x180gr" → ürün kodu
    if k.isdigit():
        oz["SADECE_RAKAM"] = 1.0
    oz["UZUNLUK"] = min(len(k), 15) / 15.0

    # ── Karakter n-gram'ları (kelimenin "şekli") ──
    if len(kl) >= 4:
        oz[f"BAS3:{kl[:3]}"] = 1.0        # ilk 3 harf
        oz[f"SON3:{kl[-3:]}"] = 1.0       # son 3 harf (Türkçe ekler: -lar, -siz)

    # ── Kelimenin kendisi (öğrenilen lexicon) ──
    oz[f"KELIME:{kl}"] = 1.0

    # ── Bağlam (önceki/sonraki kelime) ──
    if onceki:
        oz[f"ONCE:{onceki.lower()}"] = 1.0
    if sonraki:
        oz[f"SONRA:{sonraki.lower()}"] = 1.0

    return oz


def _cumle_kelimeleri(cumle: str) -> list[tuple[str, str, str]]:
    """Cümleyi (kelime, önceki, sonraki) üçlülerine ayır."""
    s = _temizle_fiyat(cumle)
    # & işaretini koru (marka adları: "Jack & Jones", "H&M")
    s = s.replace("&", " & ")
    # Emojileri ve diğer noktalama işaretlerini boşlukla değiştir (& hariç)
    s = re.sub(r"[^\wçğıöşüâîÇĞİÖŞÜÂÎ&]+", " ", s, flags=re.UNICODE)
    kelimeler = [w for w in s.split() if len(w) >= 2 or w == "&"]
    sonuc = []
    for i, w in enumerate(kelimeler):
        onceki = kelimeler[i-1] if i > 0 else ""
        sonraki = kelimeler[i+1] if i < len(kelimeler)-1 else ""
        sonuc.append((w, onceki, sonraki))
    return sonuc


def _skor(ozellikler: dict[str, float]) -> float:
    """Sigmoid(ağırlık·özellik). 1.0=URUN, 0.0=FILLER."""
    z = _bias
    for oz, deger in ozellikler.items():
        z += _agirliklar.get(oz, 0.0) * deger
    # Sigmoid (overflow korumalı)
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _egit(pozitif_cumleler: list[str], negatif_cumleler: list[str]) -> None:
    """Logistic Regression eğitimi — SGD."""
    global _agirliklar, _bias

    # Eğitim örnekleri: (özellikler, etiket) — etiket 1=URUN, 0=FILLER
    poz_ornekler = []
    for cumle in pozitif_cumleler:
        for kelime, onceki, sonraki in _cumle_kelimeleri(cumle):
            poz_ornekler.append((_kelime_ozellikleri(kelime, onceki, sonraki), 1))

    neg_ornekler = []
    for cumle in negatif_cumleler:
        for kelime, onceki, sonraki in _cumle_kelimeleri(cumle):
            neg_ornekler.append((_kelime_ozellikleri(kelime, onceki, sonraki), 0))
    # Net filler tek kelimeleri güçlü negatif sinyal olarak ekle
    # (her birini birden çok kez — pozitif baskınlığını dengele)
    for kelime in _FILLER_TEK_KELIMELER:
        for _ in range(5):
            neg_ornekler.append((_kelime_ozellikleri(kelime, "", ""), 0))

    # ── Class balancing ──
    # Pozitif (14000+) ile negatif (birkaç yüz) dengesiz. Negatifleri
    # çoğaltarak modele FILLER sinyallerini eşit ağırlıkta öğretiyoruz.
    if neg_ornekler and poz_ornekler:
        kat = max(1, len(poz_ornekler) // len(neg_ornekler))
        neg_ornekler = neg_ornekler * kat

    ornekler = poz_ornekler + neg_ornekler
    if not ornekler:
        return

    _agirliklar = {}
    _bias = 0.0

    for epoch in range(_LR_EPOCH):
        random.shuffle(ornekler)
        for ozellikler, etiket in ornekler:
            tahmin = _skor(ozellikler)
            hata = tahmin - etiket
            # Bias güncelle
            _bias -= _LR_LR * hata
            # Ağırlıkları güncelle (L2 regularization)
            for oz, deger in ozellikler.items():
                mevcut = _agirliklar.get(oz, 0.0)
                grad = hata * deger + _LR_L2 * mevcut
                _agirliklar[oz] = mevcut - _LR_LR * grad

    log("OK", f"Ürün tanıyıcı eğitildi: {len(ornekler)} kelime örneği, "
              f"{len(_agirliklar)} özellik")


def kelime_urun_mu(kelime: str, onceki: str = "", sonraki: str = "") -> float:
    """Bir kelimenin ürün adı parçası olma olasılığı (0.0-1.0)."""
    if not _yuklendi:
        ilk_kurulum()
    return _skor(_kelime_ozellikleri(kelime, onceki, sonraki))


# ════════════════════════════════════════════════════════════════
# SATIR SEVİYESİ SINIFLANDIRICI — "bu satırın tamamı ürün adı mı?"
# ════════════════════════════════════════════════════════════════
# Token modeli kelime kelime bakar; satır modeli bütüne bakar.
# İki modelin oyu birleşir (ensemble) → daha sağlam karar.

_satir_agirliklar: dict[str, float] = {}
_satir_bias: float = 0.0


def _satir_ozellikleri(satir: str) -> dict[str, float]:
    """Bir satırın bütünsel özellikleri (satır bazlı, token değil)."""
    oz: dict[str, float] = {"BIAS": 1.0}
    kelimeler_ctx = _cumle_kelimeleri(satir)
    if not kelimeler_ctx:
        return oz
    kelimeler = [w for w, _, _ in kelimeler_ctx]
    n = len(kelimeler)

    oz["KELIME_SAYISI"] = min(n, 8) / 8.0

    token_skorlari = [_skor(_kelime_ozellikleri(w, o, s)) for w, o, s in kelimeler_ctx]
    oz["ORT_TOKEN_SKOR"] = sum(token_skorlari) / n
    oz["MAX_TOKEN_SKOR"] = max(token_skorlari)
    oz["MIN_TOKEN_SKOR"] = min(token_skorlari)
    oz["URUN_KELIME_ORANI"] = sum(1 for s in token_skorlari if s >= 0.5) / n

    oz["BUYUK_BASLANGIC_ORANI"] = sum(1 for w in kelimeler if w[:1].isupper()) / n
    oz["TAMAMI_BUYUK_ORANI"] = sum(1 for w in kelimeler if len(w) >= 3 and w.isupper()) / n
    oz["KOD_ORANI"] = sum(
        1 for w in kelimeler if any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
    ) / n
    fl = sum(1 for w in kelimeler
             if w.replace("İ", "i").replace("I", "ı").lower() in _FILLER_SET)
    oz["FILLER_ORANI"] = fl / n
    return oz


def _satir_skor(satir: str) -> float:
    """Satır modelinin 'bu satır ürün adı' olasılığı (0-1)."""
    oz = _satir_ozellikleri(satir)
    z = _satir_bias
    for k, v in oz.items():
        z += _satir_agirliklar.get(k, 0.0) * v
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _satir_egit(pozitif_satirlar: list[str], negatif_satirlar: list[str]) -> None:
    """Satır sınıflandırıcı eğitimi (token modeli eğitildikten SONRA)."""
    global _satir_agirliklar, _satir_bias
    ornekler = [(_satir_ozellikleri(s), 1) for s in pozitif_satirlar]
    ornekler += [(_satir_ozellikleri(s), 0) for s in negatif_satirlar]
    if not ornekler:
        return
    _satir_agirliklar = {}
    _satir_bias = 0.0
    for epoch in range(_LR_EPOCH):
        random.shuffle(ornekler)
        for oz, etiket in ornekler:
            z = _satir_bias
            for k, v in oz.items():
                z += _satir_agirliklar.get(k, 0.0) * v
            tahmin = 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))
            hata = tahmin - etiket
            _satir_bias -= _LR_LR * hata
            for k, v in oz.items():
                mevcut = _satir_agirliklar.get(k, 0.0)
                _satir_agirliklar[k] = mevcut - _LR_LR * (hata * v + _LR_L2 * mevcut)
    log("OK", f"Satır sınıflandırıcı eğitildi: {len(ornekler)} satır örneği")


def urun_adi_cikar(metin: str) -> Optional[str]:
    """Metinden ürün adı çıkar — TOKEN + SATIR modeli birlikte (ensemble).

    1. Token modeli: her satırda ürün kelime dizilerini bulur
    2. Satır modeli: o satırın bütünsel ürün-olma olasılığı
    3. İki skor 0.6/0.4 ağırlıkla birleşir; en güçlü aday döner
    """
    if not _yuklendi:
        ilk_kurulum()
    if not metin:
        return None

    en_iyi_ad = None
    en_iyi_skor = 0.0

    for satir in metin.split("\n"):
        satir = satir.strip()
        if not satir or satir.startswith(("#", "@")) or "http" in satir:
            continue
        kelimeler_ctx = _cumle_kelimeleri(satir)
        if not kelimeler_ctx:
            continue

        satir_oyu = _satir_skor(satir)
        skorlar = [(w, _skor(_kelime_ozellikleri(w, o, s))) for w, o, s in kelimeler_ctx]

        mevcut_dizi, diziler = [], []
        for kelime, s in skorlar:
            if s >= 0.5:
                mevcut_dizi.append((kelime, s))
            else:
                if mevcut_dizi:
                    diziler.append(mevcut_dizi); mevcut_dizi = []
        if mevcut_dizi:
            diziler.append(mevcut_dizi)

        for dizi in diziler:
            ad = " ".join(w for w, _ in dizi)
            ort_token = sum(s for _, s in dizi) / len(dizi)
            dizi_skoru = ort_token * (1 + 0.1 * min(len(dizi), 5))
            birlesik = 0.6 * dizi_skoru + 0.4 * satir_oyu   # ENSEMBLE
            if len(ad) >= 3 and birlesik > en_iyi_skor:
                en_iyi_skor = birlesik
                en_iyi_ad = ad

    if en_iyi_ad and len(en_iyi_ad) >= 3:
        kelimeler = en_iyi_ad.split()
        # Her kelimeyi normalize et
        norm = [k.replace("İ", "i").replace("I", "ı").lower() for k in kelimeler]
        # Tek kelime + filler → reddet
        if len(kelimeler) == 1 and norm[0] in _FILLER_SET:
            return None
        # Tek kelime + tamamı büyük harf → kupon kodu (FIRSATI, INDIRIM50) → reddet
        # Gerçek tek-kelime ürünler normal yazılır (Çorap, Lego), kupon kodları BÜYÜK
        if len(kelimeler) == 1 and kelimeler[0].isupper() and len(kelimeler[0]) >= 4:
            return None
        # Tüm kelimeler filler VEYA mağaza adı ise → gerçek ürün değil
        # (örn. "Hepsiburada işbirliği varan" → hepsi filler/mağaza)
        try:
            from utils.reklam import _MAGAZA_RE
            anlamli = [
                k for k in norm
                if k not in _FILLER_SET and not _MAGAZA_RE.search(k)
            ]
            if not anlamli:
                return None   # somut nesne yok, sadece mağaza+filler
        except Exception:
            pass
        return en_iyi_ad[:80]
    return None


# ════════════════════════════════════════════════════════════════
# Self-supervised: bot çalışırken yeni örneklerle güçlen
# ════════════════════════════════════════════════════════════════

_yeni_pozitif: list[str] = []
_yeni_negatif: list[str] = []


_egitim_gerekli = False   # arka plan görevi bunu kontrol eder


def ogren_pozitif(urun_adi: str) -> None:
    """Doğrulanmış ürün adını eğitime ekle. Eşik dolunca SADECE bayrak
    kaldırır — gerçek eğitim arka plan görevinde (event loop bloklanmasın)."""
    global _egitim_gerekli
    if urun_adi and len(urun_adi) >= 3:
        _yeni_pozitif.append(urun_adi)
        if len(_yeni_pozitif) >= 50:
            _egitim_gerekli = True


def ogren_negatif(slogan: str) -> None:
    """Reklam/slogan olarak işaretlenmiş metni negatif örnek olarak ekle."""
    global _egitim_gerekli
    if slogan and len(slogan) >= 5:
        _yeni_negatif.append(slogan)
        if len(_yeni_negatif) >= 50:
            _egitim_gerekli = True


def egitim_gerekli_mi() -> bool:
    """Arka plan görevi için: yeniden eğitim bekliyor mu?"""
    return _egitim_gerekli


async def arka_plan_egit() -> None:
    """Eğitimi thread'de çalıştır — event loop bloklanmaz.
    main.py'da periyodik görev olarak çağrılır."""
    global _egitim_gerekli
    if not _egitim_gerekli:
        return
    _egitim_gerekli = False
    import asyncio
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, yeniden_egit)


def yeniden_egit() -> None:
    """Token + Satır modellerini yeni örneklerle yeniden eğit (senkron)."""
    global _yeni_pozitif, _yeni_negatif
    from utils.ml_dataset import EGITIM_VERISI
    pozitif = [m for m, _ in EGITIM_VERISI] + _yeni_pozitif
    negatif = list(_NEGATIF_CUMLELER) + _yeni_negatif
    _egit(pozitif, negatif)               # token modeli
    _satir_egit(pozitif, negatif)         # satır modeli (token sonrası)
    _kaydet()
    # Bellek sızıntısını önle — son 500/200 örneği tut (model zaten öğrendi)
    _yeni_pozitif = _yeni_pozitif[-500:]
    _yeni_negatif = _yeni_negatif[-200:]


# ── Disk ──
def _kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_MODEL_FILE) or ".", exist_ok=True)
        gecici = _MODEL_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({
                "agirliklar": _agirliklar,
                "bias": _bias,
                "satir_agirliklar": _satir_agirliklar,
                "satir_bias": _satir_bias,
                "yeni_pozitif": _yeni_pozitif[-500:],
                "yeni_negatif": _yeni_negatif[-200:],
            }, f, ensure_ascii=False)
        os.replace(gecici, _MODEL_FILE)
    except Exception as e:
        log("UYARI", f"Ürün tanıyıcı kaydet: {e}")


def _yukle() -> bool:
    global _agirliklar, _bias, _yeni_pozitif, _yeni_negatif
    global _satir_agirliklar, _satir_bias
    if not os.path.exists(_MODEL_FILE):
        return False
    try:
        with open(_MODEL_FILE, encoding="utf-8") as f:
            d = json.load(f)
        _agirliklar = d.get("agirliklar", {})
        _bias = d.get("bias", 0.0)
        _satir_agirliklar = d.get("satir_agirliklar", {})
        _satir_bias = d.get("satir_bias", 0.0)
        _yeni_pozitif = d.get("yeni_pozitif", [])
        _yeni_negatif = d.get("yeni_negatif", [])
        return bool(_agirliklar)
    except Exception as e:
        log("UYARI", f"Ürün tanıyıcı yükle: {e}")
        return False


def ilk_kurulum() -> None:
    global _yuklendi
    if _yuklendi:
        return
    if _yukle():
        _yuklendi = True
        log("OK", f"Ürün tanıyıcı yüklendi: {len(_agirliklar)} özellik")
        return
    # İlk eğitim
    from utils.ml_dataset import EGITIM_VERISI
    pozitif = [m for m, _ in EGITIM_VERISI]
    log("BILGI", f"Ürün tanıyıcı ilk eğitim: {len(pozitif)} pozitif, "
                 f"{len(_NEGATIF_CUMLELER)} negatif örnek")
    _egit(pozitif, _NEGATIF_CUMLELER)            # token modeli
    _satir_egit(pozitif, _NEGATIF_CUMLELER)      # satır modeli
    _kaydet()
    _yuklendi = True


def istatistik() -> dict:
    if not _yuklendi:
        ilk_kurulum()
    return {
        "ozellik_sayisi": len(_agirliklar),
        "satir_ozellik": len(_satir_agirliklar),
        "bias": round(_bias, 3),
        "yeni_pozitif": len(_yeni_pozitif),
        "yeni_negatif": len(_yeni_negatif),
    }
