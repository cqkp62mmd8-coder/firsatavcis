"""
#8 — Mesaj zenginleştirme. Amazon/Trendyol yorum API'leri yok.
Şu an: link domain'ine göre statik güvenilirlik göstergeleri ekler.
Gelecekte: scraper / API entegrasyonu yapılabilir.
"""
from urllib.parse import urlparse

# Statik mağaza skorları (kullanıcı geri bildirimine göre düzenlenebilir)
_MAGAZA_GUVEN = {
    "amazon.com.tr":  ("✅ Resmi Amazon TR", 5.0),
    "amzn.to":         ("✅ Resmi Amazon TR", 5.0),
    "trendyol.com":    ("✅ Resmi Trendyol",  4.8),
    "ty.gl":           ("✅ Resmi Trendyol",  4.8),
    "hepsiburada.com": ("✅ Resmi Hepsiburada", 4.8),
    "hb.biz":          ("✅ Resmi Hepsiburada", 4.8),
    "hb.gl":           ("✅ Resmi Hepsiburada", 4.8),
    "mediamarkt.com":  ("✅ Resmi MediaMarkt", 4.7),
    "teknosa.com":     ("✅ Resmi Teknosa",   4.7),
    "n11.com":         ("✓ N11",             4.5),
    "sl.n11.com":      ("✓ N11",             4.5),
    "gratis.com":      ("✅ Resmi Gratis",    4.7),
    "boyner.com":      ("✅ Resmi Boyner",    4.7),
    "ciceksepeti.com": ("✅ Resmi Çiçeksepeti", 4.6),
    "aliexpress.com":  ("ℹ️ Yurtdışı (AliExpress)", 3.8),
    "temu.com":        ("ℹ️ Yurtdışı (Temu)",      3.5),
}


def guvenilirlik_etiketi(link: str | None) -> str | None:
    """Link'in mağazasına göre güvenilirlik etiketi döner.
    None ise mesaja eklenmemeli."""
    if not link:
        return None
    try:
        netloc = urlparse(link).netloc.lower()
        for domain, (etiket, _) in _MAGAZA_GUVEN.items():
            if domain in netloc:
                return etiket
    except Exception:
        pass
    return None


def magaza_skoru(link: str | None) -> float | None:
    """Link'in mağazasının statik güven skoru (5 üzerinden)."""
    if not link:
        return None
    try:
        netloc = urlparse(link).netloc.lower()
        for domain, (_, skor) in _MAGAZA_GUVEN.items():
            if domain in netloc:
                return skor
    except Exception:
        pass
    return None
