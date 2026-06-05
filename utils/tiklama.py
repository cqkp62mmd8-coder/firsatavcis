"""
═══════════════════════════════════════════════════════════════════════
TIKLAMA TAKİBİ (v23.18) — DORMANT (varsayılan KAPALI)

Affiliate gelir ölçümünün temeli. Her paylaşılan ürüne kısa bir kimlik
verir; kullanıcı butona tıklayınca (redirect üzerinden) tıklama kaydedilir.

ÖNEMLİ: Bu modülün VARLIĞI hiçbir şeyi aktif etmez. Sadece
config.TIKLAMA_TAKIP_AKTIF=True olunca devreye girer. Kapalıyken bot
bugünküyle birebir aynı davranır — bu modül sadece veri saklar, bekler.

Tablolar:
  tiklama_urun   — kısa_id → (urun_adi, kategori, hedef_url, fiyat, ts)
  tiklama_olay   — her tıklama olayı (kısa_id, ts)
═══════════════════════════════════════════════════════════════════════
"""
import time
import secrets
import string

from utils import db
from utils.log import log

_KURULU = False
_ALFABE = string.ascii_lowercase + string.digits


def _ilk_kurulum() -> None:
    global _KURULU
    if _KURULU:
        return
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS tiklama_urun (
                    kisa_id   TEXT PRIMARY KEY,
                    urun_adi  TEXT,
                    kategori  TEXT,
                    hedef_url TEXT NOT NULL,
                    fiyat     REAL,
                    magaza    TEXT,
                    ts        INTEGER
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS tiklama_olay (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    kisa_id  TEXT,
                    ts       INTEGER
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_tiklama_olay_kid ON tiklama_olay(kisa_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tiklama_olay_ts ON tiklama_olay(ts)")
        _KURULU = True
    except Exception as e:
        log("UYARI", f"tiklama kurulum: {e}")


def _yeni_id(uzunluk: int = 7) -> str:
    """Çakışmayan kısa kimlik üret (örn 'k3f9x2a')."""
    for _ in range(6):
        kid = "".join(secrets.choice(_ALFABE) for _ in range(uzunluk))
        try:
            with db.cursor() as c:
                var = c.execute("SELECT 1 FROM tiklama_urun WHERE kisa_id=?", (kid,)).fetchone()
            if not var:
                return kid
        except Exception:
            return kid
    return "".join(secrets.choice(_ALFABE) for _ in range(uzunluk + 2))


def urun_kaydet(hedef_url: str, urun_adi: str = "", kategori: str = "",
                fiyat: float = 0.0, magaza: str = "") -> str | None:
    """Bir ürünü kaydet, kısa kimliğini döndür. hedef_url = gerçek (affiliate) link.

    Döner: kısa_id (redirect URL'de kullanılır) veya None (hata).
    """
    if not hedef_url:
        return None
    _ilk_kurulum()
    try:
        kid = _yeni_id()
        with db.cursor() as c:
            c.execute(
                "INSERT INTO tiklama_urun (kisa_id, urun_adi, kategori, hedef_url, fiyat, magaza, ts) "
                "VALUES (?,?,?,?,?,?,?)",
                (kid, urun_adi[:200], kategori[:50], hedef_url, fiyat or 0.0,
                 magaza[:50], int(time.time())),
            )
        return kid
    except Exception as e:
        log("UYARI", f"tiklama urun_kaydet: {e}")
        return None


def hedef_bul(kisa_id: str) -> dict | None:
    """Kısa kimlikten hedef URL + ürün bilgisini getir (redirect için)."""
    if not kisa_id:
        return None
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            r = c.execute(
                "SELECT kisa_id, urun_adi, kategori, hedef_url, fiyat, magaza "
                "FROM tiklama_urun WHERE kisa_id=?", (kisa_id,)).fetchone()
        if not r:
            return None
        return dict(r)
    except Exception:
        return None


def tiklama_kaydet(kisa_id: str) -> None:
    """Bir tıklama olayını kaydet (redirect anında çağrılır)."""
    if not kisa_id:
        return
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            c.execute("INSERT INTO tiklama_olay (kisa_id, ts) VALUES (?,?)",
                      (kisa_id, int(time.time())))
    except Exception as e:
        log("UYARI", f"tiklama_kaydet: {e}")


def istatistik(gun: int = 7) -> dict:
    """Son N günün tıklama istatistiği: toplam, en çok tıklanan ürünler,
    kategori dağılımı, saatlik dağılım."""
    _ilk_kurulum()
    sonuc = {"toplam": 0, "en_cok": [], "kategori": [], "saatlik": {}}
    try:
        esik = int(time.time()) - gun * 86400
        with db.cursor() as c:
            r = c.execute("SELECT COUNT(*) n FROM tiklama_olay WHERE ts>=?", (esik,)).fetchone()
            sonuc["toplam"] = r["n"] if r else 0

            # En çok tıklanan ürünler
            rows = c.execute("""
                SELECT u.urun_adi, u.kategori, COUNT(o.id) AS sayi
                FROM tiklama_olay o JOIN tiklama_urun u ON o.kisa_id=u.kisa_id
                WHERE o.ts>=? GROUP BY o.kisa_id ORDER BY sayi DESC LIMIT 10
            """, (esik,)).fetchall()
            sonuc["en_cok"] = [(r["urun_adi"], r["sayi"]) for r in rows]

            # Kategori dağılımı
            krows = c.execute("""
                SELECT u.kategori, COUNT(o.id) AS sayi
                FROM tiklama_olay o JOIN tiklama_urun u ON o.kisa_id=u.kisa_id
                WHERE o.ts>=? AND u.kategori!='' GROUP BY u.kategori ORDER BY sayi DESC LIMIT 8
            """, (esik,)).fetchall()
            sonuc["kategori"] = [(r["kategori"], r["sayi"]) for r in krows]
    except Exception as e:
        log("UYARI", f"tiklama istatistik: {e}")
    return sonuc


def link_sar(hedef_url: str, urun_adi: str = "", kategori: str = "",
             fiyat: float = 0.0, magaza: str = "") -> str:
    """Hedef linki redirect URL'sine sar — SADECE takip aktifse.

    Kapalıysa (varsayılan) hedef linki AYNEN döndürür → davranış değişmez.
    Açıksa: ürünü kaydeder, kısa redirect URL'si döndürür.
    """
    import config
    if not getattr(config, "TIKLAMA_TAKIP_AKTIF", False):
        return hedef_url  # DORMANT — hiçbir şey değişmez
    base = getattr(config, "TIKLAMA_BASE_URL", "")
    if not base:
        return hedef_url  # base URL yoksa sarmadan geç (güvenli)
    kid = urun_kaydet(hedef_url, urun_adi, kategori, fiyat, magaza)
    if not kid:
        return hedef_url
    return f"{base}/git/{kid}"
