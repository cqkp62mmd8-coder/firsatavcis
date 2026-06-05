"""
═══════════════════════════════════════════════════════════════════════
KULLANICI İSTEK SİSTEMİ (v22.10 — Sistem 6)

Aboneler bota DM ile "şu ürünü arıyorum" diyebilir. Bot isteği kaydeder,
o ürünle eşleşen bir fırsat geldiğinde isteği yapan kullanıcıya haber verir.

Kullanım (kullanıcı tarafı):
  Kullanıcı bota: "ara iphone 15"  → istek kaydedilir
  Eşleşen ürün gelince → bot kullanıcıya DM: "Aradığın ürün geldi!"

Eşleştirme: istek kelimelerinin hepsi ürün adında/metinde geçiyorsa eşleşir.
═══════════════════════════════════════════════════════════════════════
"""
import time
from utils import db
from utils.log import log


def _ilk_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kullanici_istek (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici   INTEGER NOT NULL,
                    arama       TEXT NOT NULL,
                    ts          INTEGER NOT NULL,
                    aktif       INTEGER DEFAULT 1,
                    son_bildirim INTEGER DEFAULT 0
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_istek_aktif ON kullanici_istek(aktif)")
    except Exception as e:
        log("UYARI", f"İstek kurulum: {e}")


def istek_ekle(kullanici: int, arama: str) -> bool:
    """Kullanıcının ürün arama isteğini kaydet."""
    if not kullanici or not arama or len(arama.strip()) < 2:
        return False
    _ilk_kurulum()
    arama = arama.strip().lower()[:100]
    try:
        with db.cursor() as c:
            # Aynı kullanıcı aynı aramayı tekrar eklemesin
            var = c.execute(
                "SELECT id FROM kullanici_istek WHERE kullanici=? AND arama=? AND aktif=1",
                (kullanici, arama)
            ).fetchone()
            if var:
                return False
            # Kullanıcı başına max 10 aktif istek
            sayi = c.execute(
                "SELECT COUNT(*) n FROM kullanici_istek WHERE kullanici=? AND aktif=1",
                (kullanici,)
            ).fetchone()["n"]
            if sayi >= 10:
                return False
            c.execute(
                "INSERT INTO kullanici_istek (kullanici, arama, ts) VALUES (?, ?, ?)",
                (kullanici, arama, int(time.time()))
            )
        return True
    except Exception as e:
        log("UYARI", f"İstek ekle: {e}")
        return False


def istek_sil(kullanici: int, arama: str | None = None) -> int:
    """Kullanıcının isteğini/isteklerini sil. arama None ise hepsini."""
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            if arama:
                c.execute("UPDATE kullanici_istek SET aktif=0 WHERE kullanici=? AND arama=?",
                          (kullanici, arama.strip().lower()))
            else:
                c.execute("UPDATE kullanici_istek SET aktif=0 WHERE kullanici=?", (kullanici,))
            return c.rowcount
    except Exception:
        return 0


def isteklerim(kullanici: int) -> list:
    """Kullanıcının aktif isteklerini listele."""
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT arama FROM kullanici_istek WHERE kullanici=? AND aktif=1 ORDER BY ts DESC",
                (kullanici,)
            ).fetchall()
            return [r["arama"] for r in satirlar]
    except Exception:
        return []


def eslesenleri_bul(urun_adi: str, metin: str = "") -> list:
    """Bir ürün geldiğinde, eşleşen aktif istekleri bul.
    Döner: [(kullanici_id, arama), ...] — bildirim gönderilecekler."""
    if not urun_adi:
        return []
    _ilk_kurulum()
    havuz = (urun_adi + " " + (metin or "")).lower()
    eslesme = []
    try:
        simdi = int(time.time())
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT id, kullanici, arama, son_bildirim FROM kullanici_istek WHERE aktif=1"
            ).fetchall()
            for r in satirlar:
                kelimeler = r["arama"].split()
                # Tüm arama kelimeleri üründe geçiyorsa eşleşir
                if kelimeler and all(k in havuz for k in kelimeler):
                    # Aynı isteğe 6 saatte bir bildirim (spam değil)
                    if simdi - r["son_bildirim"] >= 6 * 3600:
                        eslesme.append((r["kullanici"], r["arama"]))
                        c.execute("UPDATE kullanici_istek SET son_bildirim=? WHERE id=?",
                                  (simdi, r["id"]))
    except Exception as e:
        log("UYARI", f"İstek eşleştirme: {e}")
    return eslesme


def istatistik() -> dict:
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            aktif = c.execute("SELECT COUNT(*) n FROM kullanici_istek WHERE aktif=1").fetchone()["n"]
            kullanici = c.execute(
                "SELECT COUNT(DISTINCT kullanici) n FROM kullanici_istek WHERE aktif=1"
            ).fetchone()["n"]
            return {"aktif_istek": aktif, "istek_yapan": kullanici}
    except Exception:
        return {"aktif_istek": 0, "istek_yapan": 0}


# ═══════════════════════════════════════════════════════════════════════
# KATEGORİ ABONELİĞİ (v23.19) — kişiselleştirme
# Kullanıcı bir KATEGORİye abone olur (örn "elektronik"), o kategoride
# fırsat çıkınca ona özel DM gider. Keyword isteğinden farkı: kalıcı ve
# kategori bazlı (tek tek ürün değil, tüm kategori).
# ═══════════════════════════════════════════════════════════════════════

def _kategori_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kategori_abone (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici INTEGER NOT NULL,
                    kategori  TEXT NOT NULL,
                    ts        INTEGER NOT NULL,
                    UNIQUE(kullanici, kategori)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_kabone_kat ON kategori_abone(kategori)")
    except Exception as e:
        log("UYARI", f"Kategori abone kurulum: {e}")


def kategori_abone_ol(kullanici: int, kategori: str) -> bool:
    """Kullanıcıyı bir kategoriye abone yap."""
    if not kullanici or not kategori:
        return False
    _kategori_kurulum()
    kat = kategori.strip().lower()
    try:
        with db.cursor() as c:
            c.execute("INSERT OR IGNORE INTO kategori_abone (kullanici, kategori, ts) "
                      "VALUES (?,?,?)", (kullanici, kat, int(time.time())))
        return True
    except Exception as e:
        log("UYARI", f"kategori_abone_ol: {e}")
        return False


def kategori_abone_iptal(kullanici: int, kategori: str | None = None) -> int:
    """Aboneliği iptal et. kategori None ise TÜM abonelikleri sil."""
    _kategori_kurulum()
    try:
        with db.cursor() as c:
            if kategori:
                cur = c.execute("DELETE FROM kategori_abone WHERE kullanici=? AND kategori=?",
                                (kullanici, kategori.strip().lower()))
            else:
                cur = c.execute("DELETE FROM kategori_abone WHERE kullanici=?", (kullanici,))
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    except Exception:
        return 0


def aboneliklerim(kullanici: int) -> list:
    """Kullanıcının abone olduğu kategoriler."""
    _kategori_kurulum()
    try:
        with db.cursor() as c:
            rows = c.execute("SELECT kategori FROM kategori_abone WHERE kullanici=? ORDER BY kategori",
                             (kullanici,)).fetchall()
        return [r["kategori"] for r in rows]
    except Exception:
        return []


def kategori_aboneleri(kategori: str) -> list:
    """Bir kategoriye abone olan kullanıcı ID'leri."""
    if not kategori:
        return []
    _kategori_kurulum()
    try:
        with db.cursor() as c:
            rows = c.execute("SELECT kullanici FROM kategori_abone WHERE kategori=?",
                             (kategori.strip().lower(),)).fetchall()
        return [r["kullanici"] for r in rows]
    except Exception:
        return []


def kategori_istatistik() -> dict:
    """Toplam abone, kategori dağılımı."""
    _kategori_kurulum()
    try:
        with db.cursor() as c:
            top = c.execute("SELECT COUNT(DISTINCT kullanici) n FROM kategori_abone").fetchone()
            dag = c.execute("SELECT kategori, COUNT(*) sayi FROM kategori_abone "
                            "GROUP BY kategori ORDER BY sayi DESC LIMIT 10").fetchall()
        return {"abone_sayisi": top["n"] if top else 0,
                "dagilim": [(r["kategori"], r["sayi"]) for r in dag]}
    except Exception:
        return {"abone_sayisi": 0, "dagilim": []}
