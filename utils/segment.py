"""
═══════════════════════════════════════════════════════════════════════
Kullanıcı Segmentasyon

Telegram inline butonlarına (🔥 vote_good / ❌ vote_fake) yapılan
tıklamaları kaydet. Çıkarılan bilgiler:

  • Hangi kategoriler en çok ilgi görüyor? (en çok 🔥)
  • Hangi mağazalar tıklanıyor?
  • Hangi indirim aralığı popüler? (örn. %30-50 vs %70+)
  • Saatlik aktivite (en yoğun saat)
  • Şüpheli işaretlenmiş mağaza/kategoriler

DB: kullanici_tikla (ts, kullanici_id, mesaj_id, oy_turu)
Mesaj meta: mesaj_meta (mesaj_id, kategori, magaza, indirim)
═══════════════════════════════════════════════════════════════════════
"""
import collections
import sqlite3
import time
from typing import Optional

import config
from utils.db import DB_FILE
from utils.log import log


def _baglanti() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # db.py ile aynı WAL modu — çoklu bağlantı kilitlenmesini önler
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
    except Exception:
        pass
    return conn


from contextlib import contextmanager


@contextmanager
def _baglan():
    """Bağlantıyı garanti kapatan context manager (sızıntı önler)."""
    conn = _baglanti()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


_tablo_kuruldu = False


def _ilk_kurulum() -> None:
    global _tablo_kuruldu
    if _tablo_kuruldu:
        return
    try:
        conn = _baglanti()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kullanici_tikla (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              INTEGER NOT NULL,
                kullanici_id    INTEGER,
                mesaj_id        INTEGER,
                oy_turu         TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mesaj_meta (
                mesaj_id        INTEGER PRIMARY KEY,
                ts              INTEGER NOT NULL,
                kategori        TEXT NOT NULL,
                magaza          TEXT,
                indirim         INTEGER,
                urun_adi        TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tikla_ts ON kullanici_tikla(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tikla_oy ON kullanici_tikla(oy_turu)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_kat ON mesaj_meta(kategori)")
        conn.commit()
        conn.close()
        _tablo_kuruldu = True
    except Exception as e:
        log("UYARI", f"Segment tablo kurulum: {e}")


def mesaj_kaydet(mesaj_id: int, kategori: str, magaza: str = "",
                 indirim: int = 0, urun_adi: str = "") -> None:
    """Her başarılı paylaşımdan sonra mesaj meta bilgisini kaydet.
    Bu, daha sonra tıklamalarla eşleştirilir."""
    if not mesaj_id:
        return
    _ilk_kurulum()
    try:
        conn = _baglanti()
        conn.execute(
            "INSERT OR REPLACE INTO mesaj_meta (mesaj_id, ts, kategori, magaza, indirim, urun_adi) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(mesaj_id), int(time.time()), kategori, magaza, int(indirim) if indirim else 0,
             urun_adi[:200] if urun_adi else "")
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log("UYARI", f"Mesaj meta kaydet: {e}")


def tikla_kaydet(kullanici_id: Optional[int], mesaj_id: Optional[int], oy_turu: str) -> bool:
    """Bir kullanıcının bir mesaja oy verdiğini kaydet.
    oy_turu: 'good' (🔥) veya 'fake' (❌)
    Döner: True = yeni oy kaydedildi, False = bu kullanıcı zaten oy vermiş."""
    _ilk_kurulum()
    try:
        with _baglan() as conn:
            # Aynı kullanıcı aynı mesaja daha önce oy verdi mi?
            if kullanici_id and mesaj_id:
                mevcut = conn.execute(
                    "SELECT oy_turu FROM kullanici_tikla WHERE kullanici_id=? AND mesaj_id=? LIMIT 1",
                    (int(kullanici_id), int(mesaj_id))
                ).fetchone()
                if mevcut:
                    # Oyunu değiştiriyorsa güncelle, aynıysa hiçbir şey yapma
                    if mevcut[0] == oy_turu:
                        return False
                    conn.execute(
                        "UPDATE kullanici_tikla SET oy_turu=?, ts=? WHERE kullanici_id=? AND mesaj_id=?",
                        (oy_turu, int(time.time()), int(kullanici_id), int(mesaj_id))
                    )
                    conn.commit()
                    return True
            conn.execute(
                "INSERT INTO kullanici_tikla (ts, kullanici_id, mesaj_id, oy_turu) VALUES (?, ?, ?, ?)",
                (int(time.time()), int(kullanici_id) if kullanici_id else None,
                 int(mesaj_id) if mesaj_id else None, oy_turu)
            )
            conn.commit()
            return True
    except Exception as e:
        log("UYARI", f"Tıklama kaydet: {e}")
        return False


def oy_sayilari(mesaj_id: int) -> tuple[int, int]:
    """Bir mesajın (🔥 good, ❌ fake) oy sayılarını döndür."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        rows = conn.execute(
            "SELECT oy_turu, COUNT(*) FROM kullanici_tikla WHERE mesaj_id=? GROUP BY oy_turu",
            (int(mesaj_id),)
        ).fetchall()
        conn.close()
        d = {r[0]: r[1] for r in rows}
        return d.get("good", 0), d.get("fake", 0)
    except Exception as e:
        log("UYARI", f"Oy sayıları: {e}")
        return 0, 0


def en_cok_oylanan(gun: int = 7, limit: int = 5) -> list[dict]:
    """Son N günde en çok 🔥 oyu alan mesajları döndür.
    Her kayıt: {mesaj_id, iyi, sahte, net}. net = iyi - sahte."""
    _ilk_kurulum()
    try:
        kesim = int(time.time()) - gun * 86400
        conn = _baglanti()
        rows = conn.execute(
            "SELECT mesaj_id, "
            "SUM(CASE WHEN oy_turu='good' THEN 1 ELSE 0 END) as iyi, "
            "SUM(CASE WHEN oy_turu='fake' THEN 1 ELSE 0 END) as sahte "
            "FROM kullanici_tikla WHERE ts >= ? AND mesaj_id IS NOT NULL "
            "GROUP BY mesaj_id ORDER BY iyi DESC LIMIT ?",
            (kesim, limit)
        ).fetchall()
        conn.close()
        return [
            {"mesaj_id": r[0], "iyi": r[1] or 0, "sahte": r[2] or 0,
             "net": (r[1] or 0) - (r[2] or 0)}
            for r in rows
        ]
    except Exception as e:
        log("UYARI", f"En çok oylanan: {e}")
        return []


def oy_ozeti(gun: int = 7) -> dict:
    """Son N günün toplam oy istatistiği."""
    _ilk_kurulum()
    try:
        kesim = int(time.time()) - gun * 86400
        conn = _baglanti()
        rows = conn.execute(
            "SELECT oy_turu, COUNT(*) FROM kullanici_tikla WHERE ts >= ? GROUP BY oy_turu",
            (kesim,)
        ).fetchall()
        conn.close()
        d = {r[0]: r[1] for r in rows}
        return {"iyi": d.get("good", 0), "sahte": d.get("fake", 0),
                "toplam": sum(d.values())}
    except Exception as e:
        log("UYARI", f"Oy özeti: {e}")
        return {"iyi": 0, "sahte": 0, "toplam": 0}


def begenilen_kategoriler(gun: int = 30, limit: int = 5) -> list[dict]:
    """Kategori bazlı beğeni analizi — hangi kategori en çok 🔥 alıyor.
    mesaj_meta (kategori) ile kullanici_tikla (oy) birleştirilir.
    Her kayıt: {kategori, iyi, sahte}."""
    _ilk_kurulum()
    try:
        kesim = int(time.time()) - gun * 86400
        conn = _baglanti()
        rows = conn.execute(
            "SELECT m.kategori, "
            "SUM(CASE WHEN t.oy_turu='good' THEN 1 ELSE 0 END) as iyi, "
            "SUM(CASE WHEN t.oy_turu='fake' THEN 1 ELSE 0 END) as sahte "
            "FROM kullanici_tikla t JOIN mesaj_meta m ON t.mesaj_id = m.mesaj_id "
            "WHERE t.ts >= ? GROUP BY m.kategori ORDER BY iyi DESC LIMIT ?",
            (kesim, limit)
        ).fetchall()
        conn.close()
        return [
            {"kategori": r[0], "iyi": r[1] or 0, "sahte": r[2] or 0}
            for r in rows
        ]
    except Exception as e:
        log("UYARI", f"Beğenilen kategoriler: {e}")
        return []


# ════════════════════════════════════════════════════════════════
# SORGULAR — ne tıklanıyor?
# ════════════════════════════════════════════════════════════════

def populer_kategoriler(gun: int = 7) -> list[dict]:
    """Son N günde en çok 🔥 alan kategoriler."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        kesim = int(time.time()) - gun * 86400
        rows = conn.execute("""
            SELECT m.kategori,
                   SUM(CASE WHEN k.oy_turu = 'good' THEN 1 ELSE 0 END) AS iyi_oy,
                   SUM(CASE WHEN k.oy_turu = 'fake' THEN 1 ELSE 0 END) AS sahte_oy,
                   COUNT(*) AS toplam_tikla
            FROM kullanici_tikla k
            JOIN mesaj_meta m ON k.mesaj_id = m.mesaj_id
            WHERE k.ts >= ?
            GROUP BY m.kategori
            ORDER BY iyi_oy DESC
        """, (kesim,)).fetchall()
        conn.close()
        return [
            {"kategori": r["kategori"], "iyi_oy": r["iyi_oy"],
             "sahte_oy": r["sahte_oy"], "toplam": r["toplam_tikla"]}
            for r in rows
        ]
    except Exception as e:
        log("UYARI", f"Popüler kategori sorgu: {e}")
        return []


def populer_magazalar(gun: int = 7) -> list[dict]:
    """Son N günde en çok 🔥 alan mağazalar."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        kesim = int(time.time()) - gun * 86400
        rows = conn.execute("""
            SELECT m.magaza,
                   SUM(CASE WHEN k.oy_turu = 'good' THEN 1 ELSE 0 END) AS iyi_oy,
                   SUM(CASE WHEN k.oy_turu = 'fake' THEN 1 ELSE 0 END) AS sahte_oy
            FROM kullanici_tikla k
            JOIN mesaj_meta m ON k.mesaj_id = m.mesaj_id
            WHERE k.ts >= ? AND m.magaza != ''
            GROUP BY m.magaza
            ORDER BY iyi_oy DESC
            LIMIT 20
        """, (kesim,)).fetchall()
        conn.close()
        return [
            {"magaza": r["magaza"], "iyi_oy": r["iyi_oy"], "sahte_oy": r["sahte_oy"]}
            for r in rows
        ]
    except Exception as e:
        log("UYARI", f"Popüler mağaza sorgu: {e}")
        return []


def supheli_magazalar(gun: int = 30) -> list[dict]:
    """Çok sahte oy alan mağazalar — kalite kontrolü için."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        kesim = int(time.time()) - gun * 86400
        rows = conn.execute("""
            SELECT m.magaza,
                   SUM(CASE WHEN k.oy_turu = 'fake' THEN 1 ELSE 0 END) AS sahte,
                   SUM(CASE WHEN k.oy_turu = 'good' THEN 1 ELSE 0 END) AS iyi
            FROM kullanici_tikla k
            JOIN mesaj_meta m ON k.mesaj_id = m.mesaj_id
            WHERE k.ts >= ? AND m.magaza != ''
            GROUP BY m.magaza
            HAVING sahte >= 3 AND sahte > iyi
            ORDER BY sahte DESC
        """, (kesim,)).fetchall()
        conn.close()
        return [
            {"magaza": r["magaza"], "sahte_oy": r["sahte"], "iyi_oy": r["iyi"]}
            for r in rows
        ]
    except Exception as e:
        return []


def saatlik_aktivite(gun: int = 7) -> list[int]:
    """Saatlik tıklama dağılımı (0-23) — son N gün."""
    _ilk_kurulum()
    saatler = [0] * 24
    try:
        conn = _baglanti()
        kesim = int(time.time()) - gun * 86400
        rows = conn.execute("""
            SELECT ts FROM kullanici_tikla WHERE ts >= ?
        """, (kesim,)).fetchall()
        conn.close()
        for r in rows:
            # UTC+3 (Türkiye)
            saat = (r["ts"] // 3600 + 3) % 24
            saatler[saat] += 1
        return saatler
    except Exception:
        return saatler


def istatistik() -> dict:
    """Genel istatistikler."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        toplam_tikla = conn.execute("SELECT COUNT(*) FROM kullanici_tikla").fetchone()[0]
        toplam_iyi = conn.execute(
            "SELECT COUNT(*) FROM kullanici_tikla WHERE oy_turu = 'good'"
        ).fetchone()[0]
        toplam_sahte = conn.execute(
            "SELECT COUNT(*) FROM kullanici_tikla WHERE oy_turu = 'fake'"
        ).fetchone()[0]
        benzersiz_kullanici = conn.execute(
            "SELECT COUNT(DISTINCT kullanici_id) FROM kullanici_tikla WHERE kullanici_id IS NOT NULL"
        ).fetchone()[0]
        mesaj_meta = conn.execute("SELECT COUNT(*) FROM mesaj_meta").fetchone()[0]
        conn.close()
        return {
            "toplam_tikla":         toplam_tikla,
            "iyi_oy":               toplam_iyi,
            "sahte_oy":             toplam_sahte,
            "benzersiz_kullanici":  benzersiz_kullanici,
            "kayitli_mesaj":        mesaj_meta,
        }
    except Exception:
        return {}


def temizle_eski(gun: int = 180) -> int:
    """N günden eski tıklamaları sil."""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        kesim = int(time.time()) - gun * 86400
        cur = conn.execute("DELETE FROM kullanici_tikla WHERE ts < ?", (kesim,))
        n = cur.rowcount
        conn.execute("DELETE FROM mesaj_meta WHERE ts < ?", (kesim,))
        conn.commit()
        conn.close()
        return n
    except Exception:
        return 0
