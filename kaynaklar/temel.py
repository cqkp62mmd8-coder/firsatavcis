"""kaynaklar/ — Fırsat keşif kaynakları (v23.37).

Kanal dinlemenin yerine geçen modüler giriş katmanı. Her kaynak, normalize
edilmiş fırsat sözlükleri üretir; zamanlayıcı bunları mevcut paylaşım hattına
besler. Böylece ayrıştırma/filtre/kalite/biçimleme/paylaşım hattı aynı kalır.

Normalize fırsat sözlüğü alanları:
    url        : ürün linki (tercihen affiliate)         [zorunlu]
    ad         : ürün adı                                 [zorunlu]
    fiyat      : güncel fiyat (float)                     [zorunlu]
    eski_fiyat : eski/piyasa fiyatı (float | None)
    gorsel     : görsel URL (str | None)
    kategori   : kategori (str | None)
    magaza     : mağaza adı (str | None)
    kaynak     : kaynağın adı (str)
"""
from __future__ import annotations
from typing import Any


class Kaynak:
    """Tüm fırsat kaynaklarının temel sınıfı.

    Alt sınıflar `firsatlar()` metodunu uygular ve normalize fırsat sözlükleri
    listesi döndürür. Hata durumunda boş liste döndürmeli (asla patlamamalı).
    """

    ad: str = "kaynak"

    def etkin_mi(self) -> bool:
        """Bu kaynak yapılandırılmış ve kullanılabilir mi?"""
        return True

    def firsatlar(self) -> list[dict[str, Any]]:
        """Keşfedilen fırsatları normalize sözlük listesi olarak döndür."""
        raise NotImplementedError


def firsat_gecerli_mi(f: dict[str, Any]) -> bool:
    """Bir fırsat sözlüğü paylaşıma uygun minimum alanlara sahip mi?"""
    if not isinstance(f, dict):
        return False
    url = (f.get("url") or "").strip()
    ad = (f.get("ad") or "").strip()
    try:
        fiyat = float(f.get("fiyat") or 0)
    except (TypeError, ValueError):
        return False
    return bool(url) and bool(ad) and fiyat > 0


def indirim_hesapla(eski: Any, yeni: Any) -> int:
    """Eski/yeni fiyattan indirim yüzdesi (yoksa 0)."""
    try:
        e = float(eski or 0)
        y = float(yeni or 0)
    except (TypeError, ValueError):
        return 0
    if e <= 0 or y <= 0 or y >= e:
        return 0
    return int(round((e - y) / e * 100))
