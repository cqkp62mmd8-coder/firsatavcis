"""
═══════════════════════════════════════════════════════════════════════
KALİTE KARNE (v22.7 — Sistem 3)

Her paylaşıma 0-100 kalite puanı verir. Düşük puanlılar elenebilir.
Puan bileşenleri:
  • Ürün adı netliği (0-35): uzunluk, kelime sayısı, çöp değil
  • Kategori güveni (0-25): ML ne kadar emin
  • Fiyat geçerliliği (0-20): gerçek fiyat var mı, indirim mantıklı mı
  • Görsel varlığı (0-10): görsel ekli mi
  • Link kalitesi (0-10): geçerli ürün linki mi

Eşiğin altı → paylaşma. /karne ile istatistik.
═══════════════════════════════════════════════════════════════════════
"""
import re
import time
from utils.log import log

# v23.6 — Kalite geçmişi artık DB'de (eskiden bellekteydi, bot restart'ta
# sıfırlanıyordu → panel "Ort. Kalite: 0" gösteriyordu). DB'de kalıcı.
_KARNE_MAX = 200


def _karne_kaydet_db(puan: int) -> None:
    """Bir kalite puanını DB'ye ekle (son 200 tutulur)."""
    try:
        from utils import db
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kalite_gecmis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    puan INTEGER NOT NULL,
                    ts INTEGER NOT NULL
                )
            """)
            c.execute("INSERT INTO kalite_gecmis (puan, ts) VALUES (?, ?)",
                      (int(puan), int(time.time())))
            # Son 200'ü tut
            c.execute("""
                DELETE FROM kalite_gecmis WHERE id NOT IN (
                    SELECT id FROM kalite_gecmis ORDER BY ts DESC LIMIT ?
                )
            """, (_KARNE_MAX,))
    except Exception as e:
        log("UYARI", f"Kalite kaydet: {e}")


def _karne_oku_db() -> list:
    """DB'deki kalite puanlarını oku."""
    try:
        from utils import db
        with db.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kalite_gecmis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    puan INTEGER NOT NULL,
                    ts INTEGER NOT NULL
                )
            """)
            satirlar = c.execute("SELECT puan FROM kalite_gecmis ORDER BY ts DESC LIMIT ?",
                                 (_KARNE_MAX,)).fetchall()
            return [r["puan"] for r in satirlar]
    except Exception:
        return []


def puan_hesapla(urun_adi: str | None, kategori: str, guven: float,
                 indirim: int, eski_fiyat: float, yeni_fiyat: float,
                 gorsel_var: bool, link: str | None) -> dict:
    """Bir paylaşımın kalite puanını hesapla. Döner: {puan, detay, gecer}."""
    detay = {}

    # 1. Ürün adı netliği (0-35)
    ad_puan = 0
    if urun_adi:
        kelime = len(urun_adi.split())
        uzunluk = len(urun_adi)
        if kelime >= 2:        ad_puan += 15
        elif kelime == 1:      ad_puan += 7
        if uzunluk >= 15:      ad_puan += 12
        elif uzunluk >= 8:     ad_puan += 7
        # Marka/model işareti (büyük harf + rakam) → kaliteli
        if re.search(r"[A-Z]", urun_adi) and re.search(r"\d", urun_adi):
            ad_puan += 8
        ad_puan = min(ad_puan, 35)
    detay["urun_adi"] = ad_puan

    # 2. Kategori güveni (0-25)
    kat_puan = 0
    if kategori and kategori != "genel":
        kat_puan = int(min(guven, 1.0) * 25)
    else:
        kat_puan = 5   # genel kategori de olur ama düşük puan
    detay["kategori"] = kat_puan

    # 3. Fiyat geçerliliği (0-20)
    fiyat_puan = 0
    if yeni_fiyat and yeni_fiyat > 0:
        fiyat_puan += 10
        if eski_fiyat and eski_fiyat > yeni_fiyat:
            fiyat_puan += 5   # gerçek indirim
        if 5 <= indirim <= 90:
            fiyat_puan += 5   # mantıklı indirim aralığı
    detay["fiyat"] = fiyat_puan

    # 4. Görsel (0-10)
    detay["gorsel"] = 10 if gorsel_var else 0

    # 5. Link (0-10)
    link_puan = 0
    if link and re.match(r"https?://", link):
        link_puan = 10
    detay["link"] = link_puan

    toplam = sum(detay.values())
    return {"puan": toplam, "detay": detay}


def degerlendir(urun_adi, kategori, guven, indirim, eski_f, yeni_f,
                gorsel_var, link, esik: int = 35) -> bool:
    """Paylaşım kalite eşiğini geçiyor mu? Geçmişe de kaydet."""
    sonuc = puan_hesapla(urun_adi, kategori, guven, indirim,
                         eski_f, yeni_f, gorsel_var, link)
    puan = sonuc["puan"]
    # v23.6 — Geçmişe DB'ye ekle (kalıcı, restart'ta kaybolmaz)
    _karne_kaydet_db(puan)
    gecer = puan >= esik
    if not gecer:
        log("BILGI", f"Kalite eşiği altı ({puan}/{esik}): "
                     f"'{(urun_adi or '?')[:30]}' detay={sonuc['detay']}")
    return gecer


def istatistik() -> dict:
    """Karne istatistikleri (/karne için). v23.6: DB'den okur (kalıcı)."""
    karne = _karne_oku_db()
    if not karne:
        return {"toplam": 0, "ortalama": 0, "dusuk": 0, "yuksek": 0}
    return {
        "toplam":   len(karne),
        "ortalama": round(sum(karne) / len(karne), 1),
        "dusuk":    sum(1 for p in karne if p < 50),
        "yuksek":   sum(1 for p in karne if p >= 75),
        "en_dusuk": min(karne),
        "en_yuksek": max(karne),
    }
