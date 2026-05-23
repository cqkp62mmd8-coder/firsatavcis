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


class TestReklamYapisalMantik:
    """Reklam ayrımı kalıp listesiyle DEĞİL, yapısal mantıkla.
    Hiç görülmemiş reklam türleri de yakalanmalı (somut ürün+fiyat yoksa reklam)."""

    def test_gorulmemis_reklamlar_yakalanir(self):
        from utils import reklam
        # Bunların hiçbiri kalıp listesinde YOK — yapısal olarak elenmeli
        gorulmemis = [
            "Sürpriz seni bekliyor hemen gel",
            "Join our community for the best deals",
            "Yarınki büyük sürprize hazır mısın",
            "Profilimdeki linke tıklamayı unutma",
            "Bu akşam canlı yayındayız bekleriz",
            "Anketimize katıl görüşünü bildir",
            "100 TL bonus kazanmak için tıkla",
        ]
        for m in gorulmemis:
            rek, _ = reklam.reklam_mi(m)
            assert rek is True, f"Reklam kaçtı: {m}"

    def test_somut_urunler_gecer(self):
        from utils import reklam
        urunler = [
            ("iPhone 15 Pro Max 256GB 89999 TL", ""),
            ("Çorap 89 TL", ""),
            ("Zucchi Marsilya Sabunu 5x180gr 99 TL", ""),
            ("Bosch Buzdolabı 18999 TL", "trendyol.com/x-p-1"),
        ]
        for m, link in urunler:
            rek, _ = reklam.reklam_mi(m, link=link)
            assert rek is False, f"Ürün reklam sanıldı: {m}"

    def test_fiyatli_reklam_yakalanir(self):
        from utils import reklam
        # Fiyat içeren ama ürün SATMAYAN mesajlar (çekiliş/bonus/üyelik)
        assert reklam.reklam_mi("Çekilişe katıl 1000 TL hediye kazan")[0] is True
        assert reklam.reklam_mi("50 puan kazan davet et")[0] is True


class TestCokluMarkaLinkEslestirme:
    """Çoklu ürün mesajında her blok KENDİ linkini almalı.
    Aksi halde link_bul hepsine aynı ilk linki verir → tek paylaşım bug'ı."""

    def test_coklu_blok_ayri_link(self):
        from services.analiz import mesaj_bolum_ayir, urun_kimligine_gore_grupla, link_bul
        btn = ["https://trendyol.com/adidas-p-111", "https://trendyol.com/nike-p-222"]
        ham = ("🔥 Adidas Samba Erkek Ayakkabı %40 indirim 2499 TL\n"
               "🔥 Nike Air Force Beyaz %35 indirim 2999 TL")
        bloklar = mesaj_bolum_ayir(ham)
        urun_linkleri = urun_kimligine_gore_grupla(btn)
        assert len(bloklar) == 2
        assert len(urun_linkleri) == 2
        # Eşleşme aktifken her blok kendi sıralı linkini almalı
        l0 = link_bul(bloklar[0], [urun_linkleri[0]])
        l1 = link_bul(bloklar[1], [urun_linkleri[1]])
        assert l0 != l1, "İki blok aynı linki aldı — çoklu paylaşım bozulur"
        assert "adidas" in l0
        assert "nike" in l1


class TestIsbirligiReklami:
    """İşbirliği/sponsor/duyuru mesajları reklam — somut indirim öznesi yok."""

    def test_isbirligi_reklam(self):
        from utils import reklam
        # "Hepsiburada işbirliği %50" — platform + işbirliği, satılık ürün yok
        rek, _ = reklam.reklam_mi(
            "Hepsiburada işbirliği %50 ye varan indirim Kupon FIRSATI",
            link="hepsiburada.com")
        assert rek is True

    def test_gercek_marka_kampanyasi_gecer(self):
        from utils import reklam
        # "Adidas ürünlerinde %50" — indirimin öznesi var (marka)
        rek, _ = reklam.reklam_mi("Adidas ürünlerinde %50 indirim", link="trendyol.com")
        assert rek is False

    def test_kupon_kodu_urun_degil(self):
        from utils import urun_taniyici
        urun_taniyici.ilk_kurulum()
        # Tamamı büyük tek kelime = kupon kodu, ürün adı değil
        assert urun_taniyici.urun_adi_cikar("Kupon FIRSATI %50") in (None, "")


class TestGemini:
    """Gemini anlama katmanı — anahtar yoksa sessizce yedeğe düşer."""

    def test_anahtar_yoksa_devre_disi(self):
        from utils import gemini
        # Test ortamında anahtar yok → kullanılamaz, None döner
        if not gemini.aktif:
            assert gemini.kullanilabilir() is False
            assert gemini.analiz_et("iPhone 15 Pro 89999 TL") is None

    def test_istatistik_yapisi(self):
        from utils import gemini
        ist = gemini.istatistik()
        assert "aktif" in ist
        assert "model" in ist
        assert "istek" in ist


class TestSablonGemini:
    """Şablon Gemini sonucuyla zenginleşir — akıllı ürün adı + tanıtım."""

    def test_gemini_tanitim_cumlesi_eklenir(self):
        from services.sablon import olustur
        g = {"reklam": False, "urun_adi": "Bosch Buzdolabı No-Frost",
             "kategori": "elektronik", "alt_kategori": "beyaz_esya",
             "kalite": 4, "tanitim": "Geniş hacmi ve sessiz çalışmasıyla mutfağınızın yıldızı."}
        s = olustur("Bosch Buzdolabı 18999 TL", 0,
                    ["https://trendyol.com/x-p-1"], gemini=g)
        assert s is not None
        assert "Bosch Buzdolabı No-Frost" in s
        assert "mutfağınızın yıldızı" in s

    def test_gemini_temiz_urun_adi(self):
        from services.sablon import olustur
        # Gemini temiz ad verir — "yerine" gibi takılar olmaz
        g = {"reklam": False, "urun_adi": "iPhone 15 Pro", "kategori": "elektronik",
             "alt_kategori": "telefon", "kalite": 5, "tanitim": ""}
        s = olustur("iPhone 15 Pro 89999 TL yerine 79999 TL", 11,
                    ["https://trendyol.com/x-p-2"], gemini=g)
        assert "iPhone 15 Pro" in s
        assert "yerine" not in s


class TestOylamaSistemi:
    """Canlı oylama — çift oy engelleme + oy sayma."""

    def test_cift_oy_engellenir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/oy_test"
        os.makedirs("/tmp/oy_test", exist_ok=True)
        from utils import segment
        assert segment.tikla_kaydet(901, 7001, "good") is True
        assert segment.tikla_kaydet(901, 7001, "good") is False  # aynı oy

    def test_oy_degistirme(self):
        from utils import segment
        segment.tikla_kaydet(902, 7002, "good")
        assert segment.tikla_kaydet(902, 7002, "fake") is True   # değişti
        iyi, sahte = segment.oy_sayilari(7002)
        assert iyi == 0 and sahte == 1

    def test_oy_sayma(self):
        from utils import segment
        segment.tikla_kaydet(903, 7003, "good")
        segment.tikla_kaydet(904, 7003, "good")
        segment.tikla_kaydet(905, 7003, "fake")
        iyi, sahte = segment.oy_sayilari(7003)
        assert iyi == 2 and sahte == 1


class TestSablonGeminiZengin:
    """Gemini ile zenginleştirilmiş şablon — kalite rozeti + fiyat uyarısı."""

    def test_kalite_5_elit_rozet(self):
        from services.sablon import olustur
        g = {"reklam": False, "urun_adi": "Dyson V15", "kategori": "elektronik",
             "alt_kategori": "supurge", "kalite": 5, "tanitim": "", "fiyat_uyari": ""}
        s = olustur("Dyson V15 18999 TL", 24, ["https://trendyol.com/x-p-1"], gemini=g)
        assert "ELİT" in s   # kalite 5 → elit rozet

    def test_gemini_fiyat_uyarisi(self):
        from services.sablon import olustur
        g = {"reklam": False, "urun_adi": "Powerbank", "kategori": "elektronik",
             "alt_kategori": "aksesuar", "kalite": 2, "tanitim": "",
             "fiyat_uyari": "Kapasite şüpheli."}
        s = olustur("Powerbank 299 TL", 50, ["https://trendyol.com/x-p-2"], gemini=g)
        assert "Kapasite şüpheli" in s


class TestEnCokOylanan:
    """Haftalık en çok oylanan fırsatlar."""

    def test_en_cok_oylanan_siralama(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/eco_test"
        os.makedirs("/tmp/eco_test", exist_ok=True)
        from utils import segment
        for u in range(5):
            segment.tikla_kaydet(10000 + u, 9001, "good")
        for u in range(2):
            segment.tikla_kaydet(20000 + u, 9002, "good")
        en_cok = segment.en_cok_oylanan(7, 5)
        # 9001 (5 oy) 9002'den (2 oy) önce gelmeli
        idx1 = next(i for i, m in enumerate(en_cok) if m["mesaj_id"] == 9001)
        idx2 = next(i for i, m in enumerate(en_cok) if m["mesaj_id"] == 9002)
        assert idx1 < idx2


class TestGeminiKotaYonetimi:
    """Kota dolunca (429) uzun dinlenme — gereksiz istek israfını önler."""

    def test_kisa_metin_anahtar_yoksa_none(self):
        from utils import gemini
        if not gemini.aktif:
            assert gemini.kisa_metin("Başlık yaz") is None

    def test_istatistik_kota_alani(self):
        from utils import gemini
        ist = gemini.istatistik()
        assert "kota_doldu" in ist
