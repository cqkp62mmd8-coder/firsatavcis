"""
cok_kiraci/affiliate.py — Müşteri affiliate etiketi enjeksiyonu (Faz 3).

Gönderimden önce, ürün adresine ilgili müşterinin affiliate etiketi enjekte
edilir. Platforma göre yöntem değişir:

  - Amazon: ürün adresine ?tag=ETIKET eklenir/güncellenir. Tam destekli. ✔
  - Trendyol / Hepsiburada / N11: affiliate genellikle ağ-deeplink ister; basit
    etiket eklemek kazanç sağlamaz. ŞİMDİLİK İSKELET: link değiştirilmeden döner.
    Her müşterinin ağına göre gerçek deeplink üretimi sonradan eklenecek.
"""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Tam destekli platformlar (panelde müşteriye gösterilebilir)
TAM_DESTEK = {"amazon"}


def desteklenen_platform(magaza: str) -> bool:
    """Bu platform için affiliate enjeksiyonu otomatik çalışıyor mu?"""
    return (magaza or "").lower() in TAM_DESTEK


def _amazon(url: str, etiket: str) -> str:
    p = urlparse(url)
    q = {k: v[-1] for k, v in parse_qs(p.query).items()}
    q["tag"] = etiket                       # mevcut tag varsa değiştirilir
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))


def enjekte(urun_url: str, magaza: str, etiket: str) -> str:
    """Müşterinin affiliate etiketini ürün adresine enjekte et.
    Etiket yoksa ya da platform desteklenmiyorsa adres olduğu gibi döner."""
    if not urun_url or not etiket:
        return urun_url or ""
    m = (magaza or "").lower()
    if "amazon" in m:
        try:
            return _amazon(urun_url, etiket)
        except Exception:
            return urun_url
    # Diğer platformlar: ağ-deeplink gerekir → şimdilik değiştirme
    return urun_url
