"""services/sablon.py birim testleri."""


class TestOlustur:
    def test_temel(self):
        from services.sablon import olustur
        m = "Test Ürün 200 TL yerine 100 TL"
        sonuc = olustur(m, 50, ["https://amzn.to/x"])
        assert sonuc is not None
        assert "%50" in sonuc

    def test_sifir_indirim_none(self):
        from services.sablon import olustur
        assert olustur("metin", 0, []) is None

    def test_negatif_ifade_filtreler(self):
        from services.sablon import olustur
        # "iptal edildi", "yanlış paylaşım" gibi
        assert olustur("Yanlış paylaşım, fiyat hatası", 50, []) is None

    def test_tasarruf_etiketi_buyuk(self):
        from services.sablon import olustur
        # Tasarruf TL'si artık başlıkta yok — sadece %
        m = "Ürün 200 TL yerine 100 TL"
        sonuc = olustur(m, 50, ["https://amzn.to/x"])
        assert sonuc is not None
        assert "%50" in sonuc

    def test_tasarruf_etiketi_kucuk_gizli(self):
        from services.sablon import olustur
        # Bu test artık trivial — başlıkta hiçbir tasarruf etiketi yok
        m = "Kalem 60 TL yerine 30 TL"
        sonuc = olustur(m, 50, ["https://hb.biz/x"])
        assert "tasarruf" not in sonuc.lower()

    def test_vip_rozet(self):
        from services.sablon import olustur
        # %72 indirim → ELİT FIRSAT olmalı
        m = "Apple AirPods 8000 TL yerine 2000 TL"
        sonuc = olustur(m, 75, ["https://amzn.to/x"])
        assert "ELİT" in sonuc or "💎" in sonuc

    def test_kucuk_indirim_normal(self):
        from services.sablon import olustur
        # %25 indirim → ELİT değil
        m = "Ürün 100 TL yerine 75 TL"
        sonuc = olustur(m, 25, ["https://amzn.to/x"])
        assert "ELİT" not in sonuc


class TestFiyatFormat:
    def test_kusurat_silme(self):
        from services.sablon import _fiyat_format
        assert _fiyat_format("1.499,00") == "1.499"
        assert _fiyat_format("100,00") == "100"

    def test_anlamli_kusurat_korunur(self):
        from services.sablon import _fiyat_format
        assert _fiyat_format("299,90") == "299,90"
        assert _fiyat_format("1.234,56") == "1.234,56"


class TestTasarruf:
    def test_hesaplama(self):
        from services.sablon import _tasarruf_hesapla
        assert _tasarruf_hesapla(200, 100) == 100
        assert _tasarruf_hesapla(0, 50) == 0
        assert _tasarruf_hesapla(100, 200) == 0   # yeni > eski mantıksız

    def test_format(self):
        from services.sablon import _tasarruf_format
        assert _tasarruf_format(2050) == "2.050"
        assert _tasarruf_format(1234567) == "1.234.567"
