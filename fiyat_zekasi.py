"""
═══════════════════════════════════════════════════════════════════════
Fiyat Zekası — "Bu gerçekten iyi bir fırsat mı?"

Yapay zeka ile fiyat değerlendirmesi. Her kategori/alt-kategori için
fiyat dağılımını zaman içinde öğrenir (online istatistik). Yeni bir
ürün geldiğinde:
  • O kategorideki tipik fiyata göre ucuz mu, pahalı mı?
  • Percentile hesabı: "Bu fiyat, gördüğümüz telefonların en ucuz %15'inde"
  • Fırsat skorunu zenginleştirir

Welford online algoritması — sabit bellek, akış halinde öğrenir.
Pure Python, harici bağımlılık yok.

KULLANIM:
    fiyat_zekasi.kaydet("elektronik:telefon", 45000)   # öğren
    skor = fiyat_zekasi.firsat_degeri("elektronik:telefon", 32000)
    # → {"percentile": 0.12, "yorum": "çok iyi fiyat", "ortalama": 48000}
═══════════════════════════════════════════════════════════════════════
"""
import json
import math
import os
from typing import Optional

import config
from utils.log import log

_VERI_FILE = os.path.join(config.DATA_DIR, "fiyat_zekasi.json")

# Her kategori için son N fiyatı tut (percentile hesabı için)
_MAKS_ORNEK = 200
# Anlamlı percentile için minimum örnek
_MIN_ORNEK = 15

# kategori → {"fiyatlar": [son N fiyat], "n": toplam, "mean": ort, "m2": welford}
_veri: dict[str, dict] = {}
_yuklendi = False
_kayit_sayac = 0


def _yukle() -> None:
    global _veri, _yuklendi
    if _yuklendi:
        return
    if os.path.exists(_VERI_FILE):
        try:
            with open(_VERI_FILE, encoding="utf-8") as f:
                _veri = json.load(f)
        except Exception as e:
            log("UYARI", f"Fiyat zekası yükle: {e}")
            _veri = {}
    _yuklendi = True


def _kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_VERI_FILE) or ".", exist_ok=True)
        gecici = _VERI_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(_veri, f, ensure_ascii=False)
        os.replace(gecici, _VERI_FILE)
    except Exception as e:
        log("UYARI", f"Fiyat zekası kaydet: {e}")


def kaydet(kategori: str, fiyat: float) -> None:
    """Bir kategorideki gerçek fiyatı öğren (online güncelleme)."""
    _yukle()
    global _kayit_sayac
    if not kategori or not fiyat or fiyat <= 0:
        return

    if kategori not in _veri:
        _veri[kategori] = {"fiyatlar": [], "n": 0, "mean": 0.0, "m2": 0.0}
    d = _veri[kategori]

    # Welford online mean/variance
    d["n"] += 1
    delta = fiyat - d["mean"]
    d["mean"] += delta / d["n"]
    d["m2"] += delta * (fiyat - d["mean"])

    # Son N fiyatı tut (percentile için)
    d["fiyatlar"].append(fiyat)
    if len(d["fiyatlar"]) > _MAKS_ORNEK:
        d["fiyatlar"] = d["fiyatlar"][-_MAKS_ORNEK:]

    _kayit_sayac += 1
    if _kayit_sayac >= 20:
        _kaydet()
        _kayit_sayac = 0


def firsat_degeri(kategori: str, fiyat: float) -> Optional[dict]:
    """Bir fiyatın o kategori için ne kadar iyi olduğunu değerlendir.

    Döner:
      {
        "percentile": 0.0-1.0,  # 0 = en ucuz, 1 = en pahalı
        "yorum": "çok iyi fiyat" | "iyi fiyat" | "ortalama" | "pahalı",
        "ortalama": kategori ortalaması,
        "ornek_sayisi": kaç fiyattan hesaplandı,
        "bonus": fırsat skoruna eklenecek bonus puan (0-15),
      }
    Yeterli veri yoksa None döner.
    """
    _yukle()
    if not kategori or not fiyat or fiyat <= 0:
        return None
    d = _veri.get(kategori)
    if not d or d["n"] < _MIN_ORNEK:
        return None

    fiyatlar = d["fiyatlar"]
    if not fiyatlar:
        return None

    # Percentile: bu fiyattan ucuz olanların oranı
    daha_ucuz = sum(1 for f in fiyatlar if f < fiyat)
    percentile = daha_ucuz / len(fiyatlar)

    # Yorum + bonus
    if percentile <= 0.15:
        yorum, bonus = "çok iyi fiyat", 15
    elif percentile <= 0.35:
        yorum, bonus = "iyi fiyat", 10
    elif percentile <= 0.65:
        yorum, bonus = "ortalama fiyat", 3
    elif percentile <= 0.85:
        yorum, bonus = "ortalama üstü", 0
    else:
        yorum, bonus = "pahalı", 0

    return {
        "percentile":   round(percentile, 3),
        "yorum":        yorum,
        "ortalama":     round(d["mean"], 0),
        "ornek_sayisi": len(fiyatlar),
        "bonus":        bonus,
    }


def std(kategori: str) -> float:
    """Kategori fiyat standart sapması."""
    _yukle()
    d = _veri.get(kategori)
    if not d or d["n"] < 2:
        return 0.0
    return math.sqrt(max(d["m2"] / (d["n"] - 1), 0))


def kategori_profili(kategori: str) -> dict:
    """Bir kategorinin fiyat profili."""
    _yukle()
    d = _veri.get(kategori)
    if not d or not d["fiyatlar"]:
        return {"kategori": kategori, "ornek": 0}
    fiyatlar = sorted(d["fiyatlar"])
    n = len(fiyatlar)
    return {
        "kategori":   kategori,
        "ornek":      d["n"],
        "ortalama":   round(d["mean"], 0),
        "std":        round(std(kategori), 0),
        "min":        fiyatlar[0],
        "maks":       fiyatlar[-1],
        "medyan":     fiyatlar[n // 2],
    }


def tum_profiller() -> list[dict]:
    _yukle()
    return [kategori_profili(k) for k in sorted(_veri.keys())]


def istatistik() -> dict:
    _yukle()
    return {
        "kategori_sayisi":  len(_veri),
        "toplam_gozlem":    sum(d["n"] for d in _veri.values()),
        "dosya":            _VERI_FILE,
    }
