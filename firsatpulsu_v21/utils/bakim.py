"""
═══════════════════════════════════════════════════════════════════════
DB BAKIM — Otomatik veritabanı temizliği (v22)

SQLite zamanla şişer: eski oylar, görülmüş kayıtlar, metrikler, ürün
hafızası birikir. Railway diskini doldurmasın diye periyodik temizlik.

Temizlenen:
  • kullanici_tikla  → OY_SAKLAMA_GUN'den eski oylar
  • mesaj_meta       → OY_SAKLAMA_GUN'den eski mesaj metaları
  • urun_hafiza      → HAFIZA_SAKLAMA_GUN'den eski, az görülen ürünler
  • metrik           → 90 günden eski metrikler
  • gorulmus         → zaten TTL'li ama VACUUM ile sıkıştırılır

VACUUM ile dosya fiziksel olarak küçültülür.
═══════════════════════════════════════════════════════════════════════
"""
import time

import config
from utils import db
from utils.log import log


def bakim_yap(zorla: bool = False) -> dict:
    """Tüm bakım işlemlerini çalıştır. Silinen kayıt sayılarını döndürür."""
    sonuc: dict[str, int] = {}
    simdi = int(time.time())

    # 1. Eski oylar (kullanici_tikla)
    oy_kesim = simdi - config.OY_SAKLAMA_GUN * 86400
    sonuc["oylar"] = _sil("kullanici_tikla", "ts", oy_kesim)

    # 2. Eski mesaj metaları
    sonuc["mesaj_meta"] = _sil("mesaj_meta", "ts", oy_kesim)

    # 3. Eski + az görülen ürün hafızası (sık görülenleri koru)
    hafiza_kesim = simdi - config.HAFIZA_SAKLAMA_GUN * 86400
    try:
        with db.cursor() as c:
            n = c.execute(
                "DELETE FROM urun_hafiza WHERE ts < ? AND gorulme < 3",
                (hafiza_kesim,)
            ).rowcount
            sonuc["urun_hafiza"] = max(0, n)
    except Exception as e:
        log("UYARI", f"Bakım urun_hafiza: {e}")
        sonuc["urun_hafiza"] = 0

    # 4. Eski metrikler (90 gün) — metrik tablosunda kolon 'olusturma'
    metrik_kesim = simdi - 90 * 86400
    sonuc["metrik"] = _sil("metrik", "olusturma", metrik_kesim)

    # 5. Eski duplicate kayıtları (DUPLICATE_GUN'ün 2 katı yeter)
    pay_kesim = simdi - max(config.DUPLICATE_GUN * 2, 7) * 86400
    sonuc["duplicate"] = _sil("duplicate_kayit", "ts", pay_kesim)

    # 6. VACUUM — dosyayı fiziksel küçült (sadece bir şey silindiyse)
    toplam = sum(sonuc.values())
    if toplam > 0 or zorla:
        try:
            with db.cursor() as c:
                c.execute("VACUUM")
            sonuc["vacuum"] = 1
        except Exception as e:
            log("UYARI", f"Bakım VACUUM: {e}")

    log("OK", f"DB bakımı: {toplam} eski kayıt temizlendi {dict(sonuc)}")
    return sonuc


def _sil(tablo: str, ts_kolon: str, kesim: int) -> int:
    """Bir tablodan kesim zamanından eski kayıtları sil. Tablo yoksa 0."""
    try:
        with db.cursor() as c:
            n = c.execute(
                f"DELETE FROM {tablo} WHERE {ts_kolon} < ?", (kesim,)
            ).rowcount
            return max(0, n)
    except Exception:
        return 0   # tablo yok / kolon yok → sessiz geç


def db_boyut() -> dict:
    """Veritabanı boyut bilgisi (admin /bakim için)."""
    import os
    bilgi: dict = {}
    try:
        yol = getattr(db, "DB_FILE", None)
        if yol and os.path.exists(yol):
            bilgi["dosya_mb"] = round(os.path.getsize(yol) / 1024 / 1024, 2)
    except Exception:
        pass
    # Tablo satır sayıları
    for tablo in ("kullanici_tikla", "urun_hafiza", "gorulmus",
                  "metrik", "duplicate_kayit", "paylasim_kayit", "mesaj_meta"):
        try:
            with db.cursor() as c:
                n = c.execute(f"SELECT COUNT(*) n FROM {tablo}").fetchone()["n"]
                bilgi[tablo] = n
        except Exception:
            pass
    return bilgi
