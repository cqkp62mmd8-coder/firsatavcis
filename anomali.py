"""
═══════════════════════════════════════════════════════════════════════
Anomali Tespiti — şüpheli mesajları yakalar (z-score tabanlı)
═══════════════════════════════════════════════════════════════════════
"""
import json
import math
import os
from typing import Optional

import config
from utils.log import log

_STAT_FILE = os.path.join(config.DATA_DIR, "anomali_stat.json")


class _WelfordStat:
    """Streaming mean & variance — sabit bellek."""
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def ekle(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.m2 += delta * delta2

    def varyans(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    def std(self) -> float:
        return math.sqrt(max(self.varyans(), 1e-6))

    def z(self, x: float) -> float:
        if self.n < 10:
            return 0.0
        s = self.std()
        return abs(x - self.mean) / s if s else 0.0

    def to_dict(self) -> dict:
        return {"n": self.n, "mean": self.mean, "m2": self.m2}

    @classmethod
    def from_dict(cls, d: dict) -> "_WelfordStat":
        ws = cls()
        ws.n = d.get("n", 0)
        ws.mean = d.get("mean", 0.0)
        ws.m2 = d.get("m2", 0.0)
        return ws


_stats: dict[str, _WelfordStat] = {
    "uzunluk":    _WelfordStat(),
    "fiyat":      _WelfordStat(),
    "indirim":    _WelfordStat(),
    "link_sayi":  _WelfordStat(),
    "emoji_oran": _WelfordStat(),
}
_yuklendi = False
_kayit_sayac = 0


def _yukle() -> None:
    global _stats, _yuklendi
    if _yuklendi:
        return
    if os.path.exists(_STAT_FILE):
        try:
            with open(_STAT_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for ad, d in data.items():
                _stats[ad] = _WelfordStat.from_dict(d)
        except Exception as e:
            log("UYARI", f"Anomali stat yükle: {e}")
    _yuklendi = True


def _kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_STAT_FILE) or ".", exist_ok=True)
        gecici = _STAT_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({ad: s.to_dict() for ad, s in _stats.items()}, f)
        os.replace(gecici, _STAT_FILE)
    except Exception as e:
        log("UYARI", f"Anomali stat kaydet: {e}")


def kontrol_et(metin: str, fiyat: Optional[float] = None, indirim: Optional[int] = None,
               link_sayi: int = 0) -> tuple[bool, str]:
    """Mesajı kontrol et. Döner: (anomali_mi, sebep)."""
    _yukle()
    global _kayit_sayac

    if not metin:
        return True, "boş mesaj"

    # ── Hard kurallar ──
    if indirim and indirim > 95:
        return True, f"indirim aşırı yüksek (%{indirim})"
    if fiyat is not None and 0 < fiyat < 10:
        return True, f"fiyat çok düşük ({fiyat} TL)"
    if fiyat is not None and fiyat > 10_000_000:
        return True, f"fiyat çok yüksek ({fiyat} TL)"

    emoji_sayi = sum(1 for c in metin if ord(c) > 0x1F000)
    emoji_oran = emoji_sayi / len(metin) if len(metin) >= 8 else 0.0
    if emoji_oran > 0.30:
        return True, f"emoji oranı yüksek (%{emoji_oran*100:.0f})"

    harf_top = sum(1 for c in metin if c.isalpha())
    if harf_top > 20:
        buyuk = sum(1 for c in metin if c.isupper())
        if buyuk / harf_top > 0.7:
            return True, "büyük harf bombası"

    if link_sayi > 10:
        return True, f"çok link ({link_sayi})"

    # ── Z-score kontrolleri ──
    sebepler = []
    uzunluk = len(metin)
    if _stats["uzunluk"].z(uzunluk) > 4:
        sebepler.append(f"uzunluk anormal (z={_stats['uzunluk'].z(uzunluk):.1f})")
    if fiyat is not None and _stats["fiyat"].z(fiyat) > 5:
        sebepler.append(f"fiyat anormal (z={_stats['fiyat'].z(fiyat):.1f})")
    if sebepler:
        return True, "; ".join(sebepler)

    # ── Normal mesaj → istatistik güncelle ──
    _stats["uzunluk"].ekle(uzunluk)
    if fiyat is not None:
        _stats["fiyat"].ekle(fiyat)
    if indirim is not None:
        _stats["indirim"].ekle(indirim)
    _stats["link_sayi"].ekle(link_sayi)
    _stats["emoji_oran"].ekle(emoji_oran)

    _kayit_sayac += 1
    if _kayit_sayac >= 50:
        _kaydet()
        _kayit_sayac = 0

    return False, ""


def istatistik() -> dict:
    _yukle()
    return {
        ad: {"n": s.n, "ort": round(s.mean, 2), "std": round(s.std(), 2)}
        for ad, s in _stats.items()
    }
