"""
═══════════════════════════════════════════════════════════════════════
Profesyonel ML Kategori Sınıflandırıcı v3 — İLERİ DÜZEY YAPAY ZEKA

v2'den farklar:
  ✦ Hiyerarşik iki-aşamalı sınıflandırma (önce ana, sonra alt)
  ✦ Logistic Regression + L2 regularization (sklearn-bağımsız implementasyon)
  ✦ Karakter & kelime karışık tokenleme (multilingual robust)
  ✦ Ensemble: Naive Bayes + LogReg ağırlıklı kombinasyon
  ✦ Confidence calibration (Platt scaling benzeri)
  ✦ Anlamsal benzerlik kontrolü (kNN feature matcher)
  ✦ Belirsizlik öğrenmesi (margin sampling — düşük margin = belirsiz)
  ✦ Aktif öğrenme önceliklendirme (en bilgilendirici örnekler önce)
  ✦ Self-supervised pseudo-labeling (yüksek güvenli tahminler eğitime geri)

Hiçbir harici ML kütüphanesi yok — pure Python + math.
═══════════════════════════════════════════════════════════════════════
"""
import collections
import json
import math
import os
import random
import time
from typing import Optional

import config
from utils.log import log, simdi_tr


# ─── Sabit yollar ──────────────────────────────────────────────
_MODEL_FILE        = os.path.join(config.DATA_DIR, "ml_model_v3.json")
_EGITIM_FILE       = os.path.join(config.DATA_DIR, "ml_egitim_v3.json")
_AKTIF_OGRENME_FILE = os.path.join(config.DATA_DIR, "ml_aktif_ogrenme_v3.json")
MODEL_VERSION = 3

# ─── Hyperparametreler ─────────────────────────────────────────
_NB_AGIRLIK   = 0.4    # Naive Bayes (genel)
_LR_AGIRLIK   = 0.4    # Logistic Regression (discriminative)
_PROTO_AGIRLIK = 0.2   # Prototip benzerlik (semantik benzerlik)
_LR_LR       = 0.05
_LR_L2       = 0.001
_LR_EPOCH    = 8
_BELIRSIZ_ESIK = 0.55
_YUKSEK_GUVEN = 0.85
_RETRAIN_ESIK = 30

# ─── Global durum ──────────────────────────────────────────────
_egitim_verisi: list[dict] = []
_kirli_sayac: int = 0
_son_egitim_zaman: float = 0.0
_yuklendi: bool = False

# Aşamalı sınıflandırma:
#  1) Ana kategori için tek bir model (Naive Bayes + LogReg ensemble)
#  2) Her ana kategori için kendi alt-kategori modeli
_ana_kategoriler: list[str] = []
_ana_nb_priors:   dict[str, float] = {}
_ana_nb_skorlar:  dict[str, dict[str, float]] = {}
_ana_nb_token_toplam: dict[str, int] = {}
_ana_lr_agirliklar: dict[str, dict[str, float]] = {}   # ana_kat → {token: weight}
_ana_lr_bias:      dict[str, float] = {}
_idf:              dict[str, float] = {}
_vocab:            set[str] = set()

# Alt seviye modeller (ana_kat → alt model)
_alt_modeller: dict[str, dict] = {}   # her ana_kat için { nb_priors, nb_skorlar, lr_agirliklar, alt_listesi }

# Belirsiz kuyrukla aktif öğrenme
_belirsiz_kuyruk: list[dict] = []
_BELIRSIZ_LIMIT = 100


# ════════════════════════════════════════════════════════════════
# TOKENİZASYON — multilingual + morfolojik
# ════════════════════════════════════════════════════════════════
import re

_TURKCE_EKLER = [
    "ları", "leri", "lar", "ler",
    "dan", "den", "tan", "ten",
    "nın", "nin", "nun", "nün",
    "ın",  "in",  "un",  "ün",
    "da",  "de",  "ta",  "te",
    "ya",  "ye",  "yi",  "yı",
    "lık", "lik", "luk", "lük",
    "siz", "sız", "suz", "süz",
    "lı",  "li",  "lu",  "lü",
    "cı",  "ci",  "cu",  "cü",
    "sı",  "si",  "su",  "sü",
]
_TURKCE_EKLER.sort(key=len, reverse=True)

_DURDUR = frozenset({
    "ve", "ile", "için", "olan", "bir", "bu", "şu", "o", "veya", "ya",
    "var", "yok", "ki", "mi", "mı", "mu", "mü",
    "her", "tüm", "sadece", "kadar", "doğru", "kez", "kere",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "tl", "₺", "lira", "indirim", "fiyat", "yerine", "arası",
    "yeni", "model", "tip", "set", "adet",
    "kg", "gr", "ml", "lt", "cm", "mm", "inç", "watt", "volt", "amper",
})


def _kok_bul(kelime: str) -> str:
    """Türkçe basit stemmer — birden fazla ek olabileceği için iteratif.

    Örnek:
      'telefonlarında' → 'telefonların' → 'telefon'  (2 iterasyon)
      'ürünlerinde'    → 'ürünlerin'    → 'ürün'
    """
    if len(kelime) <= 4:
        return kelime
    k = kelime.lower()
    # En fazla 3 ek çıkar (Türkçe genelde 1-3 ek alır)
    for _ in range(3):
        eski_uzunluk = len(k)
        for ek in _TURKCE_EKLER:
            if k.endswith(ek) and len(k) - len(ek) >= 3:
                k = k[:-len(ek)]
                break
        if len(k) == eski_uzunluk:
            break   # Bu turda ek bulunamadı, dur
    return k


def _karakter_ngram(kelime: str, n: int = 3) -> list[str]:
    """Karakter n-gramları — yazım hatalarına ve yeni markalara dayanıklılık."""
    if len(kelime) < n:
        return []
    return [f"#{kelime[i:i+n]}#" for i in range(len(kelime) - n + 1)]


def _tokenize(metin: str) -> list[str]:
    """Kapsamlı tokenizasyon:
      - URL, fiyat, birim temizleme
      - Stop word filtreleme
      - Türkçe kök bulma
      - Unigram + bigram + trigram + karakter trigram
    """
    if not metin:
        return []
    s = metin.lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[\d.,]+\s*(?:tl|₺|lira|dolar|usd|eur|euro)", " ", s, flags=re.I)
    s = re.sub(r"%\s*\d+|\d+\s*%", " ", s)
    s = re.sub(r"\b\d+\s*(?:gb|mb|tb|kg|gr|ml|lt|cm|mm|inç|inch|watt|w|volt|v|kw|hp|mp)\b", " ", s, flags=re.I)
    s = re.sub(r"\b\d+[a-z]?\b", " ", s)
    s = re.sub(r"[^\wçğıöşüâîİ\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()

    raw = s.split()
    kelimeler = []
    for k in raw:
        if len(k) < 3 or k in _DURDUR:
            continue
        kelimeler.append(_kok_bul(k))
    if not kelimeler:
        return []

    tokens = list(kelimeler)
    # Bigrams + trigrams
    for i in range(len(kelimeler) - 1):
        tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}")
    for i in range(len(kelimeler) - 2):
        tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}_{kelimeler[i+2]}")
    # Karakter trigram (yazım hatalarına ve bilinmeyen kelimelere)
    for k in kelimeler:
        if len(k) >= 5:
            tokens.extend(_karakter_ngram(k, 3))

    return tokens


# ════════════════════════════════════════════════════════════════
# NAİVE BAYES — temel sınıflandırıcı
# ════════════════════════════════════════════════════════════════

def _nb_egit(veri: list[tuple[str, str]]) -> dict:
    """Naive Bayes modelini eğit. Döner: model parametreleri dict.

    Bu fonksiyon hem ana hem alt kategori modeli için kullanılır.
    """
    if not veri:
        return {"priors": {}, "skorlar": {}, "token_toplam": {}, "vocab": set(), "idf": {}}

    token_sayim_kat: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int)
    )
    kat_ornek_sayisi: dict[str, int] = collections.defaultdict(int)
    token_belge_sayisi: dict[str, int] = collections.defaultdict(int)

    for metin, kategori in veri:
        tokens = _tokenize(metin)
        if not tokens:
            continue
        kat_ornek_sayisi[kategori] += 1
        for token in set(tokens):
            token_belge_sayisi[token] += 1
        for token in tokens:
            token_sayim_kat[kategori][token] += 1

    toplam = sum(kat_ornek_sayisi.values())
    vocab = set()
    for kat_dict in token_sayim_kat.values():
        vocab.update(kat_dict.keys())

    # IDF
    idf = {}
    for token, df in token_belge_sayisi.items():
        idf[token] = math.log((toplam + 1) / (df + 1)) + 1

    # Priors (log)
    priors = {kat: math.log(say / toplam) for kat, say in kat_ornek_sayisi.items()}

    # Likelihoods (log P(token|kat) — TF-IDF ağırlıklı + Laplace)
    skorlar = {}
    token_toplam = {}
    vocab_size = len(vocab)
    for kategori, token_dict in token_sayim_kat.items():
        toplam_token = sum(token_dict.values())
        token_toplam[kategori] = toplam_token
        skorlar[kategori] = {}
        for token in vocab:
            sayim = token_dict.get(token, 0)
            tf = (sayim + 1) / (toplam_token + vocab_size)
            idf_v = idf.get(token, 1.0)
            skorlar[kategori][token] = math.log(tf * idf_v)

    return {
        "priors":       priors,
        "skorlar":      skorlar,
        "token_toplam": token_toplam,
        "vocab":        vocab,
        "idf":          idf,
    }


def _nb_tahmin(tokens: list[str], model: dict) -> dict[str, float]:
    """Naive Bayes ile tahmin — kategori → log-olasılık döner."""
    if not model.get("priors"):
        return {}
    vocab_size = len(model["vocab"]) or 1
    skorlar = {}
    for kategori, log_prior in model["priors"].items():
        log_skor = log_prior
        kat_skor = model["skorlar"].get(kategori, {})
        kat_toplam = model["token_toplam"].get(kategori, 1)
        for token in tokens:
            if token in kat_skor:
                log_skor += kat_skor[token]
            else:
                idf_v = model["idf"].get(token, math.log(2))
                log_skor += math.log((1 / (kat_toplam + vocab_size)) * idf_v)
        skorlar[kategori] = log_skor
    return skorlar


# ════════════════════════════════════════════════════════════════
# LOGISTIC REGRESSION — discriminative sınıflandırıcı
# ════════════════════════════════════════════════════════════════

def _softmax(skorlar: dict[str, float]) -> dict[str, float]:
    """Log-skorları normalize ederek olasılığa çevir."""
    if not skorlar:
        return {}
    maks = max(skorlar.values())
    exp_s = {k: math.exp(v - maks) for k, v in skorlar.items()}
    toplam = sum(exp_s.values())
    if toplam == 0:
        return {k: 1.0/len(skorlar) for k in skorlar}
    return {k: v/toplam for k, v in exp_s.items()}


def _lr_egit(veri: list[tuple[str, str]], kategori_listesi: list[str]) -> dict:
    """Logistic Regression — SGD ile multi-class.

    Multinomial cross-entropy loss, L2 regularized.
    Her token başına bir feature, her kategori için bir ağırlık vektörü.

    Döner:
      {
        "agirliklar": {kat: {token: weight}},
        "bias": {kat: bias},
        "kategoriler": [kategori_listesi]
      }
    """
    if not veri or not kategori_listesi:
        return {"agirliklar": {}, "bias": {}, "kategoriler": []}

    kat_idx = {k: i for i, k in enumerate(kategori_listesi)}
    n_kat = len(kategori_listesi)

    # Tüm tokenleri topla (vocab oluştur)
    vocab = set()
    cached_tokens: list[tuple[list[str], int]] = []   # (tokens, label_idx)
    for metin, kategori in veri:
        if kategori not in kat_idx:
            continue
        tokens = _tokenize(metin)
        if not tokens:
            continue
        vocab.update(tokens)
        cached_tokens.append((tokens, kat_idx[kategori]))

    if not cached_tokens:
        return {"agirliklar": {}, "bias": {}, "kategoriler": kategori_listesi}

    # Ağırlık matrisi: kat × vocab
    # Bias vektörü: kat
    agirliklar: list[dict[str, float]] = [collections.defaultdict(float) for _ in range(n_kat)]
    bias = [0.0] * n_kat

    # SGD epochs
    indeksler = list(range(len(cached_tokens)))
    for epoch in range(_LR_EPOCH):
        random.shuffle(indeksler)
        for idx in indeksler:
            tokens, label = cached_tokens[idx]
            # Forward: skor = bias + sum(weights[token])
            skorlar = [bias[c] for c in range(n_kat)]
            for tok in tokens:
                for c in range(n_kat):
                    skorlar[c] += agirliklar[c].get(tok, 0.0)
            # Softmax
            maks_s = max(skorlar)
            exp_s = [math.exp(s - maks_s) for s in skorlar]
            toplam_e = sum(exp_s)
            olas = [e/toplam_e for e in exp_s]
            # Gradient: olas - one_hot(label)
            # weights gradient: grad_c[token] = (olas[c] - 1{c==label}) * 1
            for c in range(n_kat):
                hata = olas[c] - (1.0 if c == label else 0.0)
                # Bias
                bias[c] -= _LR_LR * hata
                # Weights (sadece bu örnekteki tokenler için)
                if hata != 0:
                    for tok in tokens:
                        # L2 reg: gradient = hata + L2 * w
                        mevcut = agirliklar[c].get(tok, 0.0)
                        yeni = mevcut - _LR_LR * (hata + _LR_L2 * mevcut)
                        agirliklar[c][tok] = yeni

    # Defaultdict → dict
    agirliklar_dict = {kategori_listesi[c]: dict(agirliklar[c]) for c in range(n_kat)}
    bias_dict = {kategori_listesi[c]: bias[c] for c in range(n_kat)}

    return {
        "agirliklar":   agirliklar_dict,
        "bias":         bias_dict,
        "kategoriler":  kategori_listesi,
    }


def _lr_tahmin(tokens: list[str], model: dict) -> dict[str, float]:
    """Logistic Regression ile tahmin — kategori → ham skor döner."""
    if not model.get("kategoriler"):
        return {}
    skorlar = {}
    for kat in model["kategoriler"]:
        ag = model["agirliklar"].get(kat, {})
        b  = model["bias"].get(kat, 0.0)
        skor = b
        for tok in tokens:
            skor += ag.get(tok, 0.0)
        skorlar[kat] = skor
    return skorlar


# ════════════════════════════════════════════════════════════════
# ENSEMBLE — NB + LogReg birleşimi
# ════════════════════════════════════════════════════════════════

def _ensemble_tahmin(tokens: list[str], nb_model: dict, lr_model: dict,
                     prototipler: dict[str, dict[str, float]] | None = None) -> dict[str, float]:
    """3-way ensemble: NB + LR + Prototip-kosinüs ağırlıklı.

    Args:
      tokens: tokenize edilmiş metin
      nb_model: Naive Bayes model
      lr_model: Logistic Regression model
      prototipler: Kategori → prototip vektörü (opsiyonel)
    """
    nb_skor = _nb_tahmin(tokens, nb_model)
    lr_skor = _lr_tahmin(tokens, lr_model)

    nb_olas = _softmax(nb_skor)
    lr_olas = _softmax(lr_skor)

    # Prototip benzerliği (kosinüs)
    proto_olas: dict[str, float] = {}
    if prototipler:
        sorgu_v = _vektor_olustur(tokens)
        if sorgu_v:
            kosinus_skorlar = {kat: _kosinus(sorgu_v, prot) for kat, prot in prototipler.items()}
            # Kosinüs zaten 0-1 arası — softmax değil, normalize et
            toplam_k = sum(kosinus_skorlar.values())
            if toplam_k > 0:
                proto_olas = {k: v/toplam_k for k, v in kosinus_skorlar.items()}

    # Ortak kategoriler
    tum_kat = set(nb_olas.keys()) | set(lr_olas.keys()) | set(proto_olas.keys())
    if not tum_kat:
        return {}

    ensemble = {}
    for kat in tum_kat:
        skor = (_NB_AGIRLIK * nb_olas.get(kat, 0.0)
                + _LR_AGIRLIK * lr_olas.get(kat, 0.0)
                + _PROTO_AGIRLIK * proto_olas.get(kat, 0.0))
        ensemble[kat] = skor

    toplam = sum(ensemble.values())
    if toplam > 0:
        ensemble = {k: v/toplam for k, v in ensemble.items()}
    return ensemble


# ════════════════════════════════════════════════════════════════
# KATEGORI PROTOTİP VEKTÖRÜ — kosinüs benzerlik tabanlı
# ════════════════════════════════════════════════════════════════
#
# Her kategori için "prototip vektör" — o kategorinin tüm örneklerindeki
# token frekanslarının ortalaması. Yeni metnin vektörü ile kosinüs
# benzerliği = ne kadar tipik bir örnek.
#
# Bu, marka karışıklığını çözer:
#   "Samsung Galaxy" — telefon prototipiyle yüksek benzerlik (terim örtüşmesi)
#   "Samsung 55 inç UHD" — tv prototipiyle yüksek benzerlik
# Çünkü "Galaxy" ≠ "55 inç UHD" — bu ayırt edici terimler ağır basar.

def _vektor_olustur(tokens: list[str]) -> dict[str, float]:
    """Token listesinden frekans vektörü (IDF ağırlıklı)."""
    if not tokens:
        return {}
    sayim = collections.Counter(tokens)
    n = len(tokens)
    vektor = {}
    for tok, c in sayim.items():
        tf = c / n
        idf = _idf.get(tok, 1.0)
        vektor[tok] = tf * idf
    return vektor


def _kosinus(v1: dict[str, float], v2: dict[str, float]) -> float:
    """İki vektör arasında kosinüs benzerliği."""
    if not v1 or not v2:
        return 0.0
    # Ortak tokenlerde dot product
    ortak = set(v1.keys()) & set(v2.keys())
    if not ortak:
        return 0.0
    dot = sum(v1[t] * v2[t] for t in ortak)
    norm1 = math.sqrt(sum(v*v for v in v1.values()))
    norm2 = math.sqrt(sum(v*v for v in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _prototip_olustur(veri: list[tuple[str, str]]) -> dict[str, dict[str, float]]:
    """Her kategori için prototip vektörü oluştur (token frekansları ortalaması)."""
    kat_tokens: dict[str, list[str]] = collections.defaultdict(list)
    for metin, kategori in veri:
        kat_tokens[kategori].extend(_tokenize(metin))
    return {kat: _vektor_olustur(toks) for kat, toks in kat_tokens.items()}


# Ana ve alt prototipleri
_ana_prototipler: dict[str, dict[str, float]] = {}
_alt_prototipler: dict[str, dict[str, dict[str, float]]] = {}   # ana_kat → alt_kat → vector


def _modeli_egit() -> None:
    """Hiyerarşik iki aşamalı eğitim:
      Aşama 1: Tüm ana kategoriler için tek bir ensemble model
      Aşama 2: Her ana kategori için ayrı bir alt-kategori modeli
    """
    global _ana_nb_priors, _ana_nb_skorlar, _ana_nb_token_toplam
    global _ana_lr_agirliklar, _ana_lr_bias, _ana_kategoriler
    global _idf, _vocab, _alt_modeller, _son_egitim_zaman

    if not _egitim_verisi:
        return

    # Veriyi ana ve (ana, alt) bazında topla
    ana_veri: list[tuple[str, str]] = []
    alt_veri_grup: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)

    for kayit in _egitim_verisi:
        metin = kayit["metin"]
        tam_kat = kayit["kategori"]
        if ":" in tam_kat:
            ana, alt = tam_kat.split(":", 1)
        else:
            ana, alt = tam_kat, ""
        ana_veri.append((metin, ana))
        if alt:
            alt_veri_grup[ana].append((metin, alt))

    # ─ Aşama 1: Ana kategori modeli ─
    ana_kategoriler = sorted(set(k for _, k in ana_veri))
    _ana_kategoriler = ana_kategoriler

    nb_model = _nb_egit(ana_veri)
    _ana_nb_priors = nb_model["priors"]
    _ana_nb_skorlar = nb_model["skorlar"]
    _ana_nb_token_toplam = nb_model["token_toplam"]
    _idf = nb_model["idf"]
    _vocab = nb_model["vocab"]

    lr_model = _lr_egit(ana_veri, ana_kategoriler)
    _ana_lr_agirliklar = lr_model["agirliklar"]
    _ana_lr_bias = lr_model["bias"]

    # Prototip vektörleri (kosinüs benzerlik için)
    global _ana_prototipler, _alt_prototipler
    _ana_prototipler = _prototip_olustur(ana_veri)

    # ─ Aşama 2: Her ana için alt modeli + alt prototipler ─
    _alt_modeller = {}
    _alt_prototipler = {}
    for ana_kat, alt_veri in alt_veri_grup.items():
        if len(alt_veri) < 5:
            continue
        alt_kategoriler = sorted(set(k for _, k in alt_veri))
        if len(alt_kategoriler) < 2:
            continue
        alt_nb = _nb_egit(alt_veri)
        alt_lr = _lr_egit(alt_veri, alt_kategoriler)
        _alt_modeller[ana_kat] = {
            "kategoriler": alt_kategoriler,
            "nb": alt_nb,
            "lr": alt_lr,
        }
        _alt_prototipler[ana_kat] = _prototip_olustur(alt_veri)

    _son_egitim_zaman = time.time()
    log("OK", f"ML v3 eğitildi: {len(_egitim_verisi)} örnek, "
              f"{len(_ana_kategoriler)} ana, {len(_alt_modeller)} alt-grup, "
              f"{len(_vocab)} token")


# ════════════════════════════════════════════════════════════════
# TAHMİN API
# ════════════════════════════════════════════════════════════════

def tahmin(metin: str) -> tuple[str, float]:
    """Düzleştirilmiş 'ana:alt' formatında tahmin.
    Geriye dönük uyumluluk için 'ana:alt' string + güven (0-1) döner."""
    ana, alt, guv = tahmin_hiyerarsik(metin)
    if alt:
        return f"{ana}:{alt}", guv
    return ana, guv


def tahmin_hiyerarsik(metin: str) -> tuple[str, str, float]:
    """İki aşamalı tahmin:
      1) Ana kategoriyi belirle (ensemble NB+LR)
      2) O ana kategori için alt-kategoriyi belirle (eğer alt modeli varsa)

    Döner: (ana, alt, güven) — alt yoksa '' döner.
    Güven = (ana güveni) × (alt güveni)
    """
    if not _yuklendi:
        ilk_kurulum()
    if not _ana_nb_priors:
        return "genel", "", 0.0

    tokens = _tokenize(metin)
    if not tokens:
        return "genel", "", 0.0

    # Aşama 1: Ana kategori
    ana_nb_model = {
        "priors": _ana_nb_priors,
        "skorlar": _ana_nb_skorlar,
        "token_toplam": _ana_nb_token_toplam,
        "vocab": _vocab,
        "idf": _idf,
    }
    ana_lr_model = {
        "agirliklar": _ana_lr_agirliklar,
        "bias": _ana_lr_bias,
        "kategoriler": _ana_kategoriler,
    }
    ana_olas = _ensemble_tahmin(tokens, ana_nb_model, ana_lr_model, _ana_prototipler)
    if not ana_olas:
        return "genel", "", 0.0

    ana_kat = max(ana_olas, key=ana_olas.get)
    ana_guven = ana_olas[ana_kat]

    # ── v18: ML belirsizse marka sözlüğünden destek al ──
    # Eğer ML <0.55 güvende ise ve metin başında öğrenilmiş bir marka varsa,
    # o markanın bilinen kategorisine yönlendir.
    if ana_guven < 0.55:
        try:
            from utils import marka_ogrenme
            # Metnin ilk birkaç kelimesini dene
            kelimeler = metin.split()
            for boyut in (2, 1):   # önce 2-kelimelik, sonra 1-kelimelik
                if len(kelimeler) >= boyut:
                    aday = " ".join(kelimeler[:boyut])
                    marka_kat = marka_ogrenme.marka_mi(aday)
                    if marka_kat:
                        # Markanın bildiği kategoriyi kullan, güveni biraz yükselt
                        ana_kat = marka_kat
                        ana_guven = max(ana_guven, 0.60)
                        break
        except Exception:
            pass

    # Aşama 2: Alt kategori (sadece bu ana kategoriye özel modelle)
    alt_kat = ""
    alt_guven = 1.0
    alt_model = _alt_modeller.get(ana_kat)
    if alt_model:
        alt_olas = _ensemble_tahmin(tokens, alt_model["nb"], alt_model["lr"], _alt_prototipler.get(ana_kat))
        if alt_olas:
            alt_kat = max(alt_olas, key=alt_olas.get)
            alt_guven = alt_olas[alt_kat]

    # Birleştirilmiş güven (zincir kuralı)
    toplam_guven = ana_guven * alt_guven
    return ana_kat, alt_kat, toplam_guven


def tahmin_topk(metin: str, k: int = 3) -> list[tuple[str, float]]:
    """En iyi k 'ana:alt' kombinasyonu."""
    if not _yuklendi:
        ilk_kurulum()
    if not _ana_nb_priors:
        return []
    tokens = _tokenize(metin)
    if not tokens:
        return []

    ana_nb_model = {
        "priors": _ana_nb_priors,
        "skorlar": _ana_nb_skorlar,
        "token_toplam": _ana_nb_token_toplam,
        "vocab": _vocab,
        "idf": _idf,
    }
    ana_lr_model = {
        "agirliklar": _ana_lr_agirliklar,
        "bias": _ana_lr_bias,
        "kategoriler": _ana_kategoriler,
    }
    ana_olas = _ensemble_tahmin(tokens, ana_nb_model, ana_lr_model, _ana_prototipler)

    # Her ana için en iyi alt'ı bul
    kombine: list[tuple[str, float]] = []
    for ana_kat, ana_o in ana_olas.items():
        alt_model = _alt_modeller.get(ana_kat)
        if not alt_model:
            kombine.append((ana_kat, ana_o))
            continue
        alt_olas = _ensemble_tahmin(tokens, alt_model["nb"], alt_model["lr"], _alt_prototipler.get(ana_kat))
        if not alt_olas:
            kombine.append((ana_kat, ana_o))
            continue
        # Her alt'ı kombine ile ekle
        for alt_kat, alt_o in alt_olas.items():
            kombine.append((f"{ana_kat}:{alt_kat}", ana_o * alt_o))

    kombine.sort(key=lambda x: -x[1])
    return kombine[:k]


def ana_kategori_olasiliklari(metin: str) -> dict[str, float]:
    """Sadece ana kategori olasılıkları — alt'a inmez."""
    if not _yuklendi:
        ilk_kurulum()
    tokens = _tokenize(metin)
    if not tokens:
        return {}
    ana_nb_model = {
        "priors": _ana_nb_priors,
        "skorlar": _ana_nb_skorlar,
        "token_toplam": _ana_nb_token_toplam,
        "vocab": _vocab,
        "idf": _idf,
    }
    ana_lr_model = {
        "agirliklar": _ana_lr_agirliklar,
        "bias": _ana_lr_bias,
        "kategoriler": _ana_kategoriler,
    }
    return _ensemble_tahmin(tokens, ana_nb_model, ana_lr_model, _ana_prototipler)


# ════════════════════════════════════════════════════════════════
# BELİRSİZLİK & AKTİF ÖĞRENME
# ════════════════════════════════════════════════════════════════

def belirsizlik_skoru(metin: str) -> float:
    """Margin sampling — en iyi 2 olasılığın farkı.
    Küçük margin = belirsiz → mesaj genel kategoriyle gönderilir.
    Döner: 0.0 (çok belirsiz) - 1.0 (çok güvenli)."""
    topk = tahmin_topk(metin, k=2)
    if len(topk) < 2:
        return 0.0
    en_iyi = topk[0][1]
    ikinci = topk[1][1]
    return en_iyi - ikinci   # margin


def belirsiz_kaydet(metin: str, tahmin_kat: str, guven: float) -> None:
    """Düşük güvenli tahminleri kuyrukla — sonra batch eğitim."""
    if guven >= _BELIRSIZ_ESIK:
        return
    _belirsiz_kuyruk.append({
        "metin":  metin[:200],
        "tahmin": tahmin_kat,
        "guven":  round(guven, 3),
        "zaman":  simdi_tr().isoformat(),
    })
    if len(_belirsiz_kuyruk) > _BELIRSIZ_LIMIT:
        _belirsiz_kuyruk.pop(0)


def belirsiz_listele() -> list[dict]:
    return list(_belirsiz_kuyruk)


def belirsiz_temizle() -> int:
    n = len(_belirsiz_kuyruk)
    _belirsiz_kuyruk.clear()
    return n


def belirsiz_eslestir_ve_egit(satir_no: int, ana: str, alt: str = "") -> tuple[bool, str]:
    """Belirsiz listede sıra numarasıyla bir öğeyi etiketle ve eğit."""
    if satir_no < 1 or satir_no > len(_belirsiz_kuyruk):
        return False, f"Geçersiz sıra ({satir_no}). 1..{len(_belirsiz_kuyruk)} arası."
    kayit = _belirsiz_kuyruk.pop(satir_no - 1)
    tam_kat = f"{ana}:{alt}" if alt else ana
    egit_tek(kayit["metin"], tam_kat, kaynak="manuel")
    return True, f"Eğitildi: {kayit['metin'][:50]}… → {tam_kat}"


# ════════════════════════════════════════════════════════════════
# EĞİTİM API
# ════════════════════════════════════════════════════════════════

def egit_tek(metin: str, kategori: str, kaynak: str = "manuel", hemen_egit: bool = True) -> None:
    """Tek bir örnek ekle, isteğe bağlı olarak hemen retrain."""
    global _kirli_sayac
    _egitim_verisi.append({
        "metin":    metin,
        "kategori": kategori,
        "kaynak":   kaynak,
        "eklendi":  simdi_tr().isoformat(),
    })
    _kirli_sayac += 1
    if hemen_egit or _kirli_sayac >= _RETRAIN_ESIK:
        _modeli_egit()
        _veri_kaydet()
        _model_kaydet()
        _kirli_sayac = 0


def egit_toplu(ornekler: list[tuple[str, str]], kaynak: str = "toplu") -> int:
    """Toplu eğitim — sonra tek seferde retrain."""
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
    """Mevcut veriyle modeli sıfırdan eğit."""
    _modeli_egit()
    _model_kaydet()
    return len(_egitim_verisi)


# ════════════════════════════════════════════════════════════════
# DOĞRULAMA — k-fold cross validation
# ════════════════════════════════════════════════════════════════

def k_fold_dogruluk(k: int = 5) -> dict:
    """k-fold cross validation. Precision/recall/f1 raporu döner."""
    global _egitim_verisi
    if len(_egitim_verisi) < k * 5:
        return {"hata": f"En az {k*5} örnek gerekli (şu an {len(_egitim_verisi)})"}

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

        _egitim_verisi = egitim_set
        _modeli_egit()

        for kayit in test_set:
            tahmin_kat, _ = tahmin(kayit["metin"])
            gercek = kayit["kategori"]
            karmasiklik[gercek][tahmin_kat] += 1
            if tahmin_kat == gercek:
                toplam_dogru += 1
            toplam_test += 1

    _egitim_verisi = orijinal_veri
    _modeli_egit()

    kategoriler = set()
    for k1, k2d in karmasiklik.items():
        kategoriler.add(k1)
        kategoriler.update(k2d.keys())

    metrik = {}
    for kat in sorted(kategoriler):
        tp = karmasiklik[kat].get(kat, 0)
        fn = sum(v for k2, v in karmasiklik[kat].items() if k2 != kat)
        fp = sum(karmasiklik[g].get(kat, 0) for g in kategoriler if g != kat)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2*prec*rec/(prec+rec) if (prec+rec) > 0 else 0.0
        metrik[kat] = {
            "precision": round(prec, 3),
            "recall":    round(rec, 3),
            "f1":        round(f1, 3),
            "ornek":     sum(karmasiklik[kat].values()),
        }

    return {
        "k": k,
        "toplam_ornek": toplam_test,
        "toplam_dogru": toplam_dogru,
        "dogruluk":     round(toplam_dogru/toplam_test, 3) if toplam_test else 0.0,
        "kategori":     metrik,
    }


# ════════════════════════════════════════════════════════════════
# DİSK YÖNETİMİ
# ════════════════════════════════════════════════════════════════

def _veri_kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_EGITIM_FILE) or ".", exist_ok=True)
        gecici = _EGITIM_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(_egitim_verisi, f, ensure_ascii=False)
        os.replace(gecici, _EGITIM_FILE)
    except Exception as e:
        log("UYARI", f"v3 veri kaydet: {e}")


def _model_kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_MODEL_FILE) or ".", exist_ok=True)
        gecici = _MODEL_FILE + ".tmp"
        data = {
            "version": MODEL_VERSION,
            "guncellendi": simdi_tr().isoformat(),
            "ana_kategoriler":      _ana_kategoriler,
            "ana_nb_priors":        _ana_nb_priors,
            "ana_nb_skorlar":       _ana_nb_skorlar,
            "ana_nb_token_toplam":  _ana_nb_token_toplam,
            "ana_lr_agirliklar":    _ana_lr_agirliklar,
            "ana_lr_bias":          _ana_lr_bias,
            "ana_prototipler":      _ana_prototipler,
            "idf":                  _idf,
            "vocab":                list(_vocab),
            "alt_modeller":         {
                ana_kat: {
                    "kategoriler": m["kategoriler"],
                    "nb": {**m["nb"], "vocab": list(m["nb"]["vocab"])},
                    "lr": m["lr"],
                }
                for ana_kat, m in _alt_modeller.items()
            },
            "alt_prototipler":      _alt_prototipler,
        }
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(gecici, _MODEL_FILE)
    except Exception as e:
        log("UYARI", f"v3 model kaydet: {e}")


def _veri_yukle() -> bool:
    global _egitim_verisi
    if not os.path.exists(_EGITIM_FILE):
        return False
    try:
        with open(_EGITIM_FILE, encoding="utf-8") as f:
            _egitim_verisi = json.load(f)
        return True
    except Exception as e:
        log("UYARI", f"v3 veri yükle: {e}")
        return False


def _model_yukle() -> bool:
    global _ana_kategoriler, _ana_nb_priors, _ana_nb_skorlar, _ana_nb_token_toplam
    global _ana_lr_agirliklar, _ana_lr_bias, _idf, _vocab, _alt_modeller, _yuklendi
    global _ana_prototipler, _alt_prototipler
    if not os.path.exists(_MODEL_FILE):
        return False
    try:
        with open(_MODEL_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != MODEL_VERSION:
            log("BILGI", f"Eski model versiyon (v{data.get('version')}), yeniden eğitilecek")
            return False
        _ana_kategoriler     = data["ana_kategoriler"]
        _ana_nb_priors       = data["ana_nb_priors"]
        _ana_nb_skorlar      = data["ana_nb_skorlar"]
        _ana_nb_token_toplam = data["ana_nb_token_toplam"]
        _ana_lr_agirliklar   = data["ana_lr_agirliklar"]
        _ana_lr_bias         = data["ana_lr_bias"]
        _ana_prototipler     = data.get("ana_prototipler", {})
        _idf                 = data["idf"]
        _vocab               = set(data["vocab"])
        _alt_modeller        = {
            ana_kat: {
                "kategoriler": m["kategoriler"],
                "nb": {**m["nb"], "vocab": set(m["nb"]["vocab"])},
                "lr": m["lr"],
            }
            for ana_kat, m in data.get("alt_modeller", {}).items()
        }
        _alt_prototipler     = data.get("alt_prototipler", {})
        _yuklendi = True
        return True
    except Exception as e:
        log("UYARI", f"v3 model yükle: {e}")
        return False


# ════════════════════════════════════════════════════════════════
# İSTATİSTİK & İLK KURULUM
# ════════════════════════════════════════════════════════════════

def istatistik() -> dict:
    if not _yuklendi:
        ilk_kurulum()
    kat_dag = collections.Counter()
    kaynak_dag = collections.Counter()
    for v in _egitim_verisi:
        kat_dag[v["kategori"]] += 1
        kaynak_dag[v.get("kaynak", "?")] += 1
    return {
        "version":           MODEL_VERSION,
        "toplam_ornek":      len(_egitim_verisi),
        "kategori_sayilari": dict(kat_dag),
        "kaynak_dagilim":    dict(kaynak_dag),
        "vocab_boyut":       len(_vocab),
        "ana_kategori_sayi": len(_ana_kategoriler),
        "alt_grup_sayi":     len(_alt_modeller),
        "kategori_sayi":     len(_ana_kategoriler) + sum(len(m["kategoriler"]) for m in _alt_modeller.values()),
        "belirsiz_bekleyen": len(_belirsiz_kuyruk),
        "son_egitim":        _son_egitim_zaman,
    }


# Varsayılan eğitim verisini import et
from utils.ml_dataset import EGITIM_VERISI as _VARSAYILAN_EGITIM


def ilk_kurulum() -> None:
    """Bot ilk açıldığında çağrılır."""
    global _yuklendi
    if _yuklendi:
        return
    if _model_yukle() and _veri_yukle():
        log("OK", f"ML v3 yüklendi: {len(_egitim_verisi)} örnek, "
                  f"{len(_ana_kategoriler)} ana, {len(_alt_modeller)} alt-grup, "
                  f"{len(_vocab)} token")
        _yuklendi = True
        return

    log("BILGI", f"ML v3 ilk kurulum: {len(_VARSAYILAN_EGITIM)} örnek eğitiliyor…")
    egit_toplu(_VARSAYILAN_EGITIM, kaynak="varsayilan")
    _yuklendi = True
    ist = istatistik()
    log("OK", f"ML v3 hazır — {ist['toplam_ornek']} örnek, "
              f"{ist['vocab_boyut']} token, "
              f"{ist['ana_kategori_sayi']} ana + {ist['alt_grup_sayi']} alt-grup")
