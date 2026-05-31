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
