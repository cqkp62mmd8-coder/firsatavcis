"""v18 yeni modül testleri — dil, anomali, sahte indirim, marka, trend."""
import os
os.environ.setdefault("DATA_DIR", "/tmp/v18_pytest")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)


class TestDilTanima:
    def test_turkce_yuksek_skor(self):
        from utils import dil
        skor = dil.turkce_skoru("iPhone 15 Pro Max titanyum fiyatı çok iyi indirimli")
        assert skor >= 0.45

    def test_ingilizce_dusuk_skor(self):
        from utils import dil
        skor = dil.turkce_skoru("The new product is now available with the best discount for you")
        assert skor < 0.45

    def test_fransizca_dusuk_skor(self):
        from utils import dil
        skor = dil.turkce_skoru("Nouvelle collection de parfums pour femme avec une grande réduction")
        assert skor < 0.45


class TestAnomali:
    def test_normal_mesaj_gecer(self):
        from utils import anomali
        anom, _ = anomali.kontrol_et(
            "iPhone 15 Pro Max 256GB titanyum gri renk uzun açıklama metni burada",
            fiyat=89999, indirim=30, link_sayi=1)
        assert anom is False

    def test_asiri_indirim_yakalanir(self):
        from utils import anomali
        anom, sebep = anomali.kontrol_et("Süper fırsat", fiyat=50, indirim=97, link_sayi=1)
        assert anom is True

    def test_dusuk_fiyat_yakalanir(self):
        from utils import anomali
        anom, _ = anomali.kontrol_et("Ürün açıklaması burada", fiyat=3, indirim=40, link_sayi=1)
        assert anom is True

    def test_emoji_bombasi_yakalanir(self):
        from utils import anomali
        anom, _ = anomali.kontrol_et("🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥 AL", link_sayi=1)
        assert anom is True


class TestSahteIndirim:
    def test_normal_indirim_gecer(self):
        from utils import sahte_indirim
        sahte, _ = sahte_indirim.sahte_mi(1000, 700, 30, "Trendyol")
        assert sahte is False

    def test_yuzde_95_sahte(self):
        from utils import sahte_indirim
        sahte, _ = sahte_indirim.sahte_mi(1000, 50, 95, "Trendyol")
        assert sahte is True

    def test_absurd_oran_sahte(self):
        from utils import sahte_indirim
        sahte, _ = sahte_indirim.sahte_mi(5000, 80, 98, "Hepsiburada")
        assert sahte is True


class TestMarkaOgrenme:
    def test_tekrarli_marka_ogrenilir(self):
        from utils import marka_ogrenme
        marka_ogrenme.temizle_hepsi()
        for _ in range(3):
            marka_ogrenme.kaydet("TestMarka Pro ürün modeli", "elektronik")
        assert marka_ogrenme.marka_mi("TestMarka") == "elektronik"

    def test_tek_gorulen_marka_degil(self):
        from utils import marka_ogrenme
        marka_ogrenme.temizle_hepsi()
        marka_ogrenme.kaydet("TekSeferMarka ürün", "giyim")
        # 1 kez görülen marka olmamalı (eşik 3)
        assert marka_ogrenme.marka_mi("TekSeferMarka") is None
