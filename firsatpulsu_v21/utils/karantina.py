"""
═══════════════════════════════════════════════════════════════════════
KARANTİNA (v22.9 — Sistem 3)

Kalite puanı sınırda olan ("emin değilim" bölgesi) paylaşımları doğrudan
elemek yerine admin onayına sunar. Admin /onayla veya /reddet ile karar verir.

Net iyi (yüksek puan) → direkt paylaş
Net kötü (çok düşük puan) → direkt ele
Sınırda (orta puan) → KARANTİNA → admin kararı

Böylece hem çöp paylaşılmaz hem de iyi ürünler yanlışlıkla elenmez.
═══════════════════════════════════════════════════════════════════════
"""
import time
from collections import OrderedDict
from utils.log import log

# Karantinadaki paylaşımlar: id → {sablon, gorsel, linkler, ...}
_karantina: OrderedDict = OrderedDict()
_MAX = 50
_sayac = 0


def ekle(sablon: str, gorsel_bytes, linkler, magaza, kat, kanal,
         indirim, fs, puan: int) -> int:
    """Bir paylaşımı karantinaya al. Döner: karantina ID."""
    global _sayac
    _sayac += 1
    kid = _sayac
    _karantina[kid] = {
        "sablon": sablon, "gorsel": gorsel_bytes, "linkler": linkler,
        "magaza": magaza, "kat": kat, "kanal": kanal,
        "indirim": indirim, "fs": fs, "puan": puan, "ts": time.time(),
    }
    # Taşma → en eskiyi at
    while len(_karantina) > _MAX:
        _karantina.popitem(last=False)
    return kid


def al(kid: int) -> dict | None:
    """Karantinadaki bir öğeyi al (çıkarmadan)."""
    return _karantina.get(kid)


def cikar(kid: int) -> dict | None:
    """Karantinadan çıkar ve döndür (onay/ret sonrası)."""
    return _karantina.pop(kid, None)


def bekleyenler() -> list:
    """Bekleyen karantina öğelerinin özeti."""
    sonuc = []
    for kid, v in _karantina.items():
        # Şablondan ürün adı (ilk <b> başlık)
        import re
        m = re.search(r"<b>([^<]{4,})</b>", v["sablon"])
        ad = m.group(1) if m else "?"
        sonuc.append({"id": kid, "urun": ad[:40], "puan": v["puan"],
                      "magaza": v["magaza"]})
    return sonuc


def sayi() -> int:
    return len(_karantina)
