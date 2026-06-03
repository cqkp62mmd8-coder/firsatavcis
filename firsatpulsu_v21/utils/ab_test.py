"""
═══════════════════════════════════════════════════════════════════════
A/B ŞABLON TESTİ (v22.7 — Sistem 8)

Farklı şablon başlık stillerini rotasyona sokar, hangisi daha çok 🔥 oy
alıyor öğrenir, zamanla kazanan stile ağırlık verir.

Stiller (başlık varyantları):
  A: "💎 ELİT FIRSAT — %X İNDİRİM"  (mevcut)
  B: "🔥 KAÇIRMA — %X İNDİRİM"
  C: "⚡ FLAŞ FIRSAT · %X"

Her paylaşımda mesaj_id → stil eşleşmesi kaydedilir. Oylar gelince
hangi stilin daha iyi performans gösterdiği SQLite'ta toplanır.
Kazanan stile daha sık (ağırlıklı) geçilir — ama keşif için diğerleri
de ara sıra denenir (epsilon-greedy).
═══════════════════════════════════════════════════════════════════════
"""
import random
import time
from utils import db
from utils.log import log

STILLER = {
    "A": "💎 <b>ELİT FIRSAT — %{indirim} İNDİRİM</b>",
    "B": "🔥 <b>KAÇIRMA — %{indirim} İNDİRİM</b>",
    "C": "⚡ <b>FLAŞ FIRSAT · %{indirim}</b>",
}
_KESIF_ORANI = 0.25   # %25 ihtimalle rastgele keşif (kalan %75 kazanana)


def _ilk_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS ab_stil (
                    stil       TEXT PRIMARY KEY,
                    gosterim   INTEGER DEFAULT 0,
                    iyi_oy     INTEGER DEFAULT 0,
                    kotu_oy    INTEGER DEFAULT 0
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS ab_mesaj (
                    mesaj_id   INTEGER PRIMARY KEY,
                    stil       TEXT,
                    ts         INTEGER
                )
            """)
    except Exception as e:
        log("UYARI", f"AB test kurulum: {e}")


def stil_sec() -> tuple[str, str]:
    """Bir şablon stili seç (epsilon-greedy). Döner: (stil_kodu, baslik_template)."""
    _ilk_kurulum()
    # Keşif: rastgele
    if random.random() < _KESIF_ORANI:
        kod = random.choice(list(STILLER.keys()))
        return kod, STILLER[kod]
    # Sömürü: en iyi oranlı stili seç
    try:
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT stil, gosterim, iyi_oy, kotu_oy FROM ab_stil WHERE gosterim >= 5"
            ).fetchall()
        if satirlar:
            def oran(r):
                toplam = r["iyi_oy"] + r["kotu_oy"]
                return r["iyi_oy"] / toplam if toplam else 0.5
            en_iyi = max(satirlar, key=oran)
            return en_iyi["stil"], STILLER.get(en_iyi["stil"], STILLER["A"])
    except Exception:
        pass
    # Yeterli veri yok → varsayılan A
    return "A", STILLER["A"]


def gosterim_kaydet(mesaj_id: int, stil: str) -> None:
    """Bir mesajın hangi stille paylaşıldığını kaydet."""
    if not mesaj_id or not stil:
        return
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            c.execute("INSERT OR IGNORE INTO ab_stil (stil) VALUES (?)", (stil,))
            c.execute("UPDATE ab_stil SET gosterim=gosterim+1 WHERE stil=?", (stil,))
            c.execute(
                "INSERT OR REPLACE INTO ab_mesaj (mesaj_id, stil, ts) VALUES (?, ?, ?)",
                (mesaj_id, stil, int(time.time()))
            )
    except Exception as e:
        log("UYARI", f"AB gösterim: {e}")


def oy_kaydet(mesaj_id: int, iyi: bool) -> None:
    """Bir mesaja oy geldiğinde, o mesajın stiline oyu işle."""
    if not mesaj_id:
        return
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            r = c.execute("SELECT stil FROM ab_mesaj WHERE mesaj_id=?", (mesaj_id,)).fetchone()
            if not r:
                return
            stil = r["stil"]
            if iyi:
                c.execute("UPDATE ab_stil SET iyi_oy=iyi_oy+1 WHERE stil=?", (stil,))
            else:
                c.execute("UPDATE ab_stil SET kotu_oy=kotu_oy+1 WHERE stil=?", (stil,))
    except Exception as e:
        log("UYARI", f"AB oy: {e}")


def istatistik() -> dict:
    """A/B test sonuçları (/abtest için)."""
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT stil, gosterim, iyi_oy, kotu_oy FROM ab_stil ORDER BY gosterim DESC"
            ).fetchall()
        sonuc = []
        for r in satirlar:
            toplam = r["iyi_oy"] + r["kotu_oy"]
            oran = round(r["iyi_oy"] / toplam * 100, 1) if toplam else 0
            sonuc.append({
                "stil": r["stil"], "gosterim": r["gosterim"],
                "iyi": r["iyi_oy"], "kotu": r["kotu_oy"], "basari": oran,
            })
        return {"stiller": sonuc}
    except Exception:
        return {"stiller": []}
