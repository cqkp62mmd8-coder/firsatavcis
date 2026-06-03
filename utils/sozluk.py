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
    # v22.14 — Çöp/bağlam kelimeleri (model zehirlenmesini önle)
    "var", "yok", "stokta", "normal", "ucuz", "ücretsiz", "kargo",
    "sepette", "sepet", "kupon", "kod", "şimdi", "hemen", "son",
    "amazon", "trendyol", "hepsiburada", "n11", "mediamarkt", "teknosa",
    "vatan", "gittigidiyor", "morhipo", "boyner", "tr", "türkiye",
    "elektronik", "giyim", "kozmetik", "spor", "kitap", "market",
    "ürün", "ürünleri", "ürünler", "lira", "ek", "varan", "kadar",
    # v23.11 — Botun KENDİ şablon kelimeleri (kendinden öğrenmeyi önle)
    "marka", "kampanyası", "kampanyasi", "elit", "fırsat", "firsat",
    "ürünü", "urunu", "ye", "ya", "den", "dan", "satıcı", "satici",
    "depo", "resmi", "official", "garantili", "garanti",
}

# v22.14 — Sözlüğe asla girmemesi gereken çöp kalıplar
_COP_KELIME = {"var", "amazon", "tr", "indirimli", "fiyat", "yok",
               "trendyol", "hepsiburada", "normal", "stokta", "market"}


def ogren(urun_adi: str) -> int:
    """Kaliteli bir ürün adından kelimeleri öğren. Döner: öğrenilen kelime sayısı.

    v22.14: Ürün adı makul değilse HİÇ öğrenme (model zehirlenmesini önler).
    'var Amazon TR', '- İndirimli Fiyat' gibi çöpten kelime öğrenmek
    sözlüğü bozuyordu.
    """
    if not urun_adi or len(urun_adi) < 4:
        return 0
    # Makullük kapısı — çöp ürün adından öğrenme
    try:
        from services.analiz import _urun_adi_makul
        if not _urun_adi_makul(urun_adi):
            return 0
    except Exception:
        pass
    _ilk_kurulum()
    kelimeler = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{2,}", urun_adi)
    ogrenilen = 0
    try:
        simdi = int(time.time())
        with db.cursor() as c:
            for k in kelimeler:
                kl = k.replace("İ", "i").replace("I", "ı").lower()
                # v23.11 — Çöp/durdurma/salt-rakam VEYA 3 harften kısa → atla.
                # 2 harfli "ye", "ek" gibi ek/parçalar sözlüğü kirletiyordu.
                # (Model kodları "s24" rakam içerir, onlar zaten 3+ karakter.)
                harf_say = sum(1 for c2 in kl if c2.isalpha())
                if (kl in _DURDUR or kl in _COP_KELIME or kl.isdigit()
                        or (harf_say > 0 and harf_say < 3 and not any(c2.isdigit() for c2 in kl))):
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


def zehir_temizle() -> dict:
    """v22.14 — Sözlükteki çöp kelimeleri (var, amazon, tr...) sil.
    Eski zehirlenmiş veriyi temizler. Döner: {silinen}."""
    _ilk_kurulum()
    silinen = 0
    try:
        with db.cursor() as c:
            for kelime in (_COP_KELIME | _DURDUR):
                cur = c.execute("DELETE FROM kelime_sozluk WHERE kelime=?", (kelime,))
                silinen += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            # Salt rakam olan kelimeleri de sil
            c.execute("DELETE FROM kelime_sozluk WHERE kelime GLOB '[0-9]*'")
            # v23.11 — 2 harften kısa kelimeleri sil ("ye", "ek" gibi parçalar)
            # (rakam içerenler model kodu olabilir, onları koru)
            cur2 = c.execute(
                "DELETE FROM kelime_sozluk WHERE length(kelime) < 3 "
                "AND kelime NOT GLOB '*[0-9]*'")
            silinen += cur2.rowcount if cur2.rowcount and cur2.rowcount > 0 else 0
    except Exception as e:
        log("UYARI", f"Sözlük zehir temizle: {e}")
    return {"silinen": silinen}
