"""
═══════════════════════════════════════════════════════════════════════
KARA KUTU (v22.7 — Sistem 7: black box)

Botun son N olayını bellekte tutar. Bir sorun/çökme olduğunda
"ne oldu da bozuldu" sorusunu kesin cevaplar. Debugging'i kökten kolaylaştırır.

Her önemli olay (mesaj işleme, paylaşım, hata, model değişimi) zaman
damgasıyla kaydedilir. /karakutu ile son olaylar görülür.
═══════════════════════════════════════════════════════════════════════
"""
import time
from collections import deque

_olaylar: deque = deque(maxlen=100)


def kaydet(tur: str, detay: str = "", veri: dict | None = None) -> None:
    """Bir olayı kara kutuya yaz. tur: 'mesaj', 'paylasim', 'hata', 'model', 'sistem'."""
    _olaylar.append({
        "ts": time.time(),
        "tur": tur,
        "detay": detay[:200] if detay else "",
        "veri": veri or {},
    })


def son_olaylar(n: int = 20, tur: str | None = None) -> list:
    """Son N olayı döndür (opsiyonel tür filtresi)."""
    olaylar = list(_olaylar)
    if tur:
        olaylar = [o for o in olaylar if o["tur"] == tur]
    return olaylar[-n:]


def ozet() -> dict:
    """Kara kutu özeti — tür dağılımı + son hata."""
    if not _olaylar:
        return {"toplam": 0}
    turler: dict = {}
    son_hata = None
    for o in _olaylar:
        turler[o["tur"]] = turler.get(o["tur"], 0) + 1
        if o["tur"] == "hata":
            son_hata = o
    sonuc = {"toplam": len(_olaylar), "turler": turler}
    if son_hata:
        import datetime
        sonuc["son_hata"] = {
            "zaman": datetime.datetime.fromtimestamp(son_hata["ts"]).strftime("%H:%M:%S"),
            "detay": son_hata["detay"],
        }
    return sonuc


def formatla(n: int = 15) -> str:
    """Son olayları okunabilir metin olarak formatla (/karakutu için)."""
    import datetime
    olaylar = son_olaylar(n)
    if not olaylar:
        return "Kara kutu boş — henüz olay kaydedilmedi."
    _ikon = {"mesaj": "📨", "paylasim": "📤", "hata": "❌",
             "model": "🧠", "sistem": "⚙️"}
    satirlar = []
    for o in olaylar:
        zaman = datetime.datetime.fromtimestamp(o["ts"]).strftime("%H:%M:%S")
        ikon = _ikon.get(o["tur"], "•")
        satirlar.append(f"{zaman} {ikon} {o['detay'][:50]}")
    return "\n".join(satirlar)
