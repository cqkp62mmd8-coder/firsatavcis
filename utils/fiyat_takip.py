"""
═══════════════════════════════════════════════════════════════════════
FİYAT TAKİP & STOK GERİ-GELME (v22.10 — Sistem 4 + 5)

Sistem 4: Bir ürünün fiyatını zaman içinde izler. Yeni paylaşımda fiyat
  geçmişe göre DÜŞMÜŞSE "💎 son N günün en düşüğü" rozeti verir.
  Sahte indirimi de yakalar: fiyat hep aynıysa "%80 indirim" yalandır.

Sistem 5: Tükenen popüler ürün tekrar stoğa girince (yeni paylaşım gelince)
  bunu tespit eder ve "🔄 yeniden stokta" işareti koyar.

Hepsi ürün_kimligi (link bazlı normalize) üzerinden çalışır.
═══════════════════════════════════════════════════════════════════════
"""
import time
from utils import db
from utils.log import log


def _ilk_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS fiyat_gecmis (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    kimlik    TEXT NOT NULL,
                    fiyat     REAL NOT NULL,
                    ts        INTEGER NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fiyat_kimlik ON fiyat_gecmis(kimlik, ts)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS stok_durum (
                    kimlik     TEXT PRIMARY KEY,
                    son_gorulme INTEGER,
                    durum      TEXT DEFAULT 'aktif'
                )
            """)
    except Exception as e:
        log("UYARI", f"Fiyat takip kurulum: {e}")


def fiyat_kaydet(kimlik: str, fiyat: float) -> None:
    """Bir ürünün güncel fiyatını geçmişe ekle."""
    if not kimlik or not fiyat or fiyat <= 0:
        return
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            c.execute(
                "INSERT INTO fiyat_gecmis (kimlik, fiyat, ts) VALUES (?, ?, ?)",
                (kimlik, float(fiyat), int(time.time()))
            )
            # Eski kayıtları buda (ürün başına son 20 yeter)
            c.execute("""
                DELETE FROM fiyat_gecmis WHERE kimlik=? AND id NOT IN (
                    SELECT id FROM fiyat_gecmis WHERE kimlik=? ORDER BY ts DESC LIMIT 20
                )
            """, (kimlik, kimlik))
    except Exception as e:
        log("UYARI", f"Fiyat kaydet: {e}")


def fiyat_analiz(kimlik: str, guncel_fiyat: float, gun: int = 30) -> dict:
    """Güncel fiyatı geçmişle kıyasla. Döner:
    {en_dusuk_mu, sahte_indirim_mi, gecmis_min, gecmis_max, kayit_sayisi}"""
    sonuc = {"en_dusuk_mu": False, "sahte_indirim_mi": False,
             "gecmis_min": None, "gecmis_max": None, "kayit_sayisi": 0}
    if not kimlik or not guncel_fiyat or guncel_fiyat <= 0:
        return sonuc
    _ilk_kurulum()
    try:
        kesim = int(time.time()) - gun * 86400
        with db.cursor() as c:
            satirlar = c.execute(
                "SELECT fiyat FROM fiyat_gecmis WHERE kimlik=? AND ts>=?",
                (kimlik, kesim)
            ).fetchall()
        fiyatlar = [r["fiyat"] for r in satirlar]
        sonuc["kayit_sayisi"] = len(fiyatlar)
        if not fiyatlar:
            return sonuc
        gmin, gmax = min(fiyatlar), max(fiyatlar)
        sonuc["gecmis_min"] = gmin
        sonuc["gecmis_max"] = gmax
        # Güncel fiyat geçmiş minimumdan düşük/eşit → en düşük
        if guncel_fiyat <= gmin:
            sonuc["en_dusuk_mu"] = True
        # Fiyat hiç değişmemiş (min≈max) ama "indirim" deniyor → sahte
        if len(fiyatlar) >= 3 and abs(gmax - gmin) < gmax * 0.02:
            sonuc["sahte_indirim_mi"] = True
    except Exception as e:
        log("UYARI", f"Fiyat analiz: {e}")
    return sonuc


def stok_kontrol(kimlik: str) -> str:
    """Bu ürün daha önce görülüp 'tükendi' işaretlendiyse ve şimdi tekrar
    geldiyse 'yeniden_stokta' döner. İlk görülüyorsa 'yeni'. Döner: durum."""
    if not kimlik:
        return "yeni"
    _ilk_kurulum()
    try:
        simdi = int(time.time())
        with db.cursor() as c:
            r = c.execute("SELECT son_gorulme, durum FROM stok_durum WHERE kimlik=?",
                          (kimlik,)).fetchone()
            if not r:
                c.execute(
                    "INSERT INTO stok_durum (kimlik, son_gorulme, durum) VALUES (?, ?, 'aktif')",
                    (kimlik, simdi))
                return "yeni"
            # 7 günden uzun süre görülmediyse → yeniden stokta sayılır
            durum = "yeniden_stokta" if (simdi - r["son_gorulme"]) > 7 * 86400 else "tekrar"
            c.execute("UPDATE stok_durum SET son_gorulme=?, durum='aktif' WHERE kimlik=?",
                      (simdi, kimlik))
            return durum
    except Exception as e:
        log("UYARI", f"Stok kontrol: {e}")
        return "yeni"


def istatistik() -> dict:
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            urun = c.execute("SELECT COUNT(DISTINCT kimlik) n FROM fiyat_gecmis").fetchone()["n"]
            kayit = c.execute("SELECT COUNT(*) n FROM fiyat_gecmis").fetchone()["n"]
            return {"izlenen_urun": urun, "fiyat_kaydi": kayit}
    except Exception:
        return {"izlenen_urun": 0, "fiyat_kaydi": 0}
