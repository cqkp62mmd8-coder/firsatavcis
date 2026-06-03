"""
═══════════════════════════════════════════════════════════════════════
KARA KUTU (v22.7 — Sistem 7: black box) — v23.7: DB tabanlı (kalıcı)

Botun son N olayını tutar. Bir sorun/çökme olduğunda "ne oldu da bozuldu"
sorusunu kesin cevaplar. Debugging'i kökten kolaylaştırır.

v23.7: Eskiden bellekte (deque) tutuluyordu → bot restart'ta tüm olaylar
siliniyordu, /karakutu 0 gösteriyordu. Artık DB'de kalıcı.
═══════════════════════════════════════════════════════════════════════
"""
import time
import datetime

_MAX = 100


def _ilk_kurulum() -> None:
    try:
        from utils import db
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS karakutu_olay (
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    tur   TEXT NOT NULL,
                    detay TEXT,
                    ts    REAL NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_kk_ts ON karakutu_olay(ts)")
    except Exception:
        pass


def kaydet(tur: str, detay: str = "", veri: dict | None = None) -> None:
    """Bir olayı kara kutuya yaz. tur: 'mesaj', 'paylasim', 'hata', 'model', 'sistem'."""
    _ilk_kurulum()
    try:
        from utils import db
        with db.cursor() as c:
            c.execute(
                "INSERT INTO karakutu_olay (tur, detay, ts) VALUES (?, ?, ?)",
                (tur, (detay[:200] if detay else ""), time.time())
            )
            # Son _MAX olayı tut
            c.execute("""
                DELETE FROM karakutu_olay WHERE id NOT IN (
                    SELECT id FROM karakutu_olay ORDER BY ts DESC LIMIT ?
                )
            """, (_MAX,))
    except Exception:
        pass


def son_olaylar(n: int = 20, tur: str | None = None) -> list:
    """Son N olayı döndür (opsiyonel tür filtresi)."""
    _ilk_kurulum()
    try:
        from utils import db
        with db.cursor() as c:
            if tur:
                satirlar = c.execute(
                    "SELECT tur, detay, ts FROM karakutu_olay WHERE tur=? "
                    "ORDER BY ts DESC LIMIT ?", (tur, n)
                ).fetchall()
            else:
                satirlar = c.execute(
                    "SELECT tur, detay, ts FROM karakutu_olay ORDER BY ts DESC LIMIT ?",
                    (n,)
                ).fetchall()
        return [{"ts": r["ts"], "tur": r["tur"], "detay": r["detay"]}
                for r in reversed(satirlar)]
    except Exception:
        return []


def ozet() -> dict:
    """Kara kutu özeti — tür dağılımı + son hata."""
    _ilk_kurulum()
    try:
        from utils import db
        with db.cursor() as c:
            toplam = c.execute("SELECT COUNT(*) n FROM karakutu_olay").fetchone()["n"]
            if not toplam:
                return {"toplam": 0}
            tur_satirlar = c.execute(
                "SELECT tur, COUNT(*) n FROM karakutu_olay GROUP BY tur"
            ).fetchall()
            turler = {r["tur"]: r["n"] for r in tur_satirlar}
            son_hata_satir = c.execute(
                "SELECT detay, ts FROM karakutu_olay WHERE tur='hata' "
                "ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        sonuc = {"toplam": toplam, "turler": turler}
        if son_hata_satir:
            sonuc["son_hata"] = {
                "zaman": datetime.datetime.fromtimestamp(
                    son_hata_satir["ts"]).strftime("%H:%M:%S"),
                "detay": son_hata_satir["detay"],
            }
        return sonuc
    except Exception:
        return {"toplam": 0}
