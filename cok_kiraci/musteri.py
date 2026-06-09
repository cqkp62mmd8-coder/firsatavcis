"""
cok_kiraci/musteri.py — SaaS müşteri / abonelik / ayar iş mantığı.

Lisans anahtarı üretimi, panel girişi (doğrulama), abonelik süresi yönetimi,
ayar ve affiliate işlemleri. Depolama cok_kiraci/depo.py üzerinden yapılır;
bu modül DB ayrıntısından bağımsızdır (PostgreSQL'e geçişte değişmez).
"""
import json
import secrets
from datetime import datetime, timedelta

from cok_kiraci import depo
from utils.log import simdi_tr

# Karışabilen karakterler (0/O, 1/I/L) çıkarıldı → telefondan okunması kolay
_ALFABE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def lisans_key_uret() -> str:
    """FP-XXXX-XXXX-XXXX biçiminde güvenli rastgele lisans anahtarı."""
    bloklar = ["".join(secrets.choice(_ALFABE) for _ in range(4)) for _ in range(3)]
    return "FP-" + "-".join(bloklar)


def musteri_olustur(ad: str = "", plan: str = "aylik", gun: int = 30) -> dict:
    """Yeni müşteri + benzersiz lisans anahtarı oluştur, müşteri bilgisini döndür."""
    key = lisans_key_uret()
    for _ in range(10):
        if not depo.lisans_getir(key):
            break
        key = lisans_key_uret()
    simdi = simdi_tr()
    bitis = (simdi + timedelta(days=gun)).isoformat()
    mid = depo.musteri_ekle(key, ad, plan, simdi.isoformat(), bitis)
    return {"id": mid, "lisans_key": key, "ad": ad, "plan": plan, "bitis": bitis}


def _suresi_doldu(m: dict) -> bool:
    bitis = m.get("bitis")
    if not bitis:
        return False
    try:
        return simdi_tr() > datetime.fromisoformat(bitis)
    except Exception:
        return False


def giris(lisans_key: str):
    """Panel girişi: geçerli + aktif + süresi dolmamış müşteriyi döndürür; yoksa None."""
    if not lisans_key:
        return None
    m = depo.lisans_getir(lisans_key.strip())
    if not m:
        return None
    if m.get("durum") != "aktif":
        return None
    if _suresi_doldu(m):
        return None
    return m


def aktif_mi(musteri_id: int) -> bool:
    """Müşterinin aboneliği geçerli mi (gönderim katmanı bunu kontrol eder)."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return False
    return m.get("durum") == "aktif" and not _suresi_doldu(m)


def abonelik_uzat(musteri_id: int, gun: int) -> str:
    """Aboneliği uzat: bitiş geçmişse bugünden, gelecekteyse mevcut bitişten ekler."""
    m = depo.musteri_getir(musteri_id)
    simdi = simdi_tr()
    taban = simdi
    if m and m.get("bitis"):
        try:
            mevcut = datetime.fromisoformat(m["bitis"])
            if mevcut > simdi:
                taban = mevcut
        except Exception:
            pass
    yeni = (taban + timedelta(days=gun)).isoformat()
    depo.musteri_guncelle(musteri_id, bitis=yeni, durum="aktif")
    return yeni


def askiya_al(musteri_id: int) -> None:
    """Aboneliği pasifle (ödeme durunca/iptalde)."""
    depo.musteri_guncelle(musteri_id, durum="pasif")


# ── ayar (panelden düzenlenir) ────────────────────────────────────
def ayar_getir(musteri_id: int) -> dict:
    """Müşteri ayarlarını normalize edilmiş biçimde döndür."""
    a = depo.ayar_getir(musteri_id) or {}
    kategoriler = []
    if a.get("kategoriler"):
        try:
            kategoriler = json.loads(a["kategoriler"])
        except Exception:
            kategoriler = []
    return {
        "kanal": a.get("kanal", ""),
        "min_indirim": a.get("min_indirim", 20),
        "kategoriler": kategoriler,          # boş liste = tüm kategoriler
        "sablon": a.get("sablon", "klasik"),
        "aktif": bool(a.get("aktif", 1)),
    }


def ayar_kaydet(musteri_id: int, kanal=None, min_indirim=None,
                kategoriler=None, sablon=None, aktif=None) -> None:
    """Verilen ayar alanlarını güncelle (None olanlara dokunulmaz)."""
    g = {}
    if kanal is not None:
        g["kanal"] = kanal.strip()
    if min_indirim is not None:
        g["min_indirim"] = max(0, min(99, int(min_indirim)))
    if kategoriler is not None:
        g["kategoriler"] = json.dumps(list(kategoriler), ensure_ascii=False)
    if sablon is not None:
        g["sablon"] = sablon
    if aktif is not None:
        g["aktif"] = 1 if aktif else 0
    depo.ayar_guncelle(musteri_id, **g)


# ── affiliate ─────────────────────────────────────────────────────
def affiliate_kaydet(musteri_id: int, platform: str, etiket: str) -> None:
    """Müşterinin bir platform için affiliate etiketini kaydet."""
    depo.affiliate_kaydet(musteri_id, platform, (etiket or "").strip())


def affiliate_getir(musteri_id: int) -> dict:
    """{platform: etiket} sözlüğü döndür."""
    return depo.affiliate_listele(musteri_id)
