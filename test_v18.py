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


class TestReklamTespiti:
    """İndirim olmayan gerçek ürünler geçer, reklamlar atılır."""

    def test_gercek_urun_reklam_degil(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "iPhone 15 Pro Max 256GB 89.999 TL",
            "https://trendyol.com/x-p-1", "iPhone 15 Pro Max", True)
        assert rek is False

    def test_kanal_daveti_reklam(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "Kanalımıza katıl en iyi fırsatlar burada abone ol", "", "", False)
        assert rek is True

    def test_cekilis_reklam(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "Çekilişe katıl iPhone kazan detaylar için takip et", "", "", False)
        assert rek is True

    def test_marka_kampanyasi_gecer(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "Adidas tüm ürünlerde %50 indirim",
            "https://trendyol.com/adidas", "", False)
        assert rek is False

    def test_urun_sinyali_yok_reklam(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "Merhaba arkadaşlar bugün güzel fırsatlar var", "", "", False)
        assert rek is True


class TestUrunKimligi:
    """Aynı ürünün farklı linkleri tek kimlik; farklı ürünler ayrı."""

    def test_ayni_urun_farkli_tag(self):
        from services.analiz import urun_kimligi
        k1 = urun_kimligi("https://www.amazon.com.tr/dp/B0CQJSJQ1T?tag=aff1")
        k2 = urun_kimligi("https://www.amazon.com.tr/dp/B0CQJSJQ1T?ref=xyz")
        assert k1 == k2

    def test_farkli_urunler_farkli_kimlik(self):
        from services.analiz import urun_kimligi
        k1 = urun_kimligi("https://www.trendyol.com/x-p-111")
        k2 = urun_kimligi("https://www.trendyol.com/y-p-222")
        assert k1 != k2

    def test_gruplama_ayni_urun_tek(self):
        from services.analiz import urun_kimligine_gore_grupla
        sonuc = urun_kimligine_gore_grupla([
            "https://www.amazon.com.tr/dp/B0CQJSJQ1T?tag=aff1",
            "https://www.amazon.com.tr/dp/B0CQJSJQ1T?ref=xyz",
        ])
        assert len(sonuc) == 1

    def test_gruplama_iki_urun(self):
        from services.analiz import urun_kimligine_gore_grupla
        sonuc = urun_kimligine_gore_grupla([
            "https://www.trendyol.com/x-p-111",
            "https://www.trendyol.com/y-p-222",
        ])
        assert len(sonuc) == 2


class TestUrunAdiTemizleme:
    """Kargo/üyelik takıları ürün adından çıkmalı."""

    def test_ucretsiz_kargo_temizlenir(self):
        from services.analiz import urun_adi_bul
        ad = urun_adi_bul("iPhone 15 Pro Max 256GB 89.999 TL ücretsiz kargo")
        assert ad is not None
        assert "kargo" not in ad.lower()

    def test_premium_uyelik_temizlenir(self):
        from services.analiz import urun_adi_bul
        ad = urun_adi_bul("Bosch Süpürge 4.999 TL premium üyelik")
        assert ad is not None
        assert "üyelik" not in ad.lower()


class TestFiyatZekasi:
    """Kategori bazlı fiyat değerlendirmesi."""

    def test_ucuz_fiyat_yuksek_bonus(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/fz_pytest"
        os.makedirs("/tmp/fz_pytest", exist_ok=True)
        from utils import fiyat_zekasi
        # Tutarlı fiyatlar öğret
        for _ in range(20):
            fiyat_zekasi.kaydet("test:kat", 50000)
        # Çok ucuz fiyat
        d = fiyat_zekasi.firsat_degeri("test:kat", 30000)
        assert d is not None
        assert d["bonus"] >= 10   # ucuz → yüksek bonus

    def test_yetersiz_veri_none(self):
        from utils import fiyat_zekasi
        d = fiyat_zekasi.firsat_degeri("hic:yok", 1000)
        assert d is None


class TestUrunTaniyici:
    """Öğrenen ürün adı tanıyıcı (regex listesi değil, ML model)."""

    def test_gercek_urun_taninir(self):
        from utils import urun_taniyici
        assert urun_taniyici.urun_adi_cikar("iPhone 15 Pro Max 256GB 89999 TL") is not None
        assert urun_taniyici.urun_adi_cikar("Çorap 89 TL") is not None

    def test_bilinmeyen_marka_taninir(self):
        from utils import urun_taniyici
        # Hiçbir listede olmayan markalar yapısal olarak tanınmalı
        assert urun_taniyici.urun_adi_cikar("Zucchi Marsilya Sabunu 5x180gr 99 TL") is not None
        assert urun_taniyici.urun_adi_cikar("Vinature Doğal Sıvı Sabun 1.5L 49 TL") is not None

    def test_slogan_elenir(self):
        from utils import urun_taniyici
        assert urun_taniyici.urun_adi_cikar("Stoklar ERİYOR hemen yakala 999 TL") is None
        assert urun_taniyici.urun_adi_cikar("Süper fiyat şok indirim 500 TL") is None
        assert urun_taniyici.urun_adi_cikar("Kanalımıza katıl abone ol takip et") is None

    def test_kelime_skoru_dogru_yon(self):
        from utils import urun_taniyici
        # "iPhone" ürün, "hemen" filler — skorlar doğru yönde olmalı
        urun_skor = urun_taniyici.kelime_urun_mu("Süpürge")
        filler_skor = urun_taniyici.kelime_urun_mu("hemen")
        assert urun_skor > filler_skor
