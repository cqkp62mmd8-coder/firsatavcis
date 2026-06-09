"""kaynaklar paketi — config'ten etkin fırsat kaynaklarını oluşturur."""
from __future__ import annotations

from kaynaklar.temel import Kaynak, firsat_gecerli_mi, indirim_hesapla  # noqa: F401


def etkin_kaynaklar() -> list[Kaynak]:
    """Yapılandırmaya göre etkin kaynak nesnelerini döndür."""
    import config
    kaynaklar: list[Kaynak] = []

    # 1) Feed kaynağı
    if getattr(config, "FEED_URL", ""):
        from kaynaklar.feed import FeedKaynak
        eslem = {
            "ad": config.FEED_AD_ALAN,
            "fiyat": config.FEED_FIYAT_ALAN,
            "eski_fiyat": config.FEED_ESKIFIYAT_ALAN,
            "url": config.FEED_URL_ALAN,
            "gorsel": config.FEED_GORSEL_ALAN,
            "kategori": config.FEED_KATEGORI_ALAN or None,
            "magaza_sabit": config.FEED_MAGAZA_SABIT or None,
            "kayit_yolu": config.FEED_KAYIT_YOLU or None,
        }
        k = FeedKaynak(config.FEED_URL, config.FEED_BICIM, eslem, ad="feed")
        if k.etkin_mi():
            kaynaklar.append(k)

    # 2) Mağaza izleme kaynağı
    if getattr(config, "MAGAZA_IZLEME_URL", []):
        from kaynaklar.magaza import MagazaIzlemeKaynak
        k = MagazaIzlemeKaynak(config.MAGAZA_IZLEME_URL,
                               min_indirim=getattr(config, "MIN_INDIRIM", 0))
        if k.etkin_mi():
            kaynaklar.append(k)

    return kaynaklar
