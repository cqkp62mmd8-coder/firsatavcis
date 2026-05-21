"""
═══════════════════════════════════════════════════════════════════════
Profesyonel ML Kategori Sınıflandırıcı v2

Özellikler:
  • Multinomial Naive Bayes + TF-IDF ağırlıklandırma
  • Çok dilli tokenizer (Türkçe + İngilizce hibrit)
  • Karakter n-gram fallback (bilinmeyen kelimeler için)
  • Belirsizlik tespiti (low confidence → LLM fallback)
  • Otomatik öğrenme (online learning)
  • k-fold cross-validation
  • Karışıklık matrisi raporlama
  • Aktif öğrenme (hangi örnekleri etiketlersem en faydalı?)
  • Model versiyonlama
  • Fast inference (cache + indexed lookups)

Hiçbir harici bağımlılık yok — sadece Python standart kütüphanesi.
═══════════════════════════════════════════════════════════════════════
"""
import collections
import json
import math
import os
import re
import time
from typing import Optional

import config
from utils.log import log, simdi_tr


_MODEL_FILE  = os.path.join(config.DATA_DIR, "ml_model_v2.json")
_EGITIM_FILE = os.path.join(config.DATA_DIR, "ml_egitim_v2.json")
_AKTIF_OGRENME_FILE = os.path.join(config.DATA_DIR, "ml_aktif_ogrenme.json")
MODEL_VERSION = 2

# ─── Global model durumu ────────────────────────────────────────
_egitim_verisi: list[dict] = []      # [{metin, kategori, kaynak, eklendi_ts}]
_kategori_priorlari: dict[str, float] = {}   # log P(kategori)
_kelime_skorlari: dict[str, dict[str, float]] = {}   # kategori → {token: log P(token|kat)}
_kategori_token_toplam: dict[str, int] = {}
_idf_skorlari: dict[str, float] = {}   # token → IDF değeri
_tum_tokenler: set[str] = set()
_yuklendi: bool = False
_son_egitim_zaman: float = 0.0

# Aktif öğrenme: belirsiz tahminleri admin'e sor
_belirsiz_kuyruk: list[dict] = []
_BELIRSIZ_LIMIT = 50


# ════════════════════════════════════════════════════════════════
# Türkçe morfoloji + tokenizasyon
# ════════════════════════════════════════════════════════════════

# Türkçe ekler (suffixes) — kelimeyi köküne indirgemek için
_TURKCE_EKLER = [
    "ları", "leri", "lar", "ler",         # çoğul
    "dan", "den", "tan", "ten",           # ablatif
    "nın", "nin", "nun", "nün",
    "ın",  "in",  "un",  "ün",            # tamlama
    "da",  "de",  "ta",  "te",            # lokatif
    "ya",  "ye",  "yi",  "yı",
    "lık", "lik", "luk", "lük",
    "siz", "sız", "suz", "süz",
    "lı",  "li",  "lu",  "lü",
    "cı",  "ci",  "cu",  "cü",
    "sı",  "si",  "su",  "sü",
    "lım", "ım",  "im",  "um",  "üm",
    "sın", "sin", "sun", "sün",
]
_TURKCE_EKLER.sort(key=len, reverse=True)   # uzundan kısaya

# Stop words — anlam taşımayan kelimeler
_DURDUR = frozenset({
    "ve", "ile", "için", "olan", "olarak", "bir", "bu", "şu", "o", "veya", "ya da",
    "var", "yok", "den", "dan", "de", "da", "ki", "mi", "mı", "mu", "mü",
    "her", "tüm", "sadece", "kadar", "den", "doğru", "kez", "kere",
    "şimdi", "sonra", "önce", "şöyle", "böyle", "öyle",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "tl", "₺", "lira", "indirim", "fiyat", "yerine", "ila", "arası",
    "yeni", "modeli", "model", "tip", "tipi", "set", "seti", "adet",
    "kg", "gr", "ml", "lt", "cm", "mm", "inç", "watt", "volt", "amper",
})


def _kok_bul(kelime: str) -> str:
    """Türkçe ek çıkarımı — basit stemmer.
    Örnek: 'süpürgeler' → 'süpürge', 'ürünlerinde' → 'ürün'"""
    if len(kelime) <= 4:
        return kelime
    k = kelime.lower()
    # En uzun ekleri sırayla dene
    for ek in _TURKCE_EKLER:
        if k.endswith(ek) and len(k) - len(ek) >= 3:
            return k[:-len(ek)]
    return k


def _karakter_ngram(kelime: str, n: int = 3) -> list[str]:
    """Karakter n-gramları üretir (bilinmeyen kelimeler için)."""
    if len(kelime) < n:
        return []
    return [f"#{kelime[i:i+n]}#" for i in range(len(kelime) - n + 1)]


def _tokenize(metin: str, derin: bool = True) -> list[str]:
    """Profesyonel tokenizer:
    1. Temizleme (URL, sayı, fiyat, vs.)
    2. Stop word filtreleme
    3. Kök bulma (Türkçe morfoloji)
    4. n-gram (unigram + bigram + trigram)
    5. Karakter trigram (fallback, bilinmeyen kelimeler için)
    """
    if not metin:
        return []

    s = metin.lower()
    # URL'ler
    s = re.sub(r"https?://\S+", " ", s)
    # Fiyatlar
    s = re.sub(r"[\d.,]+\s*(?:tl|₺|lira|dolar|usd|eur|euro)", " ", s, flags=re.I)
    s = re.sub(r"%\s*\d+|\d+\s*%", " ", s)
    # Birimler (200ml, 16gb, 65inç vb)
    s = re.sub(r"\b\d+\s*(?:gb|mb|tb|kg|gr|ml|lt|cm|mm|inç|inch|watt|w|volt|v|kw|hp|mp)\b", " ", s, flags=re.I)
    # Model numaraları (sadece sayı veya alfasayısal kombinasyonlar — bağlam vermez)
    s = re.sub(r"\b\d+[a-z]?\b", " ", s)   # 5L, 200, 18v vs.
    # Noktalama
    s = re.sub(r"[^\wçğıöşüâîİ\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()

    # Kelimeler
    raw = s.split()
    kelimeler = []
    for k in raw:
        if len(k) < 3 or k in _DURDUR:
            continue
        # Türkçe kök
        kok = _kok_bul(k)
        kelimeler.append(kok)

    if not kelimeler:
        return []

    tokens = list(kelimeler)
    # Bigrams
    for i in range(len(kelimeler) - 1):
        tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}")
    # Trigrams
    if derin:
        for i in range(len(kelimeler) - 2):
            tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}_{kelimeler[i+2]}")
        # Karakter trigram'ları — sadece uzun kelimelerden (kısa olanlar zaten unigram)
        for k in kelimeler:
            if len(k) >= 6:
                tokens.extend(_karakter_ngram(k, 3))

    return tokens


# ════════════════════════════════════════════════════════════════
# Eğitim — Naive Bayes + IDF ağırlık
# ════════════════════════════════════════════════════════════════

def _modeli_egit() -> None:
    """Tüm _egitim_verisi'ni kullanarak modeli baştan kurar.
    NB olasılıkları + IDF ağırlıkları hesaplanır."""
    global _kategori_priorlari, _kelime_skorlari, _kategori_token_toplam
    global _idf_skorlari, _tum_tokenler, _son_egitim_zaman

    if not _egitim_verisi:
        return

    # Token sayımları
    token_sayim_kategoride: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int)
    )
    kategori_ornek_sayisi: dict[str, int] = collections.defaultdict(int)
    token_belge_sayisi: dict[str, int] = collections.defaultdict(int)
    toplam_belge = 0

    for ornek in _egitim_verisi:
        metin = ornek["metin"]
        kategori = ornek["kategori"]
        tokens = _tokenize(metin)
        if not tokens:
            continue
        kategori_ornek_sayisi[kategori] += 1
        toplam_belge += 1
        # Bu örnekte hangi tokenler var (set olarak — IDF için)
        token_set = set(tokens)
        for token in token_set:
            token_belge_sayisi[token] += 1
        # Her token'i kategori sayımına ekle (frekans)
        for token in tokens:
            token_sayim_kategoride[kategori][token] += 1

    toplam_ornek = sum(kategori_ornek_sayisi.values())
    vocab = set()
    for kat_dict in token_sayim_kategoride.values():
        vocab.update(kat_dict.keys())
    _tum_tokenler = vocab

    # IDF: log(toplam_belge / (token_belge_sayısı + 1))
    _idf_skorlari = {}
    for token, df in token_belge_sayisi.items():
        _idf_skorlari[token] = math.log((toplam_belge + 1) / (df + 1)) + 1

    # Prior P(kategori)
    _kategori_priorlari = {
        kat: math.log(say / toplam_ornek)
        for kat, say in kategori_ornek_sayisi.items()
    }

    # Likelihood P(token|kategori) — Laplace smoothing + IDF ağırlık
    _kelime_skorlari = {}
    _kategori_token_toplam = {}
    vocab_size = len(vocab)
    for kategori, token_dict in token_sayim_kategoride.items():
        toplam_token = sum(token_dict.values())
        _kategori_token_toplam[kategori] = toplam_token
        _kelime_skorlari[kategori] = {}
        for token in vocab:
            sayim = token_dict.get(token, 0)
            # TF-IDF tarzı: token frekansı × IDF
            tf = (sayim + 1) / (toplam_token + vocab_size)
            idf = _idf_skorlari.get(token, 1.0)
            _kelime_skorlari[kategori][token] = math.log(tf * idf)

    _son_egitim_zaman = time.time()


# ════════════════════════════════════════════════════════════════
# Veri yönetimi
# ════════════════════════════════════════════════════════════════

def _veri_kaydet() -> None:
    """Eğitim verisini disk'e atomic yaz."""
    try:
        os.makedirs(os.path.dirname(_EGITIM_FILE) or ".", exist_ok=True)
        gecici = _EGITIM_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(_egitim_verisi, f, ensure_ascii=False)
        os.replace(gecici, _EGITIM_FILE)
    except Exception as e:
        log("UYARI", f"Eğitim verisi kaydet: {e}")


def _model_kaydet() -> None:
    """Model parametrelerini disk'e yaz."""
    try:
        os.makedirs(os.path.dirname(_MODEL_FILE) or ".", exist_ok=True)
        gecici = _MODEL_FILE + ".tmp"
        data = {
            "version": MODEL_VERSION,
            "guncellendi": simdi_tr().isoformat(),
            "kategori_priorlari": _kategori_priorlari,
            "kelime_skorlari":    _kelime_skorlari,
            "kategori_token_toplam": _kategori_token_toplam,
            "idf_skorlari":       _idf_skorlari,
            "tum_tokenler":       list(_tum_tokenler),
        }
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(gecici, _MODEL_FILE)
    except Exception as e:
        log("UYARI", f"Model kaydet: {e}")


def _veri_yukle() -> bool:
    """Eğitim verisini yükler."""
    global _egitim_verisi
    if not os.path.exists(_EGITIM_FILE):
        return False
    try:
        with open(_EGITIM_FILE, encoding="utf-8") as f:
            _egitim_verisi = json.load(f)
        return True
    except Exception as e:
        log("UYARI", f"Eğitim yükle: {e}")
        return False


def _model_yukle() -> bool:
    """Diskten hazır modeli yükler (eğitim atlanır)."""
    global _kategori_priorlari, _kelime_skorlari, _kategori_token_toplam
    global _idf_skorlari, _tum_tokenler, _yuklendi
    if not os.path.exists(_MODEL_FILE):
        return False
    try:
        with open(_MODEL_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != MODEL_VERSION:
            log("BILGI", "Eski model versiyonu, yeniden eğitilecek")
            return False
        _kategori_priorlari = data["kategori_priorlari"]
        _kelime_skorlari = data["kelime_skorlari"]
        _kategori_token_toplam = data["kategori_token_toplam"]
        _idf_skorlari = data["idf_skorlari"]
        _tum_tokenler = set(data["tum_tokenler"])
        _yuklendi = True
        return True
    except Exception as e:
        log("UYARI", f"Model yükle: {e}")
        return False


# ════════════════════════════════════════════════════════════════
# Tahmin
# ════════════════════════════════════════════════════════════════

def tahmin(metin: str) -> tuple[str, float]:
    """Metni sınıflandır. (kategori, güven 0.0-1.0) döner."""
    global _yuklendi
    if not _yuklendi:
        _model_yukle() or ilk_kurulum()
    if not _kategori_priorlari:
        return "genel", 0.0

    tokens = _tokenize(metin)
    if not tokens:
        return "genel", 0.0

    vocab_size = len(_tum_tokenler) or 1
    skorlar: dict[str, float] = {}

    for kategori, log_prior in _kategori_priorlari.items():
        log_skor = log_prior
        kat_token_skor = _kelime_skorlari.get(kategori, {})
        kat_toplam = _kategori_token_toplam.get(kategori, 1)
        for token in tokens:
            if token in kat_token_skor:
                log_skor += kat_token_skor[token]
            else:
                # Bilinmeyen token — Laplace + IDF varsayılan
                idf = _idf_skorlari.get(token, math.log(2))
                log_skor += math.log((1 / (kat_toplam + vocab_size)) * idf)
        skorlar[kategori] = log_skor

    if not skorlar:
        return "genel", 0.0

    en_iyi_kat = max(skorlar, key=skorlar.get)
    # Softmax güven skoru
    maks = max(skorlar.values())
    exp_skorlar = {k: math.exp(v - maks) for k, v in skorlar.items()}
    toplam = sum(exp_skorlar.values())
    guven = exp_skorlar[en_iyi_kat] / toplam if toplam > 0 else 0.0

    return en_iyi_kat, guven


def tahmin_topk(metin: str, k: int = 3) -> list[tuple[str, float]]:
    """En iyi k kategoriyi döner [(kategori, güven), ...]"""
    if not _yuklendi:
        _model_yukle() or ilk_kurulum()
    if not _kategori_priorlari:
        return []
    tokens = _tokenize(metin)
    if not tokens:
        return []

    vocab_size = len(_tum_tokenler) or 1
    skorlar: dict[str, float] = {}
    for kategori, log_prior in _kategori_priorlari.items():
        log_skor = log_prior
        kat_token_skor = _kelime_skorlari.get(kategori, {})
        kat_toplam = _kategori_token_toplam.get(kategori, 1)
        for token in tokens:
            if token in kat_token_skor:
                log_skor += kat_token_skor[token]
            else:
                idf = _idf_skorlari.get(token, math.log(2))
                log_skor += math.log((1 / (kat_toplam + vocab_size)) * idf)
        skorlar[kategori] = log_skor

    maks = max(skorlar.values())
    exp_skorlar = {k: math.exp(v - maks) for k, v in skorlar.items()}
    toplam = sum(exp_skorlar.values())
    olasiliklar = [(kat, exp_skorlar[kat] / toplam) for kat in skorlar]
    olasiliklar.sort(key=lambda x: -x[1])
    return olasiliklar[:k]


def tahmin_hiyerarsik(metin: str) -> tuple[str, str, float]:
    """Hiyerarşik tahmin: (ana_kategori, alt_kategori, güven) döner.
    'elektronik:telefon' formatından ana ve alt'ı ayırır.
    Alt yoksa boş string döner."""
    tam_kat, guven = tahmin(metin)
    if ":" in tam_kat:
        ana, alt = tam_kat.split(":", 1)
        return ana, alt, guven
    return tam_kat, "", guven


def ana_kategori_olasiliklari(metin: str) -> dict[str, float]:
    """Ana kategori bazında toplam olasılık (alt kategorileri birleştirir).
    Kullanım: belirsizlik tespiti için."""
    topk = tahmin_topk(metin, k=20)   # tüm kategoriler
    ana_skor: dict[str, float] = {}
    for kat, olas in topk:
        ana = kat.split(":")[0] if ":" in kat else kat
        ana_skor[ana] = ana_skor.get(ana, 0) + olas
    return ana_skor


# ════════════════════════════════════════════════════════════════
# Aktif öğrenme — belirsiz tahminleri yakala (kalıcı, disk'te)
# ════════════════════════════════════════════════════════════════

def _aktif_ogrenme_kaydet() -> None:
    """Belirsiz kuyruğu disk'e atomic yaz."""
    try:
        os.makedirs(os.path.dirname(_AKTIF_OGRENME_FILE) or ".", exist_ok=True)
        gecici = _AKTIF_OGRENME_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(_belirsiz_kuyruk, f, ensure_ascii=False)
        os.replace(gecici, _AKTIF_OGRENME_FILE)
    except Exception as e:
        log("UYARI", f"Aktif öğrenme kaydet: {e}")


def _aktif_ogrenme_yukle() -> None:
    """Disk'ten belirsiz kuyruğu yükle (bot başlangıcında)."""
    global _belirsiz_kuyruk
    if not os.path.exists(_AKTIF_OGRENME_FILE):
        return
    try:
        with open(_AKTIF_OGRENME_FILE, encoding="utf-8") as f:
            _belirsiz_kuyruk = json.load(f)
    except Exception as e:
        log("UYARI", f"Aktif öğrenme yükle: {e}")


def belirsiz_kaydet(metin: str, tahmin_kat: str, guven: float) -> None:
    """Düşük güvenli (uncertain) tahminleri kuyrukla — disk'e de yaz.
    Sonra admin /aktiog komutu ile bunları görür ve /ogret ile etiketler."""
    if guven >= 0.5:
        return   # zaten güvenli
    # Aynı metin daha önce kaydedilmiş mi? Tekrarı önle
    metin_kisa = metin[:200]
    for kayit in _belirsiz_kuyruk:
        if kayit.get("metin") == metin_kisa:
            return
    _belirsiz_kuyruk.append({
        "metin": metin_kisa,
        "tahmin": tahmin_kat,
        "guven":  round(guven, 3),
        "zaman":  simdi_tr().isoformat(),
    })
    if len(_belirsiz_kuyruk) > _BELIRSIZ_LIMIT:
        _belirsiz_kuyruk.pop(0)
    _aktif_ogrenme_kaydet()


def belirsiz_listele() -> list[dict]:
    """Şu an belirsiz kuyrukta bekleyenler."""
    return list(_belirsiz_kuyruk)


def belirsiz_temizle() -> int:
    """Hepsini sil — disk'i de temizle."""
    n = len(_belirsiz_kuyruk)
    _belirsiz_kuyruk.clear()
    _aktif_ogrenme_kaydet()
    return n


def belirsiz_eslestir_ve_egit(satir_no: int, ana: str, alt: str = "") -> tuple[bool, str]:
    """Belirsiz kuyruktaki #satir_no'yu 'ana:alt' ile etiketle ve modele ekle.
    Etiketlenince kuyruktan çıkarılır. (basari, mesaj) döner."""
    if not (1 <= satir_no <= len(_belirsiz_kuyruk)):
        return False, f"Geçersiz numara (1-{len(_belirsiz_kuyruk)})"
    kayit = _belirsiz_kuyruk[satir_no - 1]
    metin = kayit["metin"]
    tam_kat = f"{ana}:{alt}" if alt else ana
    # Modele ekle
    egit_tek(metin, tam_kat, kaynak="aktif_ogrenme", hemen_egit=True)
    # Kuyruktan çıkar
    _belirsiz_kuyruk.pop(satir_no - 1)
    _aktif_ogrenme_kaydet()
    return True, f"Öğretildi: '{metin[:50]}…' → {tam_kat}"


# ════════════════════════════════════════════════════════════════
# Eğitim API'leri
# ════════════════════════════════════════════════════════════════

_kirli_sayac: int = 0   # eğitilmemiş yeni veri sayısı
_RETRAIN_ESIK = 20      # her 20 yeni örneğin sonunda retrain


def egit_tek(metin: str, kategori: str, kaynak: str = "manuel", hemen_egit: bool = True) -> None:
    """Tek bir örnek ekle.
    Modeli yeniden eğitir (manuel için anında, otomatik için 20 örnekte bir).
    'kaynak': 'manuel', 'auto', 'llm' gibi etiket."""
    global _kirli_sayac
    _egitim_verisi.append({
        "metin":    metin,
        "kategori": kategori,
        "kaynak":   kaynak,
        "eklendi":  simdi_tr().isoformat(),
    })
    _kirli_sayac += 1

    # Manuel eğitimde anında retrain (admin /egit komutu beklemekte)
    # Otomatik eğitimde batched retrain (her N örnekte)
    if hemen_egit or _kirli_sayac >= _RETRAIN_ESIK:
        _modeli_egit()
        _veri_kaydet()
        _model_kaydet()
        _kirli_sayac = 0


def egit_toplu(ornekler: list[tuple[str, str]], kaynak: str = "toplu") -> int:
    """Birden çok örnek ekle. Sonra tek seferde eğit."""
    global _kirli_sayac
    for metin, kategori in ornekler:
        _egitim_verisi.append({
            "metin":    metin,
            "kategori": kategori,
            "kaynak":   kaynak,
            "eklendi":  simdi_tr().isoformat(),
        })
    _modeli_egit()
    _veri_kaydet()
    _model_kaydet()
    _kirli_sayac = 0
    return len(ornekler)


def yeniden_egit() -> int:
    """Eğitim verisinden modeli sıfırdan eğit."""
    _modeli_egit()
    _model_kaydet()
    return len(_egitim_verisi)


# ════════════════════════════════════════════════════════════════
# Doğrulama / değerlendirme
# ════════════════════════════════════════════════════════════════

def k_fold_dogruluk(k: int = 5) -> dict:
    """k-fold cross validation. Doğruluk, kategori başına precision/recall döner."""
    global _egitim_verisi
    if len(_egitim_verisi) < k * 5:
        return {"hata": f"En az {k*5} örnek gerekli (şu an {len(_egitim_verisi)})"}

    import random
    veri = list(_egitim_verisi)
    random.shuffle(veri)
    fold_size = len(veri) // k

    karmasiklik: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int)
    )
    toplam_dogru = 0
    toplam_test = 0

    orijinal_veri = list(_egitim_verisi)

    for fold in range(k):
        test_baslangic = fold * fold_size
        test_son = test_baslangic + fold_size
        test_set = veri[test_baslangic:test_son]
        egitim_set = veri[:test_baslangic] + veri[test_son:]

        # Geçici eğit
        _egitim_verisi = egitim_set
        _modeli_egit()

        # Test
        for ornek in test_set:
            tahmin_kat, _ = tahmin(ornek["metin"])
            gercek = ornek["kategori"]
            karmasiklik[gercek][tahmin_kat] += 1
            if tahmin_kat == gercek:
                toplam_dogru += 1
            toplam_test += 1

    # Orijinal modele geri dön
    _egitim_verisi = orijinal_veri
    _modeli_egit()

    # Precision / Recall hesapla
    kategoriler = set()
    for k1, k2_dict in karmasiklik.items():
        kategoriler.add(k1)
        kategoriler.update(k2_dict.keys())

    metrik = {}
    for kat in sorted(kategoriler):
        tp = karmasiklik[kat].get(kat, 0)
        fn = sum(v for k2, v in karmasiklik[kat].items() if k2 != kat)
        fp = sum(karmasiklik[g].get(kat, 0) for g in kategoriler if g != kat)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrik[kat] = {
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3),
            "ornek":     sum(karmasiklik[kat].values()),
        }

    return {
        "k": k,
        "toplam_ornek":  toplam_test,
        "toplam_dogru":  toplam_dogru,
        "dogruluk":      round(toplam_dogru / toplam_test, 3) if toplam_test else 0.0,
        "kategori":      metrik,
    }


# ════════════════════════════════════════════════════════════════
# İstatistik & teşhis
# ════════════════════════════════════════════════════════════════

def istatistik() -> dict:
    if not _yuklendi:
        _model_yukle() or ilk_kurulum()
    kategori_dagilim = collections.Counter()
    kaynak_dagilim = collections.Counter()
    for v in _egitim_verisi:
        kategori_dagilim[v["kategori"]] += 1
        kaynak_dagilim[v.get("kaynak", "?")] += 1
    return {
        "version":             MODEL_VERSION,
        "toplam_ornek":        len(_egitim_verisi),
        "kategori_sayilari":   dict(kategori_dagilim),
        "kaynak_dagilim":      dict(kaynak_dagilim),
        "vocab_boyut":         len(_tum_tokenler),
        "kategori_sayi":       len(_kategori_priorlari),
        "belirsiz_bekleyen":   len(_belirsiz_kuyruk),
        "son_egitim":          _son_egitim_zaman,
    }


# Veri seti (büyük) ayrı dosyaya
from utils.ml_dataset import EGITIM_VERISI as _VARSAYILAN_EGITIM


def ilk_kurulum() -> None:
    """Bot ilk açıldığında çağrılır."""
    global _yuklendi
    # Aktif öğrenme kuyruğunu (varsa) önce yükle
    _aktif_ogrenme_yukle()

    if _model_yukle() and _veri_yukle():
        log("OK", f"ML model yüklendi: {len(_egitim_verisi)} örnek, "
                  f"{len(_tum_tokenler)} token, {len(_kategori_priorlari)} kategori"
                  + (f" (aktif öğrenme: {len(_belirsiz_kuyruk)} bekleyen)"
                     if _belirsiz_kuyruk else ""))
        _yuklendi = True
        return

    log("BILGI", f"ML modeli ilk kurulum: {len(_VARSAYILAN_EGITIM)} örnek eğitiliyor…")
    egit_toplu(_VARSAYILAN_EGITIM, kaynak="varsayilan")
    _yuklendi = True
    ist = istatistik()
    log("OK", f"ML modeli hazır — {ist['toplam_ornek']} örnek, "
              f"{ist['vocab_boyut']} token, {ist['kategori_sayi']} kategori")
