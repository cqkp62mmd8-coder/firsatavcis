"""kaynaklar/feed.py — Yapılandırılabilir ürün-feed okuyucu (v23.37).

Affiliate ağlarının (Admitad, Gelir Ortakları, mağaza ortaklık programları)
ürün/indirim feed'lerini okur. XML, CSV ve JSON biçimlerini destekler; alan
eşlemesi yapılandırma ile yapıldığı için çoğu feed'e kod değiştirmeden uyar.

Fetch ve parse AYRI tutulur: `_ayristir(ham, ...)` ağ olmadan test edilebilir.
"""
from __future__ import annotations
import csv as _csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any

from kaynaklar.temel import Kaynak, firsat_gecerli_mi


def _alan(kayit: dict, isim: str | None, varsayilan=None):
    """Bir kayıttan alanı esnek biçimde çek (büyük/küçük harf, namespace toleranslı)."""
    if not isim or not isinstance(kayit, dict):
        return varsayilan
    if isim in kayit:
        return kayit[isim]
    dl = isim.lower()
    for k, v in kayit.items():
        kk = k.lower()
        if kk == dl or kk.endswith("}" + dl) or kk.split("}")[-1] == dl:
            return v
    return varsayilan


def _sayi(deger: Any) -> float | None:
    """Metinden fiyat çıkar ('1.299,90 TL' → 1299.90)."""
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        return float(deger)
    s = str(deger)
    t = "".join(ch for ch in s if ch.isdigit() or ch in ".,")
    if not t:
        return None
    # Türkçe biçim: nokta binlik, virgül ondalık
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _normalize(kayit: dict, eslem: dict, kaynak_ad: str) -> dict | None:
    """Ham kaydı, alan eşlemesini kullanarak normalize fırsata çevir."""
    f = {
        "url": (_alan(kayit, eslem.get("url")) or "").strip() if _alan(kayit, eslem.get("url")) else "",
        "ad": (str(_alan(kayit, eslem.get("ad")) or "")).strip(),
        "fiyat": _sayi(_alan(kayit, eslem.get("fiyat"))),
        "eski_fiyat": _sayi(_alan(kayit, eslem.get("eski_fiyat"))),
        "gorsel": _alan(kayit, eslem.get("gorsel")),
        "kategori": _alan(kayit, eslem.get("kategori")),
        "magaza": _alan(kayit, eslem.get("magaza")) or eslem.get("magaza_sabit"),
        "kaynak": kaynak_ad,
    }
    return f if firsat_gecerli_mi(f) else None


def _ayristir(ham: str, bicim: str, eslem: dict, kaynak_ad: str) -> list[dict]:
    """Ham feed metnini normalize fırsat listesine çevir (ağ gerektirmez)."""
    bicim = (bicim or "").lower()
    kayitlar: list[dict] = []

    if bicim == "json":
        veri = json.loads(ham)
        yol = eslem.get("kayit_yolu")  # örn "products" veya "data.items"
        node = veri
        if yol:
            for parca in yol.split("."):
                node = node.get(parca, []) if isinstance(node, dict) else []
        if isinstance(node, dict):
            node = [node]
        kayitlar = [k for k in (node or []) if isinstance(k, dict)]

    elif bicim == "csv":
        okuyucu = _csv.DictReader(io.StringIO(ham))
        kayitlar = [dict(r) for r in okuyucu]

    else:  # xml (varsayılan)
        kok = ET.fromstring(ham)
        etiket = eslem.get("kayit_yolu") or "item"  # tekrar eden öğe
        bulunan = [e for e in kok.iter() if e.tag.split("}")[-1] == etiket]
        for el in bulunan:
            kayit: dict[str, Any] = {}
            for cocuk in el:
                ad = cocuk.tag.split("}")[-1]
                kayit[ad] = (cocuk.text or "").strip()
                # bazı feed'lerde değer attribute'ta (örn <g:price value="..."/>)
                for ak, av in cocuk.attrib.items():
                    kayit.setdefault(f"{ad}_{ak}", av)
            kayitlar.append(kayit)

    firsatlar = []
    for k in kayitlar:
        f = _normalize(k, eslem, kaynak_ad)
        if f:
            firsatlar.append(f)
    return firsatlar


class FeedKaynak(Kaynak):
    """URL'den ürün feed'i çekip normalize fırsatlar üretir."""

    def __init__(self, url: str, bicim: str, eslem: dict, ad: str = "feed"):
        self.url = url
        self.bicim = bicim
        self.eslem = eslem or {}
        self.ad = ad

    def etkin_mi(self) -> bool:
        return bool(self.url and self.eslem.get("url") and self.eslem.get("ad")
                    and self.eslem.get("fiyat"))

    def _indir(self) -> str | None:
        """Feed'i indir (ağ). Test edilebilirlik için parse'tan ayrı."""
        try:
            from utils import istek
            return istek.metin_indir(self.url, timeout=20)
        except Exception:
            try:
                import urllib.request
                with urllib.request.urlopen(self.url, timeout=20) as r:
                    return r.read().decode("utf-8", "replace")
            except Exception:
                return None

    def firsatlar(self) -> list[dict]:
        if not self.etkin_mi():
            return []
        ham = self._indir()
        if not ham:
            return []
        try:
            return _ayristir(ham, self.bicim, self.eslem, self.ad)
        except Exception:
            return []
