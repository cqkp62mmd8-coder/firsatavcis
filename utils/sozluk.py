"""
═══════════════════════════════════════════════════════════════════════
KELİME SÖZLÜĞÜ (v22.7 — Sistem 6: kendi kendine büyüyen)

Bot gördüğü her DOĞRU üründen marka/model kelimelerini öğrenip kalıcı
sözlüğe ekler. Zamanla "bu kelime ürün adıdır" bilgisi zenginleşir,
ML'e bağımlılık azalır, yedek sistem güçlenir.

Mantık:
  • Gemini veya admin onayı ile gelen kaliteli ürün adlarından kelime çıkar
  • Sık geçen kelimeler "ürün kelimesi" olarak işaretlenir (SQLite kalıcı)
  • urun_adi_bul yedek modu bu sözlüğü kullanarak daha iyi ad çıkarır
═══════════════════════════════════════════════════════════════════════
"""
import re
import time
from utils import db
from utils.log import log


def _ilk_kurulum() -> None:
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kelime_sozluk (
                    kelime   TEXT PRIMARY KEY,
                    sayi     INTEGER DEFAULT 1,
                    tur      TEXT DEFAULT 'urun',
                    ts       INTEGER
                )
            """)
    except Exception as e:
        log("UYARI", f"Sözlük kurulum: {e}")


_DURDUR = {
    "ve", "ile", "için", "the", "bir", "tüm", "yeni", "adet", "set",
    "tl", "indirim", "indirimli", "fiyat", "kampanya", "fırsat",
}


def ogren(urun_adi: str) -> int:
    """Kaliteli bir ürün adından kelimeleri öğren. Döner: öğrenilen kelime sayısı."""
    if not urun_adi or len(urun_adi) < 4:
        return 0
    _ilk_kurulum()
    kelimeler = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{2,}", urun_adi)
    ogrenilen = 0
    try:
        simdi = int(time.time())
        with db.cursor() as c:
            for k in kelimeler:
                kl = k.replace("İ", "i").replace("I", "ı").lower()
                if kl in _DURDUR or len(kl) < 2:
                    continue
                c.execute(
                    "INSERT INTO kelime_sozluk (kelime, sayi, ts) VALUES (?, 1, ?) "
                    "ON CONFLICT(kelime) DO UPDATE SET sayi=sayi+1, ts=excluded.ts",
                    (kl, simdi)
                )
                ogrenilen += 1
    except Exception as e:
        log("UYARI", f"Sözlük öğren: {e}")
    return ogrenilen


def urun_kelimesi_mi(kelime: str, min_sayi: int = 2) -> bool:
    """Bu kelime sözlükte ürün kelimesi olarak biliniyor mu?"""
    if not kelime:
        return False
    _ilk_kurulum()
    try:
        kl = kelime.replace("İ", "i").replace("I", "ı").lower()
        with db.cursor() as c:
            r = c.execute(
                "SELECT sayi FROM kelime_sozluk WHERE kelime=? AND sayi>=?",
                (kl, min_sayi)
            ).fetchone()
            return r is not None
    except Exception:
        return False


def istatistik() -> dict:
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            toplam = c.execute("SELECT COUNT(*) n FROM kelime_sozluk").fetchone()["n"]
            guclu = c.execute("SELECT COUNT(*) n FROM kelime_sozluk WHERE sayi>=3").fetchone()["n"]
            en_sik = c.execute(
                "SELECT kelime, sayi FROM kelime_sozluk ORDER BY sayi DESC LIMIT 5"
            ).fetchall()
            return {
                "toplam_kelime": toplam,
                "guclu_kelime": guclu,
                "en_sik": [(r["kelime"], r["sayi"]) for r in en_sik],
            }
    except Exception:
        return {"toplam_kelime": 0, "guclu_kelime": 0, "en_sik": []}
