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
    return conn


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


def tikla_kaydet(kullanici_id: Optional[int], mesaj_id: Optional[int], oy_turu: str) -> None:
    """Bir kullanıcının bir mesaja oy verdiğini kaydet.
    oy_turu: 'good' (🔥) veya 'fake' (❌)"""
    _ilk_kurulum()
    try:
        conn = _baglanti()
        conn.execute(
            "INSERT INTO kullanici_tikla (ts, kullanici_id, mesaj_id, oy_turu) VALUES (?, ?, ?, ?)",
            (int(time.time()), int(kullanici_id) if kullanici_id else None,
             int(mesaj_id) if mesaj_id else None, oy_turu)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log("UYARI", f"Tıklama kaydet: {e}")


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
