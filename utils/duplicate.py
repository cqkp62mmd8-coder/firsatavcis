"""
═══════════════════════════════════════════════════════════════════════
DUPLICATE ENGELLEME (v22)

Sorun: Aynı ürün farklı kanallardan defalarca geliyor → aynı fırsat
birkaç kez paylaşılıyor → kanal kalitesi düşüyor.

Çözüm: Bir ürün paylaşıldığında kalıcı işaretle. DUPLICATE_GUN içinde
aynı ürün tekrar gelirse atla.

Eşleştirme: Link kimliği (urun_kimligi) → aynı ürünün farklı tag/ref'li
linkleri bile aynı kimliği döner (Amazon /dp/, Trendyol -p-, vb).
═══════════════════════════════════════════════════════════════════════
"""
import time
from typing import Optional

import config
from utils import db
from utils.log import log


def kaydet(linkler: list[str], urun_adi: Optional[str], kategori: Optional[str],
           magaza: Optional[str], mesaj_id: Optional[int]) -> None:
    """Bir paylaşımı kaydet. Bu ürünün kimlikleri kalıcı işaretlenir."""
    if not linkler:
        return
    try:
        from services.analiz import urun_kimligi
        simdi = int(time.time())
        with db.cursor() as c:
            for lnk in linkler:
                kimlik = urun_kimligi(lnk)
                if not kimlik:
                    continue
                # Aynı kimlik tekrarı → güncelle (en son paylaşım zamanı)
                c.execute(
                    "INSERT INTO duplicate_kayit (kimlik, urun_adi, kategori, magaza, mesaj_id, ts) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(kimlik) DO UPDATE SET ts=excluded.ts, mesaj_id=excluded.mesaj_id",
                    (kimlik, (urun_adi or "")[:200], kategori, magaza, mesaj_id, simdi)
                )
    except Exception as e:
        log("UYARI", f"Duplicate kayıt: {e}")


def daha_once_paylasildi_mi(linkler: list[str]) -> Optional[dict]:
    """Bu linklerin kimlikleri son DUPLICATE_GUN içinde paylaşıldı mı?
    Eğer evet ise eski paylaşım bilgisini döndür, hayırsa None.

    DUPLICATE_GUN=0 ise duplicate kontrolü kapalı → her zaman None."""
    if config.DUPLICATE_GUN <= 0 or not linkler:
        return None
    try:
        from services.analiz import urun_kimligi
        kesim = int(time.time()) - config.DUPLICATE_GUN * 86400
        kimlikler = [urun_kimligi(l) for l in linkler if l]
        kimlikler = [k for k in kimlikler if k]
        if not kimlikler:
            return None
        # IN sorgusu — herhangi biri yakın zamanda paylaşıldıysa duplicate
        with db.cursor() as c:
            placeholder = ",".join(["?"] * len(kimlikler))
            satir = c.execute(
                f"SELECT kimlik, urun_adi, kategori, magaza, ts FROM duplicate_kayit "
                f"WHERE kimlik IN ({placeholder}) AND ts >= ? "
                f"ORDER BY ts DESC LIMIT 1",
                kimlikler + [kesim]
            ).fetchone()
            if satir:
                kac_saat = (int(time.time()) - satir["ts"]) // 3600
                return {
                    "kimlik":   satir["kimlik"],
                    "urun":     satir["urun_adi"],
                    "magaza":   satir["magaza"],
                    "kac_saat": kac_saat,
                }
    except Exception as e:
        log("UYARI", f"Duplicate kontrol: {e}")
    return None


def istatistik() -> dict:
    """Duplicate istatistikleri."""
    try:
        with db.cursor() as c:
            toplam = c.execute("SELECT COUNT(*) n FROM duplicate_kayit").fetchone()["n"]
            son_gun = int(time.time()) - 86400
            son24 = c.execute(
                "SELECT COUNT(*) n FROM duplicate_kayit WHERE ts >= ?", (son_gun,)
            ).fetchone()["n"]
            return {"toplam_kayit": toplam, "son_24_saat": son24,
                    "engelleme_gun": config.DUPLICATE_GUN}
    except Exception:
        return {"toplam_kayit": 0, "son_24_saat": 0,
                "engelleme_gun": config.DUPLICATE_GUN}
