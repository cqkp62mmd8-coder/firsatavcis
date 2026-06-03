"""
#14 — Telemetri: her olayı SQLite'a kaydet.
Olaylar:
  • paylasildi  — bot kanala mesaj attı
  • reddedildi  — filtreye takıldı
  • hata        — exception
  • sahte       — sahte indirim tespiti
  • cikis       — tıklama (gelecekte link redirect ile)
"""
import json

from utils import db
from utils.log import simdi_tr


def kayit(olay: str, *,
          magaza: str | None = None,
          kategori: str | None = None,
          kaynak: str | None = None,
          indirim: int | None = None,
          skor: float | None = None,
          veri: dict | None = None) -> None:
    """Hızlı, fire-and-forget metrik kaydı."""
    try:
        with db.cursor() as c:
            c.execute("""
                INSERT INTO metrik(olusturma, olay, magaza, kategori, kaynak, indirim, skor, veri_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                simdi_tr().timestamp(), olay, magaza, kategori, kaynak,
                indirim, skor,
                json.dumps(veri, ensure_ascii=False) if veri else None,
            ))
    except Exception:
        pass   # Metrik fail-silent — bot çalışması bozulmamalı


def son_n_saat(saat: int = 24) -> dict:
    """Son N saatte hangi olay kaç kez? Admin /rapor için."""
    esik = simdi_tr().timestamp() - saat * 3600
    sonuc = {}
    try:
        with db.cursor() as c:
            c.execute("""
                SELECT olay, COUNT(*) as n
                FROM metrik
                WHERE olusturma >= ?
                GROUP BY olay
            """, (esik,))
            sonuc = {r["olay"]: r["n"] for r in c.fetchall()}
    except Exception:
        pass
    return sonuc


def temizle_eski(gun: int = 30) -> int:
    """Eski metrikleri sil (default 30 gün)."""
    return db.temizle_eski("metrik", "olusturma", gun * 86400)
