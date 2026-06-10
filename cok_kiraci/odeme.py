"""
cok_kiraci/odeme.py — Ödeme kaydı + abonelik uzatma (Faz 5).

Ödeme BAŞARILI olduğunda odeme_kaydet çağrılır: ödemeyi 'odemeler' tablosuna yazar
ve müşterinin aboneliğini planın gün sayısı kadar uzatır.

Gerçek ödeme sağlayıcı (iyzico / PayTR / Stripe) entegrasyonu ağ + hesap gerektirir
ve canlı ortamda eklenecek. Akış: sağlayıcı tahsilatı yapar → başarı geri-çağrısında
bu modüldeki odeme_kaydet(musteri_id, plan, tutar, referans) çağrılır. Böylece ödeme
mantığı sağlayıcıdan bağımsız ve test edilebilir kalır; sağlayıcı yalnızca bu kancayı
tetikler.
"""
from cok_kiraci import depo, musteri, planlar
from utils import db
from utils.log import simdi_tr


def odeme_kaydet(musteri_id: int, plan_id: str, tutar: float,
                 referans: str = "", durum: str = "basarili"):
    """Ödemeyi kaydet; başarılıysa aboneliği planın süresi kadar uzat.
    Yeni bitiş tarihini döndürür (başarısız/geçersiz planda uzatma yok → None)."""
    depo.kur()
    with db.cursor() as c:
        c.execute(
            "INSERT INTO odemeler (musteri_id, plan, tutar, referans, durum, olusturma) "
            "VALUES (?,?,?,?,?,?)",
            (musteri_id, plan_id, float(tutar or 0), referans, durum, simdi_tr().isoformat()),
        )
    if durum == "basarili" and planlar.gecerli_plan(plan_id):
        return musteri.abonelik_baslat(musteri_id, plan_id)
    return None


def odeme_gecmisi(musteri_id: int, limit: int = 50) -> list:
    depo.kur()
    with db.cursor() as c:
        c.execute("SELECT * FROM odemeler WHERE musteri_id=? ORDER BY id DESC LIMIT ?",
                  (musteri_id, limit))
        return [dict(r) for r in c.fetchall()]


def toplam_gelir() -> float:
    """Başarılı ödemelerin toplamı (operatör panosu için)."""
    depo.kur()
    with db.cursor() as c:
        c.execute("SELECT COALESCE(SUM(tutar),0) AS t FROM odemeler WHERE durum='basarili'")
        return c.fetchone()["t"]
