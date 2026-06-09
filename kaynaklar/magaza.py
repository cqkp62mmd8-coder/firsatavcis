"""kaynaklar/magaza.py — Mağaza izleme kaynağı (v23.37).

İzleme listesindeki (watchlist) ürün URL'lerinin fiyatlarını mevcut
`services.scraping` ile kontrol eder; gerçek indirim varsa fırsat üretir.
Bu, deal-sayfası kazıması DEĞİLDİR (o, veri-merkezi IP engeli ve bot koruması
nedeniyle proxy ister); kaynak sitenin ürün sayfasından güvenilir okumadır.

Tam indirim-sayfası taraması ileride proxy ile eklenebilir; bu kaynak şimdiden
"kanal değil, kaynak site" ilkesine uyar ve güvenilir çalışır.
"""
from __future__ import annotations
from typing import Any

from kaynaklar.temel import Kaynak


class MagazaIzlemeKaynak(Kaynak):
    """Watchlist URL'lerini tarayıp indirimli olanları fırsat olarak verir."""

    ad = "magaza-izleme"

    def __init__(self, urller: list[str], min_indirim: int = 0):
        self.urller = [u for u in (urller or []) if u]
        self.min_indirim = min_indirim

    def etkin_mi(self) -> bool:
        return bool(self.urller)

    def firsatlar(self) -> list[dict[str, Any]]:
        if not self.urller:
            return []
        try:
            from services import scraping
        except Exception:
            return []
        from kaynaklar.temel import indirim_hesapla, firsat_gecerli_mi

        cikti = []
        for url in self.urller:
            try:
                bilgi = scraping.urun_bilgisi(url)  # {ad, fiyat, eski_fiyat, gorsel, ...}
            except Exception:
                bilgi = None
            if not bilgi:
                continue
            f = {
                "url": url,
                "ad": (bilgi.get("ad") or bilgi.get("baslik") or "").strip(),
                "fiyat": bilgi.get("fiyat"),
                "eski_fiyat": bilgi.get("eski_fiyat"),
                "gorsel": bilgi.get("gorsel") or bilgi.get("resim"),
                "kategori": bilgi.get("kategori"),
                "magaza": bilgi.get("magaza"),
                "kaynak": self.ad,
            }
            if not firsat_gecerli_mi(f):
                continue
            ind = indirim_hesapla(f.get("eski_fiyat"), f.get("fiyat"))
            if ind >= self.min_indirim:
                cikti.append(f)
        return cikti
