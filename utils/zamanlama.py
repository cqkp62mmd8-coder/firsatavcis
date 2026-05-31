"""
═══════════════════════════════════════════════════════════════════════
AKILLI PAYLAŞIM ZAMANLAMASI (v22.11 — Sistem 10)

Kanalın gerçek etkileşim verisinden öğrenir: hangi saatlerde paylaşımlar
daha çok oy/tıklama alıyor? O saatlere "altın saat" der, bekleme süresini
kısaltıp daha çok paylaşır. Ölü saatlerde yavaşlar.

Sabit kurallar (Cuma 18-23 gibi) yerine VERİYLE öğrenir.
Her oy geldiğinde, o saatin etkileşim skoru artar (saat 0-23).
═══════════════════════════════════════════════════════════════════════
"""
import time
from utils import db
from utils.log import log
from utils.log import simdi_tr


def _ilk_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS saat_etkilesim (
                    saat       INTEGER PRIMARY KEY,
                    paylasim   INTEGER DEFAULT 0,
                    oy         INTEGER DEFAULT 0
                )
            """)
    except Exception as e:
        log("UYARI", f"Zamanlama kurulum: {e}")


def paylasim_kaydet(saat: int | None = None) -> None:
    """Bir saatte paylaşım yapıldığını kaydet."""
    if saat is None:
        saat = simdi_tr().hour
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            c.execute("INSERT OR IGNORE INTO saat_etkilesim (saat) VALUES (?)", (saat,))
            c.execute("UPDATE saat_etkilesim SET paylasim=paylasim+1 WHERE saat=?", (saat,))
    except Exception:
        pass


def oy_kaydet(saat: int | None = None) -> None:
    """Bir saatte oy alındığını kaydet (etkileşim sinyali)."""
    if saat is None:
        saat = simdi_tr().hour
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            c.execute("INSERT OR IGNORE INTO saat_etkilesim (saat) VALUES (?)", (saat,))
            c.execute("UPDATE saat_etkilesim SET oy=oy+1 WHERE saat=?", (saat,))
    except Exception:
        pass


def altin_saat_mi(saat: int | None = None, min_veri: int = 20) -> bool:
    """Bu saat ortalamanın üstünde etkileşim alıyor mu? (altın saat)
    Yeterli veri yoksa False (sabit kurallara bırak)."""
    if saat is None:
        saat = simdi_tr().hour
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            satirlar = c.execute("SELECT saat, paylasim, oy FROM saat_etkilesim").fetchall()
        toplam_p = sum(r["paylasim"] for r in satirlar)
        if toplam_p < min_veri:
            return False
        # Her saatin oy/paylaşım oranı
        oranlar = {}
        for r in satirlar:
            if r["paylasim"] >= 2:
                oranlar[r["saat"]] = r["oy"] / r["paylasim"]
        if not oranlar:
            return False
        ort = sum(oranlar.values()) / len(oranlar)
        bu_saat = oranlar.get(saat, 0)
        return bu_saat > ort * 1.2   # ortalamanın %20 üstü → altın
    except Exception:
        return False


def en_iyi_saatler(n: int = 3) -> list:
    """En yüksek etkileşimli saatleri döndür (/zamanlama için)."""
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT saat, paylasim, oy FROM saat_etkilesim WHERE paylasim >= 2"
            ).fetchall()
        oranli = [(r["saat"], round(r["oy"] / r["paylasim"], 2), r["paylasim"])
                  for r in satirlar]
        oranli.sort(key=lambda x: x[1], reverse=True)
        return oranli[:n]
    except Exception:
        return []


def istatistik() -> dict:
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            r = c.execute("SELECT SUM(paylasim) p, SUM(oy) o FROM saat_etkilesim").fetchone()
            return {"toplam_paylasim": r["p"] or 0, "toplam_oy": r["o"] or 0,
                    "en_iyi": en_iyi_saatler(3)}
    except Exception:
        return {"toplam_paylasim": 0, "toplam_oy": 0, "en_iyi": []}
