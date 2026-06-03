"""
═══════════════════════════════════════════════════════════════════════
ÜRÜN HAFIZASI — Gemini'siz öğrenmenin çekirdeği

Sorun: Günde 1000+ mesaj geliyor ama bot her seferinde sıfırdan tahmin
ediyor — hiçbir şey hatırlamıyor. Oysa fırsatların çoğu TEKRAR EDEN
markalar/ürünler (Amazon, Trendyol, aynı markalar her gün).

Çözüm: Her ürünü/markayı kalıcı (SQLite) hafızaya yaz. Aynı ürün veya
marka tekrar geldiğinde, öğrenilen kategoriyi HATIRLA — sıfırdan tahmin
etme. Bu, Gemini'ye hiç ihtiyaç duymadan zamanla isabeti artırır.

Üç katman:
  1. Tam ürün eşleşmesi (link kimliği) → birebir hatırla
  2. Marka eşleşmesi → markanın baskın kategorisini kullan
  3. Hiçbiri yoksa → normal tahmine bırak

Öğrenme tamamen YEREL ve KALICI — restart'ta kaybolmaz, API gerekmez.
═══════════════════════════════════════════════════════════════════════
"""
import re
import time
from typing import Optional

from utils import db
from utils.log import log


def _ilk_kurulum() -> None:
    """Hafıza tablolarını oluştur (idempotent)."""
    try:
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS urun_hafiza (
                    kimlik     TEXT PRIMARY KEY,   -- link kimliği veya normalize ad
                    urun_adi   TEXT,
                    kategori   TEXT,
                    gorulme    INTEGER DEFAULT 1,
                    ts         INTEGER
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS marka_kategori (
                    marka      TEXT,
                    kategori   TEXT,
                    sayi       INTEGER DEFAULT 1,
                    PRIMARY KEY (marka, kategori)
                )
            """)
    except Exception as e:
        log("UYARI", f"Ürün hafıza kurulum: {e}")


def _marka_cikar(urun_adi: str) -> Optional[str]:
    """Ürün adından marka tahmini — genelde ilk anlamlı kelime."""
    if not urun_adi:
        return None
    kelimeler = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{2,}", urun_adi)
    if not kelimeler:
        return None
    # İlk kelime genelde markadır (Samsung, Apple, Bosch, Defacto...)
    ilk = kelimeler[0]
    # Çok genel ilk kelimeleri marka sayma
    _GENEL = {"yeni", "orijinal", "set", "adet", "li", "lu", "premium"}
    tl = ilk.replace("İ", "i").replace("I", "ı").lower()
    if tl in _GENEL or len(ilk) < 2:
        return None
    return tl


def _link_kimligi(link: Optional[str]) -> Optional[str]:
    """Linkten ürün kimliği çıkar (analiz.urun_kimligi ile uyumlu)."""
    if not link:
        return None
    try:
        from services.analiz import urun_kimligi
        k = urun_kimligi(link)
        return k or None
    except Exception:
        return None


def kaydet(urun_adi: str, link: Optional[str], kategori: Optional[str]) -> None:
    """Bir ürünü/markayı hafızaya yaz. Gözlem sayısını artırır.

    kategori None ise sadece görülme kaydedilir (kategori öğrenilmez)."""
    if not urun_adi or len(urun_adi) < 3:
        return
    # v22.14: Çöp ürün adı (Amazon TR, - İndirimli vb) hafızaya YAZILMAZ
    try:
        from services.analiz import _urun_adi_makul
        if not _urun_adi_makul(urun_adi):
            return
    except Exception:
        pass
    _ilk_kurulum()
    try:
        kimlik = _link_kimligi(link) or urun_adi.strip().lower()[:80]
        simdi = int(time.time())
        with db.cursor() as c:
            # Ürün kaydı (görülme sayısını artır)
            satir = c.execute(
                "SELECT gorulme, kategori FROM urun_hafiza WHERE kimlik=?",
                (kimlik,)
            ).fetchone()
            if satir:
                yeni_kat = kategori or satir["kategori"]
                c.execute(
                    "UPDATE urun_hafiza SET gorulme=gorulme+1, ts=?, "
                    "urun_adi=?, kategori=? WHERE kimlik=?",
                    (simdi, urun_adi[:200], yeni_kat, kimlik)
                )
            else:
                c.execute(
                    "INSERT INTO urun_hafiza (kimlik, urun_adi, kategori, gorulme, ts) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (kimlik, urun_adi[:200], kategori, simdi)
                )
            # Marka→kategori istatistiği (tutarlılık öğrenmesi)
            if kategori:
                marka = _marka_cikar(urun_adi)
                if marka:
                    c.execute(
                        "INSERT INTO marka_kategori (marka, kategori, sayi) VALUES (?, ?, 1) "
                        "ON CONFLICT(marka, kategori) DO UPDATE SET sayi=sayi+1",
                        (marka, kategori)
                    )
    except Exception as e:
        log("UYARI", f"Ürün hafıza kaydet: {e}")


def hatirla(urun_adi: str, link: Optional[str]) -> Optional[str]:
    """Bu ürün/marka daha önce öğrenildi mi? Kategorisini döndür.

    Öncelik: (1) tam ürün eşleşmesi, (2) marka baskın kategorisi.
    Hiçbiri yoksa None → normal tahmine bırak."""
    if not urun_adi:
        return None
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            # 1. Tam ürün eşleşmesi (link kimliği veya ad)
            kimlik = _link_kimligi(link) or urun_adi.strip().lower()[:80]
            satir = c.execute(
                "SELECT kategori, gorulme FROM urun_hafiza WHERE kimlik=? AND kategori IS NOT NULL",
                (kimlik,)
            ).fetchone()
            if satir and satir["kategori"]:
                return satir["kategori"]

            # 2. Marka baskın kategorisi — marka en az 3 kez tutarlı görülmüşse
            marka = _marka_cikar(urun_adi)
            if marka:
                satirlar = c.execute(
                    "SELECT kategori, sayi FROM marka_kategori WHERE marka=? "
                    "ORDER BY sayi DESC",
                    (marka,)
                ).fetchall()
                if satirlar:
                    toplam = sum(s["sayi"] for s in satirlar)
                    en = satirlar[0]
                    # 2a. Tam kategori (ana:alt) baskınsa onu döndür
                    if en["sayi"] >= 3 and en["sayi"] / toplam >= 0.70:
                        return en["kategori"]
                    # 2b. ANA kategori baskınlığı (alt farklı olsa bile).
                    #     "Defacto hep giyim" gibi — alt kategori değişse de
                    #     ana kategori tutarlıysa onu kullan.
                    ana_sayim: dict[str, int] = {}
                    for s in satirlar:
                        ana = s["kategori"].split(":")[0]
                        ana_sayim[ana] = ana_sayim.get(ana, 0) + s["sayi"]
                    en_ana = max(ana_sayim.items(), key=lambda x: x[1])
                    if en_ana[1] >= 3 and en_ana[1] / toplam >= 0.70:
                        return en_ana[0]   # sadece ana kategori (alt belirsiz)
    except Exception as e:
        log("UYARI", f"Ürün hafıza hatırla: {e}")
    return None


def duzelt(urun_adi: str, link: Optional[str], dogru_kategori: str) -> None:
    """Admin düzeltmesi — EN GÜÇLÜ sinyal. Ürünü ve markayı kalıcı düzeltir.

    Marka istatistiğini de güçlü şekilde düzeltir (5 gözlem ekler) ki
    bir sonraki sefere doğru kategori baskın gelsin."""
    if not urun_adi or not dogru_kategori:
        return
    _ilk_kurulum()
    try:
        kimlik = _link_kimligi(link) or urun_adi.strip().lower()[:80]
        simdi = int(time.time())
        with db.cursor() as c:
            c.execute(
                "INSERT INTO urun_hafiza (kimlik, urun_adi, kategori, gorulme, ts) "
                "VALUES (?, ?, ?, 1, ?) "
                "ON CONFLICT(kimlik) DO UPDATE SET kategori=excluded.kategori, ts=excluded.ts",
                (kimlik, urun_adi[:200], dogru_kategori, simdi)
            )
            marka = _marka_cikar(urun_adi)
            if marka:
                # Doğru kategoriye güçlü ağırlık ver (admin sinyali = 5 gözlem)
                c.execute(
                    "INSERT INTO marka_kategori (marka, kategori, sayi) VALUES (?, ?, 5) "
                    "ON CONFLICT(marka, kategori) DO UPDATE SET sayi=sayi+5",
                    (marka, dogru_kategori)
                )
        log("BILGI", f"Hafıza düzeltildi: {urun_adi[:40]} → {dogru_kategori}")
    except Exception as e:
        log("UYARI", f"Ürün hafıza düzelt: {e}")


def istatistik() -> dict:
    """Hafıza durumu (admin /hafiza komutu için)."""
    _ilk_kurulum()
    try:
        with db.cursor() as c:
            urun_say = c.execute("SELECT COUNT(*) n FROM urun_hafiza").fetchone()["n"]
            kategorili = c.execute(
                "SELECT COUNT(*) n FROM urun_hafiza WHERE kategori IS NOT NULL"
            ).fetchone()["n"]
            marka_say = c.execute(
                "SELECT COUNT(DISTINCT marka) n FROM marka_kategori"
            ).fetchone()["n"]
            tekrar = c.execute(
                "SELECT COUNT(*) n FROM urun_hafiza WHERE gorulme >= 2"
            ).fetchone()["n"]
            return {
                "toplam_urun": urun_say,
                "kategorili": kategorili,
                "ogrenilen_marka": marka_say,
                "tekrar_eden": tekrar,
            }
    except Exception:
        return {"toplam_urun": 0, "kategorili": 0, "ogrenilen_marka": 0, "tekrar_eden": 0}


def zehir_temizle() -> dict:
    """v22.14 — Hafızadaki çöp ürün kayıtlarını sil (Amazon TR, - İndirimli vb).
    Döner: {silinen}."""
    _ilk_kurulum()
    silinen = 0
    try:
        from services.analiz import _urun_adi_makul
        with db.cursor() as c:
            satirlar = c.execute("SELECT kimlik, urun_adi FROM urun_hafiza").fetchall()
            for s in satirlar:
                ad = s["urun_adi"] if "urun_adi" in s.keys() else ""
                # urun_adi yoksa kimlikten kontrol
                kontrol = ad or s["kimlik"]
                if kontrol and not _urun_adi_makul(kontrol):
                    c.execute("DELETE FROM urun_hafiza WHERE kimlik=?", (s["kimlik"],))
                    silinen += 1
    except Exception as e:
        log("UYARI", f"Hafıza zehir temizle: {e}")
    return {"silinen": silinen}
