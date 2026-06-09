"""schedulers/kaynak_tarama.py — Kaynakları periyodik tarayıp paylaşıma besler (v23.37).

Etkin kaynaklardan (feed, mağaza izleme) fırsatları toplar; mevcut paylaşım
hattını (olustur + dedup + kuyruk) yeniden kullanarak kanala gönderir. Böylece
kategori/kalite/biçim/gönderim mantığı aynı kalır. KAYNAK_TARAMA_AKTIF=1 değilse
hiç çalışmaz (varsayılan kapalı).
"""
from __future__ import annotations
import asyncio

from utils.log import log


def _metin_kur(f: dict) -> str:
    """Fırsattan, hattın beklediği biçimde metin üret (ad + fiyat[/eski])."""
    ad = f["ad"]
    fiyat = float(f["fiyat"])
    eski = f.get("eski_fiyat")
    try:
        eski = float(eski) if eski else None
    except (TypeError, ValueError):
        eski = None
    if eski and eski > fiyat:
        return f"{ad}\n{fiyat:.2f} TL  ~~{eski:.2f} TL~~"
    return f"{ad}\n{fiyat:.2f} TL"


def _firsat_isle(f: dict, kuyruk: asyncio.Queue) -> bool:
    """Tek fırsatı filtrele, biçimle ve kuyruğa ekle. Eklendiyse True."""
    import config
    from kaynaklar.temel import indirim_hesapla, firsat_gecerli_mi
    from handlers.mesaj import _kitap_linki_mi, _urun_olmayan_link_mi

    if not firsat_gecerli_mi(f):
        return False
    url = f["url"].strip()

    # Ürün-olmayan link (WhatsApp/sosyal) ve kitap filtreleri (hattaki ile aynı)
    if _urun_olmayan_link_mi(url):
        return False
    if getattr(config, "KITAP_FILTRELE", True) and _kitap_linki_mi(url, [url]):
        return False

    # Feed'ler katalog olduğu için yalnızca GERÇEK indirimleri paylaş
    ind = indirim_hesapla(f.get("eski_fiyat"), f.get("fiyat"))
    if ind < getattr(config, "MIN_INDIRIM", 0):
        return False

    # Tekrar kontrolü (kayıt, paylaşımdan sonra tüketicide yapılır)
    try:
        from utils import duplicate
        if duplicate.daha_once_paylasildi_mi([url]):
            return False
    except Exception:
        pass

    # Mevcut şablon/kalite mantığını yeniden kullan
    from services.sablon import olustur
    metin = _metin_kur(f)
    try:
        sablon = olustur(metin, ind, [url], gemini=None)
    except Exception as e:
        log("UYARI", f"Kaynak: şablon hatası: {e}")
        return False
    if not sablon:
        return False

    from services.analiz import magaza_bul, kategori_bul
    magaza = f.get("magaza") or magaza_bul(metin, url)
    try:
        kat = kategori_bul(metin)[0]
    except Exception:
        kat = "genel"
    kanal_adi = f.get("kaynak", "feed")

    try:
        kuyruk.put_nowait((sablon, None, [url], magaza, kat, kanal_adi, ind, float(ind)))
        return True
    except asyncio.QueueFull:
        log("UYARI", "Kaynak: kuyruk dolu, fırsat atlandı")
        return False


async def _tek_tur(kuyruk: asyncio.Queue) -> None:
    """Tüm etkin kaynakları bir kez tara."""
    from kaynaklar import etkin_kaynaklar
    kaynaklar = etkin_kaynaklar()
    if not kaynaklar:
        log("BILGI", "Kaynak taraması: etkin kaynak yok (FEED_URL/MAGAZA_IZLEME_URL boş)")
        return

    loop = asyncio.get_event_loop()
    toplam_eklenen = 0
    for k in kaynaklar:
        try:
            # firsatlar() ağ yapabilir → bloklamamak için executor'da çalıştır
            firsatlar = await loop.run_in_executor(None, k.firsatlar)
        except Exception as e:
            log("UYARI", f"Kaynak '{k.ad}' hata: {e}")
            continue
        eklenen = 0
        for f in (firsatlar or []):
            if _firsat_isle(f, kuyruk):
                eklenen += 1
        toplam_eklenen += eklenen
        log("BILGI", f"Kaynak '{k.ad}': {len(firsatlar or [])} fırsat tarandı, "
                      f"{eklenen} kuyruğa eklendi")
    if toplam_eklenen:
        log("OK", f"Kaynak taraması: toplam {toplam_eklenen} fırsat paylaşıma alındı")


async def baslat(kuyruk: asyncio.Queue) -> None:
    """KAYNAK_TARAMA_DK dakikada bir kaynakları tarar."""
    import config
    if not getattr(config, "KAYNAK_TARAMA_AKTIF", False):
        return
    aralik = max(5, getattr(config, "KAYNAK_TARAMA_DK", 30)) * 60
    log("SISTEM", f"🔎 Kaynak taraması aktif (her {aralik // 60} dk)")
    await asyncio.sleep(20)  # başlangıçta diğer servislerin oturmasını bekle
    while True:
        try:
            await _tek_tur(kuyruk)
        except Exception as e:
            log("UYARI", f"Kaynak tarama turu hata: {e}")
        await asyncio.sleep(aralik)
