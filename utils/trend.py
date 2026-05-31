"""
═══════════════════════════════════════════════════════════════════════
Trend Analizi — son 24h/7g'de kategori & mağaza eğilimleri
utils.db'nin cursor() context manager'ını kullanır.
═══════════════════════════════════════════════════════════════════════
"""
import time
from utils.db import cursor
from utils.log import log

_tablo_kuruldu = False


def _tablo_olustur() -> None:
    global _tablo_kuruldu
    if _tablo_kuruldu:
        return
    try:
        with cursor() as c:
            # v22.4 — Şema doğrulaması: tablo varsa ama yanlış şemadaysa
            # (örn. duplicate.py'nin eski çatışan şeması), yedekle ve yeniden kur.
            row = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='paylasim_kayit'"
            ).fetchone()
            if row:
                # Tablo var — şemasını doğrula
                kolonlar = {r["name"] for r in c.execute("PRAGMA table_info(paylasim_kayit)").fetchall()}
                if "ana_kat" not in kolonlar:
                    # Yanlış şema → eski tabloyu yedekle, yeniden oluştur
                    c.execute("ALTER TABLE paylasim_kayit RENAME TO paylasim_kayit_bozuk")
                    log("UYARI", "paylasim_kayit yanlış şemada bulundu — yeniden oluşturuluyor")

            c.execute("""
                CREATE TABLE IF NOT EXISTS paylasim_kayit (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        INTEGER NOT NULL,
                    ana_kat   TEXT NOT NULL,
                    alt_kat   TEXT DEFAULT '',
                    magaza    TEXT DEFAULT '',
                    indirim   INTEGER DEFAULT 0
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_paylasim_ts ON paylasim_kayit(ts)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_paylasim_ana ON paylasim_kayit(ana_kat, ts)")
        _tablo_kuruldu = True
    except Exception as e:
        log("UYARI", f"Trend tablosu oluşturma: {e}")


def kaydet(ana_kat: str, alt_kat: str = "", magaza: str = "", indirim: int = 0) -> None:
    """Başarılı bir paylaşımı trend DB'ye ekle."""
    _tablo_olustur()
    try:
        with cursor() as c:
            c.execute(
                "INSERT INTO paylasim_kayit (ts, ana_kat, alt_kat, magaza, indirim) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(time.time()), ana_kat, alt_kat or "", magaza or "", indirim),
            )
    except Exception as e:
        log("UYARI", f"Trend kayıt: {e}")


def son_n_saat(saat: int = 24) -> dict:
    """Son N saatte kategori/mağaza dağılımı."""
    _tablo_olustur()
    try:
        kesim = int(time.time()) - saat * 3600
        with cursor() as c:
            c.execute(
                "SELECT ana_kat, COUNT(*) as cc FROM paylasim_kayit WHERE ts >= ? "
                "GROUP BY ana_kat ORDER BY cc DESC", (kesim,))
            ana_dag = [(r["ana_kat"], r["cc"]) for r in c.fetchall()]
            c.execute(
                "SELECT magaza, COUNT(*) as cc, AVG(indirim) as ort FROM paylasim_kayit "
                "WHERE ts >= ? AND magaza != '' GROUP BY magaza ORDER BY cc DESC LIMIT 10", (kesim,))
            magaza_dag = [(r["magaza"], r["cc"], round(r["ort"] or 0, 1)) for r in c.fetchall()]
            c.execute("SELECT COUNT(*) as cc FROM paylasim_kayit WHERE ts >= ?", (kesim,))
            toplam = c.fetchone()["cc"]
        return {"saat": saat, "toplam": toplam, "kategoriler": ana_dag, "magazalar": magaza_dag}
    except Exception as e:
        log("UYARI", f"Son N saat: {e}")
        return {"saat": saat, "toplam": 0, "kategoriler": [], "magazalar": []}


def yukselen_kategoriler(saat: int = 24) -> list[tuple[str, float]]:
    """Son N saatte normalden fazla görülen kategoriler."""
    _tablo_olustur()
    try:
        simdi = int(time.time())
        son_kesim = simdi - saat * 3600
        eski_basla = simdi - 7 * 24 * 3600
        with cursor() as c:
            c.execute("SELECT ana_kat, COUNT(*) as cc FROM paylasim_kayit WHERE ts >= ? GROUP BY ana_kat",
                      (son_kesim,))
            son_sayim = {r["ana_kat"]: r["cc"] for r in c.fetchall()}
            c.execute("SELECT ana_kat, COUNT(*) as cc FROM paylasim_kayit WHERE ts >= ? AND ts < ? GROUP BY ana_kat",
                      (eski_basla, son_kesim))
            eski_sayim = {r["ana_kat"]: r["cc"] for r in c.fetchall()}

        son_sb = {k: v / saat for k, v in son_sayim.items()}
        eski_pencere = max(1, (son_kesim - eski_basla) / 3600)
        eski_sb = {k: v / eski_pencere for k, v in eski_sayim.items()}

        yukselen = []
        for kat, so in son_sb.items():
            eo = eski_sb.get(kat, 0.01) or 0.01
            artis = so / eo
            if artis >= 2.0 and son_sayim.get(kat, 0) >= 3:
                yukselen.append((kat, round(artis, 2)))
        yukselen.sort(key=lambda x: -x[1])
        return yukselen
    except Exception as e:
        log("UYARI", f"Yükselen kategoriler: {e}")
        return []


def temizle_eski(gun: int = 30) -> int:
    _tablo_olustur()
    try:
        kesim = int(time.time()) - gun * 24 * 3600
        with cursor() as c:
            c.execute("DELETE FROM paylasim_kayit WHERE ts < ?", (kesim,))
            return c.rowcount
    except Exception as e:
        log("UYARI", f"Trend temizle: {e}")
        return 0
