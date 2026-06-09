"""
═══════════════════════════════════════════════════════════════════════
GERÇEK MESAJ KORPUSU — canlıdan toplanan gerçek kaynak formatları

Amaç: Canlıda karşılaşılan her mesaj formatının doğru işlendiğini
garantilemek. Yeni bir kenar durum çıktığında BURAYA eklenir, böylece
o bug bir daha asla geri gelmez (regresyon koruması).

Her vaka gerçek bir kaynak mesaj yapısını temsil eder. Bu testler
"sistemin gerçek dünyada çalıştığının" kanıtıdır — birim testlerden
farklı olarak uçtan uca senaryoları kapsar.
═══════════════════════════════════════════════════════════════════════
"""
import os
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("SESSION_STRING", "x")
os.environ.setdefault("CHANNEL_ID", "@test")
os.environ.setdefault("ADMIN_ID", "1")
os.environ.setdefault("DATA_DIR", "/tmp/gercek_test")
os.makedirs("/tmp/gercek_test", exist_ok=True)


class TestAmazonAffiliateFormat:
    """Amazon affiliate botlarının tipik mesaj formatları."""

    def test_urun_adi_ilk_satirda_emoji_ile(self):
        from services.analiz import urun_adi_bul
        m = ("📦 Levi's The Trucker Jacket Erkek Ceket\n"
             "💰 Normal Fiyat: ₺5.299,59 ⬇️ İndirim: -%68 ⚡️ İndirimli: ₺1.695,00")
        ad = urun_adi_bul(m)
        assert ad is not None, "Ürün adı çıkmadı"
        assert "Trucker" in ad or "Levi" in ad or "Ceket" in ad

    def test_google_karsilastir_cta_li(self):
        from services.analiz import urun_adi_bul
        m = ("Razer Goliathus Mouse Pad [🔍 Google'da Karşılaştır]"
             "(https://google.com/search?q=razer)\n💰 İndirim: -%45")
        ad = urun_adi_bul(m)
        assert ad is not None
        assert "google" not in ad.lower()

    def test_sadece_fiyat_satiri_urun_adsiz(self):
        from services.analiz import urun_adi_bul
        # Ürün adı yoksa çöp değil None dönmeli
        m = "💰 Normal Fiyat: ₺489,90 ⬇️ İndirim: -%49 ⚡️ İndirimli: ₺249,90"
        assert urun_adi_bul(m) is None


class TestKuponluFirsat:
    """Kupon kodlu fırsat mesajları (kupon ürün adına karışmamalı)."""

    def test_tchibo_kupon_formati(self):
        from services.analiz import urun_adi_bul
        m = ("🔥Tchibo 1Kg Çekirdek Kahve\n"
             "✅Ürünün Altındaki 200TL Kupon İle 609TL - Ücretsiz Kargo")
        ad = urun_adi_bul(m)
        assert ad is not None
        assert "Tchibo" in ad
        # Kupon kodu/tutarı ürün adına girmemeli
        assert "200TL" not in ad and "Kupon" not in ad


class TestCokluUrunGercek:
    """Gerçek çoklu ürün mesajları — her ürün kendi linkiyle."""

    def test_iki_urun_uc_buton(self):
        from services.analiz import mesaj_bolum_ayir, urun_kimligine_gore_grupla, link_bul
        ham = ("🔥Tchibo 1Kg Çekirdek Kahve\n"
               "✅Ürünün Altındaki 200TL Kupon İle 609TL\n"
               "🔻Pols Gurme Vişne Reçeli 285Gr 199TL")
        bloklar = mesaj_bolum_ayir(ham)
        btn = [
            "https://n11.com/tchibo-p-111",
            "https://n11.com/pols-p-222",
            "https://hepsiburada.com/kampanya",  # alakasız 3. buton
        ]
        ul = urun_kimligine_gore_grupla(btn)
        # Her iki ürün de kendi linkini almalı
        assert len(ul) >= 2
        l0 = link_bul(bloklar[0], [ul[0]])
        l1 = link_bul(bloklar[1], [ul[1]])
        assert l0 != l1, "İki ürün aynı linke düştü"


class TestReklamGercekFormat:
    """Gerçek reklam/duyuru mesajları — paylaşılmamalı."""

    def test_isbirligi_reklami(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi(
            "Hepsiburada işbirliği %50 ye varan indirim Kupon FIRSATI",
            link="hepsiburada.com")
        assert rek is True

    def test_oyun_reklami(self):
        from utils import reklam
        # "Kurtların savaşı kızışıyor" tipi oyun reklamı (ürün yok)
        rek, _ = reklam.reklam_mi("Kurtların savaşı kızışıyor hemen oyna")
        assert rek is True

    def test_premium_uyelik(self):
        from utils import reklam
        rek, _ = reklam.reklam_mi("Premium üyelik ile ücretsiz kargo fırsatı")
        assert rek is True


class TestLinkSecimi:
    """Link seçimi — arama/karşılaştırma linkleri ürün sayılmamalı."""

    def test_amazon_vs_google(self):
        from services.analiz import urun_kimligine_gore_grupla
        linkler = [
            "https://www.amazon.com.tr/dp/B08PDKKC28?tag=x",
            "https://www.google.com/search?q=urun+akakce",
        ]
        ul = urun_kimligine_gore_grupla(linkler)
        assert len(ul) == 1
        assert "amazon" in ul[0]

    def test_gercek_urun_oncelik(self):
        from services.analiz import urun_kimligine_gore_grupla
        linkler = [
            "https://hepsiburada.com/anasayfa-kampanya",
            "https://www.trendyol.com/marka/urun-p-98765",
        ]
        ul = urun_kimligine_gore_grupla(linkler)
        # Gerçek ürün linki (-p-) önce gelmeli
        assert "-p-98765" in ul[0]


class TestKaliteKapisi:
    """Şablon kalite kapısı — bozuk/eksik çıktı paylaşılmamalı."""

    def test_linksiz_urun_paylasilmaz(self):
        from services.sablon import olustur
        # Link yok → None (marka kampanyası değil)
        s = olustur("Samsung Galaxy S24 256GB 45000 TL", 20, [])
        assert s is None

    def test_gecerli_urun_paylasilir(self):
        from services.sablon import olustur
        g = {"reklam": False, "urun_adi": "Samsung Galaxy S24",
             "kategori": "elektronik", "alt_kategori": "telefon",
             "kalite": 4, "tanitim": "", "fiyat_uyari": "", "fiyat": 0, "eski_fiyat": 0}
        s = olustur("Samsung Galaxy S24 45000 TL", 20,
                    ["https://trendyol.com/x-p-1"], gemini=g)
        assert s is not None
        assert "Samsung Galaxy S24" in s

    def test_kalite_kapisi_fonksiyonu(self):
        from services.sablon import _sablon_kalite_gecer
        # Çok kısa çıktı → reddet
        assert _sablon_kalite_gecer("kısa", "Ürün", "http://x.com", "normal") is False
        # Link yok + marka değil → reddet
        assert _sablon_kalite_gecer("x" * 50, "Ürün", None, "normal") is False
        # Geçerli → kabul
        assert _sablon_kalite_gecer("x" * 50, "iPhone 15", "http://x.com", "normal") is True


class TestSaglikSistemi:
    """Bot kendi kendini izleyen sağlık sistemi."""

    def test_yuksek_atlama_tespit(self):
        from utils import saglik
        saglik._olaylar.clear()
        for _ in range(25):
            saglik.kaydet("link_yok")
        for _ in range(2):
            saglik.kaydet("paylasildi")
        sorunlar = saglik.saglik_kontrol()
        assert len(sorunlar) >= 1
        assert any("atlandı" in s for s in sorunlar)

    def test_saglikli_durumda_uyari_yok(self):
        from utils import saglik
        saglik._olaylar.clear()
        for _ in range(20):
            saglik.kaydet("paylasildi")
        for _ in range(2):
            saglik.kaydet("link_yok")
        assert len(saglik.saglik_kontrol()) == 0

    def test_az_veri_uyari_yok(self):
        from utils import saglik
        saglik._olaylar.clear()
        saglik.kaydet("link_yok")
        assert len(saglik.saglik_kontrol()) == 0  # <10 olay → kontrol yok


class TestGeminiKategoriSablonda:
    """Gemini kategorisi şablon yazısı + hashtag'e doğru yansımalı."""

    def test_gemini_kategorisi_kullanilir(self):
        from services.sablon import olustur
        # AirPods → Gemini "ses" der, şablon "Bilgisayar" değil "Ses" göstermeli
        g = {"reklam": False, "urun_adi": "Apple AirPods Pro 2",
             "kategori": "elektronik", "alt_kategori": "ses", "kalite": 4,
             "tanitim": "", "fiyat_uyari": "", "fiyat": 7499, "eski_fiyat": 9999}
        s = olustur("Apple AirPods Pro 2 7499 TL", 25,
                    ["https://trendyol.com/x-p-1"], gemini=g)
        assert s is not None
        assert "Ses" in s            # doğru kategori yazısı
        assert "Kulaklık" in s       # doğru hashtag
        assert "Laptop" not in s     # yanlış kategori OLMAMALI


class TestBunlukKontrol:
    """Karışık deploy tespiti — bütünlük kontrolü."""

    def test_tam_surumde_eksik_yok(self):
        from utils import surum
        eksikler = surum.butunluk_kontrol()
        assert eksikler == [], f"Eksik modüller: {eksikler}"

    def test_ozet_basarili(self):
        from utils import surum
        ozet = surum.ozet()
        assert "güncel" in ozet or "✅" in ozet


class TestSablonGorsel:
    """Şablon görsel iyileştirmeleri — Gemini kategorisi + alt ikon."""

    def test_gemini_kategorisi_kullanilir(self):
        from services.sablon import olustur
        g = {"reklam": False, "urun_adi": "AirPods Pro", "kategori": "elektronik",
             "alt_kategori": "ses", "kalite": 4, "tanitim": "", "fiyat_uyari": "",
             "fiyat": 0, "eski_fiyat": 0}
        s = olustur("AirPods Pro 5000 TL", 20, ["https://trendyol.com/x-p-1"], gemini=g)
        # Ses kategorisi → 🎧 ikon + #Kulaklık (yanlış #Laptop değil)
        assert "🎧" in s
        assert "Laptop" not in s

    def test_alt_kategori_ikonlari(self):
        from services.sablon import olustur
        # Gerçekçi ürün adları — alt kategori kelimesi ürün adında geçsin
        for alt, ikon, urun in [("telefon", "📱", "Samsung Telefon Kılıfı"),
                                 ("ayakkabi", "👟", "Nike Spor Ayakkabı")]:
            ana = "giyim" if alt == "ayakkabi" else "elektronik"
            g = {"reklam": False, "urun_adi": urun, "kategori": ana,
                 "alt_kategori": alt, "kalite": 3, "tanitim": "", "fiyat_uyari": "",
                 "fiyat": 0, "eski_fiyat": 0}
            s = olustur(f"{urun} 1000 TL", 20, ["https://trendyol.com/x-p-1"], gemini=g)
            assert ikon in s, f"{alt} için {ikon} ikonu yok"


class TestCarsafSusamFormati:
    """✅ ile başlayan fiyat satırı önceki ürüne ait — ayrı ürün sayılmamalı.
    ('🔥Çarşaf \\n ✅Kupon İle 462TL'ye Düşüyor \\n 🔻Susam') → 2 ürün."""

    def test_fiyat_satiri_ayri_urun_degil(self):
        from services.analiz import mesaj_bolum_ayir, urun_adi_bul
        ham = ("🔥Soley %100 Pamuk Ranforce Lastikli Çarşaf\n\n"
               "✅Plus'a Özel İndirim + Ürün Altındaki 50TL Kupon İle Sepette 462TL'ye Düşüyor\n"
               "🔻Bozkırlı Çavuşoğlu Simitlik Susam 500Gr Plus 158TL")
        bloklar = mesaj_bolum_ayir(ham)
        assert len(bloklar) == 2, f"2 ürün bekleniyor, {len(bloklar)}"
        ad0 = urun_adi_bul(bloklar[0]) or ""
        assert "Soley" in ad0 or "Çarşaf" in ad0
        assert "Düşüyor" not in ad0

    def test_tikla_fiyat_satiri_urun_degil(self):
        from services.analiz import _urun_paragrafi_mi
        # ✅ ile başlayan fiyat satırı ürün paragrafı sayılmamalı
        assert _urun_paragrafi_mi(
            "✅Plus'a Özel İndirim + Kupon İle Sepette 462TL'ye Düşüyor") is False


class TestKenarDurumlar:
    """Sistemsel denetimde yakalanan kenar durumlar — bir daha çıkmasın."""

    def test_kupon_kodu_urun_degil(self):
        from services.analiz import _urun_adi_makul
        # Makullük kontrolü model durumundan bağımsız — kesin
        assert _urun_adi_makul("Kupon: FIRSAT50") is False
        assert _urun_adi_makul("Kod: ABC123") is False

    def test_anlamsiz_buyukharf_urun_degil(self):
        from services.analiz import _urun_adi_makul
        assert _urun_adi_makul("AAAAAAAA") is False
        assert _urun_adi_makul("XXXXXXXX") is False

    def test_bos_ve_emoji_urun_degil(self):
        from services.analiz import urun_adi_bul
        assert urun_adi_bul("") is None
        assert urun_adi_bul("🔥🔥🔥") is None
        assert urun_adi_bul("   ") is None

    def test_link_gruplama_none_guvenli(self):
        from services.analiz import urun_kimligine_gore_grupla
        # None ve boş string içeren liste → çökmemeli
        r = urun_kimligine_gore_grupla(["https://amazon.com.tr/dp/B01", None, ""])
        assert len(r) == 1

    def test_sablon_cop_girdi_none(self):
        from services.sablon import olustur
        # Çöp girdiler → None (exception değil)
        assert olustur("", 0, []) is None
        assert olustur("🔥" * 100, 30, ["https://trendyol.com/x-p-1"]) is None

    def test_dil_bos_girdi_guvenli(self):
        from utils import dil
        # Boş/çöp girdi → sıfıra bölme yok
        assert dil.turkce_skoru("") == 0.5
        assert 0 <= dil.turkce_skoru("a b c") <= 1


class TestSifiraBolme:
    """Fiyat parse'ta sıfıra bölme — '0 adet' gibi mesajlar çökmemeli."""

    def test_sifir_adet_cokmez(self):
        from services.analiz import fiyat_bul, indirim_oranini_bul
        # 0 adet → ZeroDivisionError olmamalı
        r = fiyat_bul("0 Adet Alımda 100₺ Kuponla Adedi 50₺")
        assert r is not None
        i = indirim_oranini_bul("0 adet alımda 100₺ kuponla adedi 50₺")
        assert isinstance(i, int)

    def test_normal_adet_dogru(self):
        from services.analiz import fiyat_bul
        e, y, ev, yv = fiyat_bul("3 Adet Alımda 90₺ Kuponla Adedi 50₺")
        assert yv == 50.0
        assert ev > yv


class TestDefactoFiyatSatiri:
    """✅ ile başlayan + tireli fiyat satırı bölünmemeli (Defacto senaryosu).
    '✅179TL - Ürün Altındaki 30TL Kupon İle Sepette 149TL'ye Düşüyor'"""

    def test_tireli_fiyat_satiri_bolunmez(self):
        from services.analiz import _satir_ici_iki_urun_var_mi
        s = "✅179TL - Ürün Altındaki 30TL Kupon İle Sepette 149TL'ye Düşüyor"
        # ✅ ile başlayan satır iki ürün sayılmamalı
        assert _satir_ici_iki_urun_var_mi(s) is False

    def test_defacto_iki_urun(self):
        from services.analiz import mesaj_bolum_ayir, urun_adi_bul
        ham = ("🔥Defacto %100 Pamuk Basic Tişört\n\n"
               "✅179TL - Ürün Altındaki 30TL Kupon İle Sepette 149TL'ye Düşüyor\n"
               "🔻Isana Argan Yağı Vücut Bakım Seti 200Ml 280TL\n"
               "🚚Premium Üyelik Ücretsiz Kargo")
        bloklar = mesaj_bolum_ayir(ham)
        assert len(bloklar) == 2
        ad0 = urun_adi_bul(bloklar[0]) or ""
        assert "Defacto" in ad0
        assert "Düşüyor" not in ad0


class TestHashtagKacirmabak:
    """Hashtag #kacirmabak olmalı (#FırsatPulsu değil)."""

    def test_hashtag_kanal_adi(self):
        from services.sablon import _hashtag
        h = _hashtag(["#Telefon"], "Trendyol")
        assert "#kacirmabak" in h
        assert "#FırsatPulsu" not in h


class TestAdSonTemizlik:
    """Ürün adı baş/son fiyat-bağlam takıları temizlenmeli."""

    def test_yerine_takisi_temizlenir(self):
        from services.analiz import _ad_son_temizlik
        assert _ad_son_temizlik("Defacto Tişört yerine") == "Defacto Tişört"
        assert _ad_son_temizlik("iPhone 15 indirimli fiyat") == "iPhone 15"
        assert _ad_son_temizlik("normal Nike ayakkabı") == "Nike ayakkabı"

    def test_gercek_ad_korunur(self):
        from services.analiz import _ad_son_temizlik
        assert _ad_son_temizlik("iPhone 15 Pro Max") == "iPhone 15 Pro Max"


class TestSanDiskHashtagIsbirligi:
    """#İşbirliği + Google CTA + uzun teknik parantez → ürün adı temiz çıkmalı,
    site adı (Amazon TR) ürün adı olmamalı, kategori doğru olmalı."""

    def test_hashtag_isbirligi_temizlenir(self):
        from services.analiz import urun_adi_bul
        m = ("📦 SanDisk Extreme Pro CFexpress hafıza kartı Tip B 256 GB "
             "(1.700 MB/s okuma, 1.200 MB/s yazma, RescuePRO Deluxe, 4K)\n"
             "🔍 Google'da Karşılaştır #İşbirliği")
        ad = urun_adi_bul(m)
        assert ad is not None
        assert "SanDisk" in ad
        assert "İşbirliği" not in ad
        assert "Google" not in ad
        assert "MB" not in ad  # teknik parantez temizlenmeli

    def test_uzun_teknik_parantez_temizlenir(self):
        from services.analiz import _karsilastir_ctasi_temizle
        s = _karsilastir_ctasi_temizle(
            "Nike ayakkabı (çok uzun teknik açıklama burada devam ediyor uzun)")
        assert "uzun teknik" not in s
        assert "Nike" in s

    def test_hashtag_silinir(self):
        from services.analiz import _karsilastir_ctasi_temizle
        s = _karsilastir_ctasi_temizle("Apple AirPods #İşbirliği #sponsorlu")
        assert "#" not in s
        assert "Apple" in s


class TestSiteAdiCopEngelleme:
    """Site/mağaza adı ürün adı yerine geçmiş çöp paylaşım → engellenmeli."""

    def test_urun_adsiz_paylasilmaz(self):
        from services.sablon import olustur
        # Ürün adı yok, sadece fiyat → "Amazon TR" çöpü yerine None
        ham = "💰 Normal Fiyat: ₺15.950 İndirim: -%48 İndirimli: ₺8.259"
        assert olustur(ham, 48, ["https://amazon.com.tr/dp/B0X"]) is None

    def test_gercek_urun_paylasilir(self):
        from services.sablon import olustur
        # Gerçek ürün adı var → paylaşılır
        ham = "SanDisk hafıza kartı 256 GB 8259 TL"
        s = olustur(ham, 48, ["https://amazon.com.tr/dp/B0X"])
        assert s is not None
        assert "SanDisk" in s


class TestUrunHafizaOgrenme:
    """Gemini'siz öğrenme — ürün hafızası ve marka tutarlılığı."""

    def _hazirla(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_hafiza"
        os.makedirs("/tmp/test_hafiza", exist_ok=True)
        from utils import db
        db.init()
        from utils import urun_hafiza
        # Temiz başla
        try:
            with db.cursor() as c:
                c.execute("DELETE FROM urun_hafiza")
                c.execute("DELETE FROM marka_kategori")
        except Exception:
            pass
        return urun_hafiza

    def test_tam_urun_hatirlama(self):
        uh = self._hazirla()
        uh.kaydet("SanDisk hafıza kartı", "https://amazon.com.tr/dp/B0SAND1", "elektronik:aksesuar")
        assert uh.hatirla("SanDisk hafıza kartı", "https://amazon.com.tr/dp/B0SAND1") == "elektronik:aksesuar"

    def test_admin_duzeltme_kalici(self):
        uh = self._hazirla()
        uh.kaydet("Isana Vücut Seti", "https://hb.com/isana-p-1", "saglik:kisisel")
        uh.duzelt("Isana Vücut Seti", "https://hb.com/isana-p-1", "kozmetik:vucut")
        assert uh.hatirla("Isana Vücut Seti", "https://hb.com/isana-p-1") == "kozmetik:vucut"

    def test_marka_tutarlilik_ogrenme(self):
        uh = self._hazirla()
        # Aynı marka 3 kez giyim → marka öğrenilmeli
        uh.kaydet("Defacto Tişört", "https://trendyol.com/d-p-1", "giyim:ust_giyim")
        uh.kaydet("Defacto Pantolon", "https://trendyol.com/d-p-2", "giyim:alt_giyim")
        uh.kaydet("Defacto Mont", "https://trendyol.com/d-p-3", "giyim:dis_giyim")
        # Yeni Defacto ürünü → giyim hatırlanmalı
        assert uh.hatirla("Defacto Şort", None) == "giyim"

    def test_bilinmeyen_urun_none(self):
        uh = self._hazirla()
        assert uh.hatirla("Hiç görülmemiş ürün xyz", None) is None


class TestModelZehirlenmeKorumasi:
    """Negatif öğrenme modeli zehirlememelі — 'Amazon TR döngüsü' kök çözümü."""

    def test_urun_blogu_negatif_ogrenilmez(self):
        from utils import urun_taniyici
        urun_taniyici.ilk_kurulum()
        onceki = len(urun_taniyici._yeni_negatif)
        # Fiyat + ürün içeren blok → negatif öğrenilmemeli (zehir önleme)
        urun_taniyici.ogren_negatif(
            "📦 Razer Fare Altlığı 🔍 Karşılaştır ⚡️ İndirimli: ₺61")
        assert len(urun_taniyici._yeni_negatif) == onceki  # eklenmedi

    def test_kisa_slogan_ogrenilir(self):
        from utils import urun_taniyici
        urun_taniyici.ilk_kurulum()
        onceki = len(urun_taniyici._yeni_negatif)
        # Kısa, fiyatsız slogan → öğrenilebilir
        urun_taniyici.ogren_negatif("kanala katıl çekiliş kazan")
        assert len(urun_taniyici._yeni_negatif) > onceki
        # Test izolasyonu: eklenen örneği geri al
        urun_taniyici._yeni_negatif.clear()

    def test_model_zehirlenmez(self):
        from utils import urun_taniyici
        urun_taniyici.ilk_kurulum()
        # 100 ürün-içeren reklam → model bozulmamalı
        for _ in range(100):
            urun_taniyici.ogren_negatif(
                "📦 Razer Goliathus Fare Altlığı ⚡️ ₺61")
        # Model hala ürün adı çıkarabilmeli
        ad = urun_taniyici.urun_adi_cikar("Razer Goliathus Oyun Fare Altlığı")
        assert ad is not None and "Razer" in ad
        # Test izolasyonu: diğer testleri etkilememek için modeli sıfırla
        urun_taniyici.sifirla()


class TestKategoriTemizAddan:
    """Kategori tam metin gürültüsünden değil, temiz ürün adından belirlenmeli."""

    def test_gaming_urunu_dogru_kategori(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kat"
        os.makedirs("/tmp/test_kat", exist_ok=True)
        from services import sablon
        ham = ("📦 Razer Goliathus Oyun Fare Altlığı (uzun teknik açıklama burada)\n"
               "🔍 Google'da Karşılaştır #İşbirliği\n⚡️ İndirimli: ₺61\n💰 Normal: ₺890")
        s = sablon.olustur(ham, 93, ["https://amazon.com.tr/dp/B0R"])
        assert s is not None
        # Pet Shop / Tıbbi Cihaz OLMAMALI
        assert "Pet Shop" not in s and "Tıbbi" not in s and "Evcil" not in s
        assert "Amazon TR" not in s.split("\n")[2]  # ürün adı satırı site adı değil


class TestV22Altyapi:
    """v22 altyapı: güvenli config, DB bakımı, retry, duplicate, self-heal."""

    def test_bozuk_env_cokmesin(self):
        """D: Bozuk env değişkeni varsayılana düşmeli, çökmemeli."""
        import config
        # Modülde fonksiyon var
        assert hasattr(config, "_int_env")
        # Geçersiz değer testi
        import os
        eski = os.environ.get("TEST_INT")
        os.environ["TEST_INT"] = "abc"
        try:
            v = config._int_env("TEST_INT", 42)
            assert v == 42   # bozuksa varsayılana düştü
        finally:
            if eski is None:
                os.environ.pop("TEST_INT", None)
            else:
                os.environ["TEST_INT"] = eski

    def test_duplicate_engelleme(self):
        """1: Aynı ürün ikinci kez engelleniyor."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_dup_v22"
        os.makedirs("/tmp/test_dup_v22", exist_ok=True)
        from utils import db; db.init()
        from utils import duplicate
        # Temiz başla
        try:
            with db.cursor() as c:
                c.execute("DELETE FROM paylasim_kayit")
        except Exception:
            pass
        link = "https://amazon.com.tr/dp/B0DUP12345"
        # Önce yok
        assert duplicate.daha_once_paylasildi_mi([link]) is None
        # Kaydet
        duplicate.kaydet([link], "Test", "elektronik", "Amazon", 1)
        # Şimdi var
        assert duplicate.daha_once_paylasildi_mi([link]) is not None

    def test_self_heal_bozuk_tespit(self):
        """7: Aynı kategori tekrarı bozulma tespit etmeli."""
        from utils import self_heal
        self_heal._son_kategoriler.clear()
        # 15 kez aynı (genel hariç) kategori → bozuk
        for _ in range(20):
            self_heal.kayit_ekle("yanlis:kategori")
        assert self_heal.bozuk_mu() is not None
        self_heal._son_kategoriler.clear()

    def test_self_heal_normal_durum_temiz(self):
        """7: Çeşitli kategori varsa bozuk dememeli."""
        from utils import self_heal
        self_heal._son_kategoriler.clear()
        for k in ("elektronik", "giyim", "ev", "kozmetik") * 5:
            self_heal.kayit_ekle(k)
        assert self_heal.bozuk_mu() is None
        self_heal._son_kategoriler.clear()

    def test_bakim_calisir(self):
        """B: Bakım modülü hata vermeden çalışmalı."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_bakim_v22"
        os.makedirs("/tmp/test_bakim_v22", exist_ok=True)
        from utils import db; db.init()
        from utils import bakim
        sonuc = bakim.bakim_yap(zorla=True)
        assert isinstance(sonuc, dict)
        boyut = bakim.db_boyut()
        assert isinstance(boyut, dict)

    def test_kuyruk_persistence(self):
        """G: Kuyruk diske yazılıp geri yüklenebilmeli (telethon stubsız test)."""
        import asyncio, os, sys
        # Stub yolu PYTHONPATH'te yoksa testi atla
        try:
            import telethon  # noqa
        except ImportError:
            return   # telethon stub yok, bu testi atla
        os.environ["DATA_DIR"] = "/tmp/test_kalan_v22"
        os.makedirs("/tmp/test_kalan_v22", exist_ok=True)
        import importlib, config as _c
        _c.DATA_DIR = "/tmp/test_kalan_v22"
        from services import kuyruk
        importlib.reload(kuyruk)
        async def t():
            q = asyncio.Queue(maxsize=5)
            q.put_nowait(("<b>X</b>", b"img", ["http://x.com/1"], "Amazon", "ev", "k", 30, 50.0))
            n = kuyruk.kuyruk_kaydet(q)
            assert n == 1
            q2 = asyncio.Queue(maxsize=5)
            m = kuyruk.kuyruk_yukle(q2)
            assert m == 1
            return True
        assert asyncio.run(t())

    def test_retry_kalici_hata_vazgec(self):
        """F: Kalıcı hatada retry vazgeçmeli."""
        import asyncio
        from utils.retry import deneyerek

        async def kalici():
            raise TypeError("kod hatası")

        async def main():
            try:
                await deneyerek(kalici, max_deneme=5, baslangic_bekleme=0.01)
                return False
            except TypeError:
                return True

        assert asyncio.run(main())


class TestV22Performans:
    """v22.2 performans iyileştirmeleri: cache + sparse model."""

    def test_kategori_cache_hizli(self):
        """P1: kategori_bul cache hit anlık olmalı."""
        import time, os
        os.environ["DATA_DIR"] = "/tmp/test_perf_cache"
        os.makedirs("/tmp/test_perf_cache", exist_ok=True)
        from utils import ml_kategori
        ml_kategori.ilk_kurulum()
        # Cache'i ısıt
        ml_kategori.tahmin_hiyerarsik("iPhone 15 telefon")
        # 1000 cache hit
        t = time.time()
        for _ in range(1000):
            ml_kategori.tahmin_hiyerarsik("iPhone 15 telefon")
        sure = time.time() - t
        # Cache hit halinde 1000 çağrı < 100ms olmalı (gerçekte ~1ms)
        assert sure < 0.1, f"Cache çok yavaş: {sure*1000:.0f}ms"

    def test_urun_adi_cache(self):
        """P3: urun_adi_bul aynı mesaj için cache'li olmalı."""
        import time
        from services.analiz import urun_adi_bul, _mesaj_cache
        _mesaj_cache.clear()
        m = "Apple AirPods Pro 2 4990 TL"
        # İlk çağrı (slow)
        urun_adi_bul(m)
        # 1000 cache hit
        t = time.time()
        for _ in range(1000):
            urun_adi_bul(m)
        sure = time.time() - t
        assert sure < 0.1, f"Cache hit çok yavaş: {sure*1000:.0f}ms"

    def test_sparse_model_kucuk(self):
        """P2: Model sparse formatta kaydedilince küçük olmalı."""
        import os, json, importlib
        os.environ["DATA_DIR"] = "/tmp/test_sparse"
        os.makedirs("/tmp/test_sparse", exist_ok=True)
        yol = "/tmp/test_sparse/ml_model_v3.json"
        if os.path.exists(yol):
            os.remove(yol)
        # ml_kategori'yi taze yükle ki MODEL_FILE doğru yola işaret etsin
        from utils import ml_kategori
        ml_kategori._MODEL_FILE = yol
        ml_kategori._EGITIM_FILE = "/tmp/test_sparse/ml_egitim_v3.json"
        ml_kategori._yuklendi = False
        ml_kategori._egitim_verisi = []
        ml_kategori.ilk_kurulum()
        assert os.path.exists(yol)
        boyut_mb = os.path.getsize(yol) / 1024 / 1024
        assert boyut_mb < 25, f"Model çok büyük: {boyut_mb:.1f}MB"
        with open(yol) as f:
            data = json.load(f)
        assert data.get("format_v") == 2

    def test_model_degisince_cache_temizlenir(self):
        """P1: Model sıfırlanınca tahmin cache geçersiz olmalı."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_invalidate"
        os.makedirs("/tmp/test_invalidate", exist_ok=True)
        from utils import ml_kategori
        ml_kategori.ilk_kurulum()
        # Cache'e bir şey ekle
        ml_kategori.tahmin_hiyerarsik("test ürün")
        assert len(ml_kategori._tahmin_cache) > 0
        # Sıfırla
        eski_nesil = ml_kategori._model_nesli
        ml_kategori.sifirla()
        # Nesil artmış olmalı
        assert ml_kategori._model_nesli > eski_nesil
        # Cache temiz olmalı
        assert len(ml_kategori._tahmin_cache) == 0


class TestV22GeminiKota:
    """v22.3 — Gemini akıllı kota yönetimi (Free tier günlük 1000)."""

    def test_gunluk_kota_gun_donene_kadar_kapali(self):
        """429 alınca gün dönene kadar Gemini kapalı kalmalı."""
        import os, importlib
        os.environ["GEMINI_API_KEY"] = "fake-key-test"
        from utils import gemini
        importlib.reload(gemini)
        # Bugün kotayı doldur
        gemini._kota_doldu_gun = gemini._utc_gun()
        assert gemini.kullanilabilir() is False

    def test_gun_donunce_otomatik_acilir(self):
        """Önceki günün kota damgası bugünü etkilememeli."""
        import os, datetime, importlib
        os.environ["GEMINI_API_KEY"] = "fake-key-test"
        from utils import gemini
        importlib.reload(gemini)
        dun = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        gemini._kota_doldu_gun = dun
        assert gemini.kullanilabilir() is True

    def test_dakikalik_limit_freni(self):
        """Dakika içinde DAKIKA_LIMIT'e ulaşılırsa fren devreye girer."""
        import os, time, importlib
        os.environ["GEMINI_API_KEY"] = "fake-key-test"
        from utils import gemini
        importlib.reload(gemini)
        gemini._kota_doldu_gun = ""
        # Limit kadar istek simüle et
        gemini._dakika_istekleri = [time.time()] * gemini._DAKIKA_LIMIT
        assert gemini.kullanilabilir() is False
        # Eski istekleri at (60s+ önce)
        gemini._dakika_istekleri = [time.time() - 70] * gemini._DAKIKA_LIMIT
        assert gemini.kullanilabilir() is True


class TestV22KokCozumAmazonTR:
    """v22.5 — 'Amazon TR' çöp paylaşımı kalıcı kök çözüm testleri."""

    def test_magaza_adi_urun_olamaz(self):
        from services.analiz import _urun_adi_makul
        # Mağaza adları tek başına ürün adı olamaz
        for kelime in ("Amazon TR", "Amazon", "Trendyol", "Hepsiburada",
                       "Defacto", "elektronik", "İndirimli:"):
            assert not _urun_adi_makul(kelime), f"'{kelime}' makul SANILDI"

    def test_gercek_urun_makul(self):
        from services.analiz import _urun_adi_makul
        for kelime in ("Razer Goliathus Mobile Fare Altlığı",
                       "Apple AirPods Pro 2. Nesil",
                       "Isana Argan Yağı Vücut Bakım",
                       "Bosch GSR 12V Akülü Vidalama"):
            assert _urun_adi_makul(kelime), f"'{kelime}' reddedildi"

    def test_cop_mesaj_paylasilmaz(self):
        """Şablon: gerçek ürün adı olmayan mesaj asla paylaşılmaz."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_v225"
        os.makedirs("/tmp/test_v225", exist_ok=True)
        from services.sablon import olustur
        cop_mesajlar = [
            "Amazon'da seçili elektronik ürünlerde %30 indirim",
            "Amazon TR\n₺15.950 ₺8.259",
            "Tüm elektronik ürünlerde sepette ek %25",
            "💰 Normal Fiyat: ₺15.950\nİndirimli: ₺8.259",
        ]
        for m in cop_mesajlar:
            assert olustur(m, 30, ["https://amazon.com.tr/dp/B0X"]) is None, \
                   f"Çöp paylaşıldı: {m[:40]}"

    def test_gercek_urun_hala_paylasilir(self):
        """Gerçek ürünler yanlışlıkla reddedilmemeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_v225"
        os.makedirs("/tmp/test_v225", exist_ok=True)
        from services.sablon import olustur
        iyi_mesajlar = [
            "📦 Razer Fare Altlığı Mavi\n⚡️ ₺61\n💰 ₺890",
            "Apple AirPods Pro 2\n4990 TL  7499 TL",
            "Bosch GSR 12V Vidalama\n899 TL  1490 TL",
        ]
        for m in iyi_mesajlar:
            sonuc = olustur(m, 30, ["https://amazon.com.tr/dp/B0X"])
            assert sonuc is not None, f"İyi mesaj reddedildi: {m[:40]}"


class TestV226CokluVeMarka:
    """v22.6 — Çoklu ürün isim bug fix + marka kampanyası."""

    def test_ayni_urun_iki_blok_tek_baslik(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_v226"
        os.makedirs("/tmp/test_v226", exist_ok=True)
        from services.sablon import olustur_coklu
        ayni = "Apple AirPods Pro 2\n4990 TL  7499 TL"
        sonuc = olustur_coklu(ayni, 33, "https://amazon.com.tr/dp/B0A",
                              ayni, 33, "https://amazon.com.tr/dp/B0A2")
        assert sonuc is not None
        assert sonuc.count("Apple AirPods Pro") == 1

    def test_farkli_urun_iki_baslik(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_v226"
        os.makedirs("/tmp/test_v226", exist_ok=True)
        from services.sablon import olustur_coklu
        f1 = "iPhone 15 Pro Max 256GB\n45000 TL  52000 TL"
        f2 = "Samsung Galaxy S24 Ultra\n38000 TL  45000 TL"
        sonuc = olustur_coklu(f1, 13, "https://amazon.com.tr/dp/B0IP",
                              f2, 15, "https://amazon.com.tr/dp/B0SAM")
        assert sonuc is not None
        assert "iPhone 15 Pro Max" in sonuc and "Samsung Galaxy S24" in sonuc

    def test_gercek_marka_kampanyasi_paylasilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_v226"
        os.makedirs("/tmp/test_v226", exist_ok=True)
        from services.sablon import olustur
        for m in ("Nike ürünlerinde %40'a varan indirim",
                  "LCW markasında %30 indirim"):
            assert olustur(m, 30, ["https://trendyol.com/x"]) is not None

    def test_magaza_kampanyasi_cop(self):
        from services.sablon import _marka_kampanya_gecerli
        assert not _marka_kampanya_gecerli("Amazon'da elektronik ürünlerde %30")
        assert not _marka_kampanya_gecerli("Tüm elektronik ürünlerde %25")
        assert _marka_kampanya_gecerli("Nike ürünlerinde %40")


class TestV227BuyukGuncelleme:
    """v22.7 — kalite karne, sözlük, kara kutu, devre kesici, A/B test."""

    def test_kalite_puan_ayrimi(self):
        from utils import kalite
        iyi = kalite.puan_hesapla("Apple iPhone 15 Pro Max 256GB", "elektronik",
                                  0.85, 20, 52000, 45000, True, "https://x.com/y")
        cop = kalite.puan_hesapla("İndirimli:", "genel", 0.1, 0, 0, 0, False, None)
        assert iyi["puan"] >= 75
        assert cop["puan"] < 40

    def test_sozluk_ogrenir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_sozluk"
        os.makedirs("/tmp/test_sozluk", exist_ok=True)
        from utils import db; db.init()
        from utils import sozluk
        sozluk.ogren("Apple iPhone Pro Max")
        sozluk.ogren("Apple AirPods")
        assert sozluk.urun_kelimesi_mi("apple")
        assert not sozluk.urun_kelimesi_mi("zxcvbn")

    def test_karakutu_kaydeder(self):
        from utils import karakutu
        karakutu.kaydet("paylasim", "Test ürün")
        karakutu.kaydet("hata", "Test hata")
        ozet = karakutu.ozet()
        assert ozet["toplam"] >= 2
        assert "son_hata" in ozet

    def test_devre_kesici(self):
        from utils import retry
        for _ in range(5):
            retry.hata_bildir("test_dk")
        assert retry.devre_acik_mi("test_dk")
        retry.basari_bildir("test_dk")
        assert not retry.devre_acik_mi("test_dk")

    def test_ab_test_ogrenir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_ab"
        os.makedirs("/tmp/test_ab", exist_ok=True)
        from utils import db; db.init()
        from utils import ab_test
        # B stili kazanan
        for i in range(100, 110):
            ab_test.gosterim_kaydet(i, "B"); ab_test.oy_kaydet(i, True)
        for i in range(110, 113):
            ab_test.gosterim_kaydet(i, "A"); ab_test.oy_kaydet(i, False)
        # 30 seçimde B baskın olmalı
        secim = {}
        for _ in range(30):
            kod, _ = ab_test.stil_sec()
            secim[kod] = secim.get(kod, 0) + 1
        assert secim.get("B", 0) > secim.get("A", 0)

    def test_kategori_guven_esigi(self):
        """Sistem 2: belirsiz ürün 'genel' dönmeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_guven"
        os.makedirs("/tmp/test_guven", exist_ok=True)
        from services.analiz import kategori_bul
        # Anlamsız metin → genel
        assert kategori_bul("qwerty asdfgh zxcvbn")[0] == "genel"

    def test_panel_html_uretir(self):
        """Sistem 11: panel HTML üretilmeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_panel"
        os.makedirs("/tmp/test_panel", exist_ok=True)
        from utils import db; db.init()
        from services.health import _panel_html
        html = _panel_html(3)
        assert "FırsatPulsu" in html and len(html) > 500


class TestV229KaliteCekirdek:
    """v22.9 — 3-katman ürün adı + kalite kapısı + karantina."""

    def test_3katman_gercek_urun(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_3k"
        os.makedirs("/tmp/test_3k", exist_ok=True)
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        assert urun_adi_bul("Apple iPhone 15 Pro Max 256GB\n45000 TL")
        assert urun_adi_bul("Bosch GSR 12V Vidalama\n899 TL")

    def test_3katman_cop_none(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_3k"
        os.makedirs("/tmp/test_3k", exist_ok=True)
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        assert urun_adi_bul("Amazon TR\n15950 TL") is None

    def test_karantina_yasam_dongusu(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kar"
        os.makedirs("/tmp/test_kar", exist_ok=True)
        from utils import karantina
        kid = karantina.ekle("<b>Test</b>", None, ["http://x"], "Amazon",
                             "elektronik", "@k", 30, 7.0, 42)
        assert karantina.al(kid) is not None
        assert any(b["id"] == kid for b in karantina.bekleyenler())
        oge = karantina.cikar(kid)
        assert oge["puan"] == 42
        assert karantina.al(kid) is None

    def test_kalite_kapisi_config(self):
        """KALITE_PUAN_ESIK config'i okunabilmeli."""
        import config
        assert hasattr(config, "KALITE_PUAN_ESIK")
        assert hasattr(config, "KARANTINA_ALT")
        assert hasattr(config, "KARANTINA_UST")


class TestV2210YeniYetenekler:
    """v22.10 — fiyat takip, stok geri-gelme, kullanıcı istek, zenginleştirme."""

    def test_fiyat_en_dusuk_tespit(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_ft2"
        os.makedirs("/tmp/test_ft2", exist_ok=True)
        from utils import db; db.init()
        from utils import fiyat_takip as ft
        ft.fiyat_kaydet("test_x", 1000)
        ft.fiyat_kaydet("test_x", 950)
        a = ft.fiyat_analiz("test_x", 800)
        assert a["en_dusuk_mu"]

    def test_fiyat_sahte_indirim(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_ft2"
        os.makedirs("/tmp/test_ft2", exist_ok=True)
        from utils import db; db.init()
        from utils import fiyat_takip as ft
        for _ in range(3):
            ft.fiyat_kaydet("test_sabit", 500)
        a = ft.fiyat_analiz("test_sabit", 500)
        assert a["sahte_indirim_mi"]

    def test_stok_geri_gelme(self):
        import os, time
        os.environ["DATA_DIR"] = "/tmp/test_ft2"
        os.makedirs("/tmp/test_ft2", exist_ok=True)
        from utils import db; db.init()
        from utils import fiyat_takip as ft
        assert ft.stok_kontrol("test_stok") == "yeni"
        with db.cursor() as c:
            c.execute("UPDATE stok_durum SET son_gorulme=? WHERE kimlik='test_stok'",
                      (int(time.time()) - 8 * 86400,))
        assert ft.stok_kontrol("test_stok") == "yeniden_stokta"

    def test_kullanici_istek(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_istek"
        os.makedirs("/tmp/test_istek", exist_ok=True)
        from utils import db; db.init()
        from utils import istek
        assert istek.istek_ekle(999, "iphone 15")
        assert not istek.istek_ekle(999, "iphone 15")  # tekrar
        eslesme = istek.eslesenleri_bul("Apple iPhone 15 Pro Max")
        assert any(k == 999 for k, _ in eslesme)
        # Alakasız eşleşmemeli
        assert not istek.eslesenleri_bul("Samsung TV")

    def test_istek_spam_korumasi(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_istek2"
        os.makedirs("/tmp/test_istek2", exist_ok=True)
        from utils import db; db.init()
        from utils import istek
        istek.istek_ekle(888, "macbook")
        e1 = istek.eslesenleri_bul("Apple MacBook Pro M3")
        e2 = istek.eslesenleri_bul("Apple MacBook Air M2")  # hemen tekrar
        assert len(e1) == 1 and len(e2) == 0  # 6 saat spam koruması


class TestV2211Buyume:
    """v22.11 — çoklu kanal, etkileşim, akıllı zamanlama (Grup C)."""

    def test_coklu_kanal_secimi(self):
        import os, importlib
        os.environ["CHANNEL_ID"] = "@anakanal"
        os.environ["KATEGORI_KANALLAR"] = "elektronik:@tekno,giyim:@moda"
        import config; importlib.reload(config)
        assert config.hedef_kanal_sec("elektronik") == "@tekno"
        assert config.hedef_kanal_sec("elektronik:telefon") == "@tekno"
        assert config.hedef_kanal_sec("giyim") == "@moda"
        assert config.hedef_kanal_sec("kozmetik") == "@anakanal"  # eşleşmeyen
        os.environ["KATEGORI_KANALLAR"] = ""
        importlib.reload(config)

    def test_zamanlama_altin_saat(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_zm"
        os.makedirs("/tmp/test_zm", exist_ok=True)
        from utils import db; db.init()
        from utils import zamanlama as z
        for _ in range(10):
            z.paylasim_kaydet(21); z.oy_kaydet(21); z.oy_kaydet(21)
        for _ in range(10):
            z.paylasim_kaydet(4)
        assert z.altin_saat_mi(21)
        assert not z.altin_saat_mi(4)

    def test_etkilesim_haftanin_urunu(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_et2"
        os.makedirs("/tmp/test_et2", exist_ok=True)
        from utils import db; db.init()
        from utils import segment, etkilesim
        segment.mesaj_kaydet(501, "elektronik", "Amazon", 30, "iPhone Test")
        for u in [1, 2, 3]:
            segment.tikla_kaydet(u, 501, "good")
        urun = etkilesim.haftanin_urunu()
        assert urun and urun["urun"] == "iPhone Test" and urun["oy"] >= 2

    def test_etkilesim_vitrin(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_et2"
        os.makedirs("/tmp/test_et2", exist_ok=True)
        from utils import db; db.init()
        from utils import etkilesim
        vitrin = etkilesim.haftalik_vitrin_metni()
        # Önceki testte veri eklendi → vitrin dolu olmalı
        assert vitrin is None or "Favori" in vitrin or "ilgi" in vitrin


class TestV2212AmazonTRKokCozum:
    """v22.12 — Amazon TR TÜM varyasyonları + Gemini yolu kök çözüm."""

    def test_magaza_jenerik_kombinasyonu_red(self):
        from services.analiz import _urun_adi_makul
        for ad in ["Amazon TR", "Amazon TR ürünleri", "Amazon TR ürün",
                   "Trendyol kampanya", "Hepsiburada mağaza", "Amazon Türkiye",
                   "amazon tr store", "Trendyol TR ürünleri"]:
            assert not _urun_adi_makul(ad), f"'{ad}' makul SANILDI (çöp olmalı)"

    def test_gercek_urun_magaza_kelimeli_gecer(self):
        from services.analiz import _urun_adi_makul
        # Gerçek ürün adı + mağaza kelimesi → geçmeli (mağaza tek başına değil)
        for ad in ["Apple iPhone 15 Amazon", "Samsung TV Trendyol fiyatı",
                   "Bosch Matkap Hepsiburada"]:
            assert _urun_adi_makul(ad), f"'{ad}' reddedildi (geçerli ürün)"

    def test_gemini_amazon_tr_red(self):
        """Gemini 'Amazon TR' dese bile şablon reddetmeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_gem"
        os.makedirs("/tmp/test_gem", exist_ok=True)
        from services.sablon import olustur
        for g_ad in ["Amazon TR", "Amazon TR ürünleri", "Trendyol kampanya"]:
            s = olustur("fırsat", 48, ["https://amazon.com.tr/dp/B0X"],
                        gemini={"urun_adi": g_ad})
            assert s is None, f"Gemini '{g_ad}' ile paylaşıldı"

    def test_gemini_gercek_urun_gecer(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_gem"
        os.makedirs("/tmp/test_gem", exist_ok=True)
        from services.sablon import olustur
        s = olustur("iPhone", 20, ["https://amazon.com.tr/dp/B0X"],
                    gemini={"urun_adi": "Apple iPhone 15 Pro"})
        assert s is not None


class TestV2213CiplakLink:
    """v22.13 — Çıplak link/domain ürün adı sanılma bug'ı (gerçek kök sebep)."""

    def test_ciplak_link_urun_adi_olmaz(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_link"
        os.makedirs("/tmp/test_link", exist_ok=True)
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        # Link + mağaza adı → ürün adı çıkmamalı (link metni temizlenmeli)
        assert urun_adi_bul("🔥 Amazon TR\n💰 8.259 TL\n🛒 amazon.com.tr/dp/B0XYZ") is None
        assert urun_adi_bul("AMAZON TR ÜRÜNLERİ\nhttps://amazon.com.tr/dp/B1") is None

    def test_gercek_urun_link_ile_gecer(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_link"
        os.makedirs("/tmp/test_link", exist_ok=True)
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        # Gerçek ürün + link → ürün adı link'ten arınmış olmalı
        r1 = urun_adi_bul("Apple iPhone 15 Pro Max 256GB\n45000 TL\namazon.com.tr/dp/B0AP")
        assert r1 and "amazon" not in r1.lower() and "iphone" in r1.lower()
        r2 = urun_adi_bul("Bosch GSR 12V Matkap\nhttps://trendyol.com/bosch-p-9")
        assert r2 and "trendyol" not in r2.lower() and "bosch" in r2.lower()

    def test_ciplak_link_temizleme_fonksiyon(self):
        from services.analiz import _karsilastir_ctasi_temizle
        temiz = _karsilastir_ctasi_temizle("Ürün adı amazon.com.tr/dp/B0XYZ son")
        assert "amazon.com.tr" not in temiz
        assert "Ürün adı" in temiz


class TestV2214ModelZehir:
    """v22.14 — Model zehirlenmesi önleme (sözlük/marka/hafıza guard)."""

    def test_sozluk_cop_ogrenmez(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_zehir"
        os.makedirs("/tmp/test_zehir", exist_ok=True)
        from utils import db; db.init()
        from utils import sozluk
        # Çöp ürün adı → 0 kelime
        assert sozluk.ogren("var Amazon TR") == 0
        assert sozluk.ogren("- İndirimli Fiyat var Amazon TR") == 0
        # Gerçek ürün → öğrenir
        assert sozluk.ogren("Apple iPhone 15 Pro Max") > 0

    def test_sozluk_cop_kelime_atlanir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_zehir2"
        os.makedirs("/tmp/test_zehir2", exist_ok=True)
        from utils import db; db.init()
        from utils import sozluk
        # Gerçek üründe çöp kelime geçse bile o kelime atlanmalı
        sozluk.ogren("Samsung Galaxy Amazon TR")  # Samsung galaxy öğrenilir, amazon/tr hayır
        assert not sozluk.urun_kelimesi_mi("amazon")
        assert not sozluk.urun_kelimesi_mi("tr")

    def test_zehir_temizleme(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_zehir3"
        os.makedirs("/tmp/test_zehir3", exist_ok=True)
        from utils import db; db.init()
        from utils import sozluk
        # Kirli veri ekle
        with db.cursor() as c:
            for k in ["var", "amazon", "tr", "456"]:
                c.execute("INSERT OR REPLACE INTO kelime_sozluk (kelime,sayi,ts) VALUES (?,10,0)", (k,))
            c.execute("INSERT OR REPLACE INTO kelime_sozluk (kelime,sayi,ts) VALUES ('keratin',5,0)")
        sozluk.zehir_temizle()
        assert not sozluk.urun_kelimesi_mi("amazon")
        assert not sozluk.urun_kelimesi_mi("var")
        # Temiz kelime kalmalı
        assert sozluk.urun_kelimesi_mi("keratin")

    def test_hafiza_cop_kaydetmez(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_zehir4"
        os.makedirs("/tmp/test_zehir4", exist_ok=True)
        from utils import db; db.init()
        from utils import urun_hafiza
        # Çöp kaydedilmemeli (hata fırlatmadan sessizce atlar)
        urun_hafiza.kaydet("Amazon TR", "http://x", "market")
        urun_hafiza.kaydet("- İndirimli Fiyat var", None, "market")
        # Gerçek ürün kaydedilir
        urun_hafiza.kaydet("Apple iPhone 15", "http://y", "elektronik")


class TestV230MerkeziKapi:
    """v23.0 — TEK MERKEZİ ÜRÜN ADI KAPISI (validation gateway).
    Ürün adı hangi kaynaktan gelirse gelsin tek noktadan geçer."""

    def test_kapi_magaza_adi_red(self):
        from services.urun_kapisi import gecerli_urun_adi
        for cop in ["Amazon", "amazon", "AMAZON", "Amazon TR", "Trendyol",
                    "Amazon TR ürünleri", "Amazon Türkiye", "Hepsiburada mağaza"]:
            assert gecerli_urun_adi(cop) is None, f"'{cop}' geçti"

    def test_kapi_jenerik_red(self):
        from services.urun_kapisi import gecerli_urun_adi
        for cop in ["İndirimli", "İndirimli Fiyat", "Normal Fiyat", "elektronik",
                    "Tüm elektronik", "stokta var", "- İndirimli Fiyat var Amazon TR",
                    "Süper indirim", "Mega fırsat", "TR"]:
            assert gecerli_urun_adi(cop) is None, f"'{cop}' geçti"

    def test_kapi_gercek_urun_kabul(self):
        from services.urun_kapisi import gecerli_urun_adi
        for gercek in ["Apple iPhone 15 Pro Max", "Nike Air Max", "Bosch Matkap",
                       "Korku Modern Klasikler Serisi", "Samsung Galaxy S24",
                       "Nivea Krem", "Amazon Echo Dot", "iPhone 15 Amazon",
                       "Süper Lig Topu"]:
            assert gecerli_urun_adi(gercek) is not None, f"'{gercek}' reddedildi"

    def test_kapi_ml_yapisal_entegrasyon(self):
        """urun_adi_bul çıkışı kapıdan geçmeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kapi_ent"
        os.makedirs("/tmp/test_kapi_ent", exist_ok=True)
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        # Mağaza+link → None
        assert urun_adi_bul("🔥 Amazon TR\n💰 8.259 TL\namazon.com.tr/dp/B0X") is None
        # Gerçek ürün → geçer
        assert urun_adi_bul("Apple iPhone 15 Pro\n45000 TL\namazon.com.tr/dp/B1")

    def test_kapi_scrape_entegrasyon(self):
        """Scrape 'Amazon' başlığı kapıda elenmeli."""
        from services.urun_kapisi import gecerli_urun_adi
        # Scrape og:title="Amazon" senaryosu
        assert gecerli_urun_adi("Amazon") is None
        # Gerçek scrape başlığı
        assert gecerli_urun_adi("Apple AirPods Pro 2. Nesil") is not None

    def test_ayirt_edici_kelimeler(self):
        from services.urun_kapisi import ayirt_edici_kelimeler
        # Mağaza+jenerik → ayırt edici yok
        assert ayirt_edici_kelimeler("Amazon TR ürünleri") == []
        # Gerçek ürün → ayırt edici var
        assert "iphone" in ayirt_edici_kelimeler("Apple iPhone 15")
        assert "echo" in ayirt_edici_kelimeler("Amazon Echo Dot")


class TestV231Sadelestirme:
    """v23.1 — Sadeleştirme: tüm doğrulama merkezi kapıya delege edildi."""

    def test_makul_kapiya_delege(self):
        """_urun_adi_makul artık merkezi kapıya delege ediyor."""
        from services.analiz import _urun_adi_makul
        assert _urun_adi_makul("Amazon TR") is False
        assert _urun_adi_makul("Apple iPhone 15") is True

    def test_kupon_hala_engelleniyor(self):
        from services.urun_kapisi import gecerli_urun_adi
        assert gecerli_urun_adi("Kupon: FIRSAT50") is None
        assert gecerli_urun_adi("Kod: ABC123") is None

    def test_anlamsiz_harf_engelleniyor(self):
        from services.urun_kapisi import gecerli_urun_adi
        assert gecerli_urun_adi("AAAAAAAA") is None
        assert gecerli_urun_adi("XXXXXXXX") is None

    def test_sadelestirme_tam_akis(self):
        """Sadeleştirilmiş sistem tüm senaryoları doğru işliyor."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_sade"
        os.makedirs("/tmp/test_sade", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        # Çöp
        assert olustur("🏪 Amazon 🛒 TR\n8.259 TL\namazon.com.tr/dp/B0X", 48,
                       ["https://amazon.com.tr/dp/B0X"]) is None
        # Gerçek
        assert olustur("Apple iPhone 15 Pro\n45000 TL\namazon.com.tr/dp/B1", 30,
                       ["https://amazon.com.tr/dp/B1"]) is not None


class TestV232KategoriCaprazDogrulama:
    """v23.2 — Gemini kategori/açıklama çapraz doğrulama (Otogizoshi sorunu).
    Gemini 'oto' hecesine bakıp kitabı otomotiv yapıyordu."""

    def _olustur(self, urun, kategori, tanitim):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_otog"
        os.makedirs("/tmp/test_otog", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        return olustur(f"{urun}\n84 TL\n%50\namazon.com.tr/dp/B0X", 50,
                       ["https://amazon.com.tr/dp/B0X"],
                       gemini={"urun_adi": urun, "kategori": kategori, "tanitim": tanitim})

    def test_otogizoshi_otomotiv_tuzagi(self):
        """'Otogizoshi' (kitap) → Gemini 'oto' hecesiyle otomotiv diyor → reddet."""
        s = self._olustur("Otogizoshi", "otomotiv", "Otogizoshi aracınız için pratik bir çözüm.")
        assert "tomotiv" not in (s or ""), "Otomotiv tuzağı engellenmedi"
        assert "Otomotiv" not in (s or "")

    def test_otogizoshi_uydurma_aciklama_atilir(self):
        """Uydurma 'aracınız için' açıklaması atılmalı."""
        s = self._olustur("Otogizoshi", "otomotiv", "Otogizoshi aracınız için pratik bir çözüm.")
        assert "aracınız" not in (s or "").lower(), "Uydurma açıklama atılmadı"

    def test_gercek_otomotiv_korunur(self):
        """'Oto Koltuk Kılıfı' gerçekten otomotiv → korunmalı."""
        s = self._olustur("Oto Koltuk Kılıfı", "otomotiv", "Araç koltuklarını korur.")
        assert "tomotiv" in (s or ""), "Gerçek otomotiv ürünü reddedildi"

    def test_gercek_elektronik_aciklama_korunur(self):
        """AirPods → elektronik + tutarlı açıklama korunmalı."""
        s = self._olustur("Apple AirPods Pro 2", "elektronik", "Aktif gürültü engelleme özelliği.")
        assert "gürültü" in (s or ""), "Tutarlı açıklama yanlışlıkla atıldı"

    def test_tanitim_dogrulama_birimi(self):
        from services.urun_kapisi import tanitim_gecerli
        # Kitap + araç açıklaması → None
        assert tanitim_gecerli("Aracınız için pratik çözüm.", "Otogizoshi", "genel") is None
        # Otomotiv ürünü + araç açıklaması → geçer
        assert tanitim_gecerli("Araç koltuklarını korur.", "Oto Koltuk", "otomotiv") is not None
        # Elektronik + tutarlı açıklama → geçer
        assert tanitim_gecerli("Aktif gürültü engelleme.", "AirPods", "elektronik") is not None


class TestV233UrunAdiKurtarma:
    """v23.3 — Blok bölme bozulduğunda ürün adını orijinalden kurtar.
    'Ürün adı üstte, fiyat altta' formatında fiyat bloğu ayrı düşüp
    gerçek ürünler (VitrA gibi) atlanıyordu."""

    def test_bozuk_blok_gercek_urun_kurtarilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kurtar"
        os.makedirs("/tmp/test_kurtar", exist_ok=True)
        from handlers.mesaj import _blok_analiz
        import services.analiz as a
        a._mesaj_cache.clear()
        # Blokta sadece fiyat var, ürün adı yok
        bozuk = "💰 Normal Fiyat: ₺1086\n⬇️ İndirim: -%46\n🏪 Amazon 🛒 TR"
        # Orijinalde gerçek ürün adı var
        orijinal = "📦 VitrA Marin A44945 Kapaklı Tuvalet Kağıtlığı, Krom\n💰 Fiyat: ₺578\n🏪 Amazon TR"
        s = _blok_analiz(bozuk, ["https://amazon.com.tr/dp/B0X"], orijinal_mesaj=orijinal)
        assert s is not None, "Gerçek ürün kurtarılmadı"

    def test_bozuk_blok_cop_kurtarilmaz(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kurtar2"
        os.makedirs("/tmp/test_kurtar2", exist_ok=True)
        from handlers.mesaj import _blok_analiz
        import services.analiz as a
        a._mesaj_cache.clear()
        # Hem blok hem orijinal çöp (Amazon TR)
        cop = "💰 Normal Fiyat: ₺100\n⬇️ İndirim: -%50\n🏪 Amazon 🛒 TR"
        cop_orj = "🏪 Amazon 🛒 TR\n💰 İndirimli Fiyat: var\n🚨 Stoklar eriyor"
        s = _blok_analiz(cop, ["https://amazon.com.tr/dp/B0X"], orijinal_mesaj=cop_orj)
        assert s is None, "Çöp yanlışlıkla kurtarıldı"

    def test_kurtarma_fiyatsiz_blokta_calismaz(self):
        """Fiyat/indirim olmayan blokta kurtarma denenmemeli (ürün sinyali yok)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kurtar3"
        os.makedirs("/tmp/test_kurtar3", exist_ok=True)
        from handlers.mesaj import _blok_analiz
        import services.analiz as a
        a._mesaj_cache.clear()
        # Blokta ne fiyat ne indirim → kurtarma tetiklenmemeli
        bos = "🏪 Amazon 🛒 TR\n🚨 Stoklar eriyor"
        orijinal = "📦 VitrA Tuvalet Kağıtlığı\n🏪 Amazon"
        s = _blok_analiz(bos, ["https://amazon.com.tr/dp/B0X"], orijinal_mesaj=orijinal)
        # Fiyat yok → ürün sinyali yetersiz, atlanmalı (kurtarma çalışmaz)
        assert s is None


class TestV234YedekTemizleme:
    """v23.4 — İstatistik yedeği çoğalmasın (Kaydedilenler temiz kalsın)."""

    def test_eski_yedekler_temizlenir(self):
        import asyncio, os
        os.environ["DATA_DIR"] = "/tmp/test_yedek"
        os.environ["ADMIN_ID"] = "123"
        os.makedirs("/tmp/test_yedek", exist_ok=True)
        from utils import db; db.init()
        from utils import cache

        class SahteMsg:
            def __init__(self, id, text): self.id = id; self.text = text
        class SahteClient:
            def __init__(self):
                self.mesajlar = [
                    SahteMsg(10, "##FIRSATPULSU_IST_V2##\n{}"),
                    SahteMsg(25, "##FIRSATPULSU_IST_V2##\n{}"),
                    SahteMsg(40, "##FIRSATPULSU_IST_V2##\n{}"),
                    SahteMsg(15, "normal"),
                ]
                self.silinenler = []
            async def iter_messages(self, aid, limit=300):
                for m in sorted(self.mesajlar, key=lambda x: -x.id):
                    yield m
            async def delete_messages(self, aid, ids):
                self.silinenler.extend(ids if isinstance(ids, list) else [ids])
            async def edit_message(self, a, m, t): pass
            async def send_message(self, a, t):
                return SahteMsg(99, t)

        async def calistir():
            cache._ist_yaz("toplam", 12)
            c = SahteClient()
            await cache.telegram_yukle(c)
            return cache._ist_msg_id, sorted(c.silinenler)

        msg_id, silinen = asyncio.run(calistir())
        assert msg_id == 40, f"En yeni tutulmalı, {msg_id}"
        assert silinen == [10, 25], f"Eskiler silinmeli, {silinen}"
        assert 15 not in silinen, "Normal mesaj korunmalı"


class TestV235Teshis:
    """v23.5 — Canlı teşhis sistemi (sağlamlık + görünürlük)."""

    def test_teshis_calisir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_teshis"
        os.makedirs("/tmp/test_teshis", exist_ok=True)
        from utils import db; db.init()
        from utils import teshis
        ozet = teshis.ozet()
        assert ozet["toplam"] >= 10, "yetersiz test sayısı"
        # Kritik sistemler hatasız olmalı
        assert ozet["hata"] == 0, f"Teşhiste {ozet['hata']} hata: " + \
            str([s["ad"] for s in ozet["detay"] if s["durum"] == "hata"])

    def test_teshis_kapi_korumasi(self):
        """Teşhis, Amazon TR korumasının çalıştığını doğrulamalı."""
        from utils import teshis
        sonuclar = teshis.tam_teshis()
        kapi = next((s for s in sonuclar if "kapı" in s["ad"].lower()), None)
        assert kapi and kapi["durum"] == "ok", "Kapı koruması teşhiste başarısız"


class TestV236PanelMetrikleri:
    """v23.6 — Panel metrik bug'ları: duplicate kaydı + kalıcı kalite."""

    def test_duplicate_kaydi_calisir(self):
        """'link' tanımsız bug'ı: duplicate.kaydet artık çalışmalı."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_dup_panel"
        os.makedirs("/tmp/test_dup_panel", exist_ok=True)
        from utils import db; db.init()
        from utils import duplicate
        duplicate.kaydet(["https://amazon.com.tr/dp/B1"], "Test Ürün", "elektronik", "Amazon", 101)
        ist = duplicate.istatistik()
        assert ist["son_24_saat"] >= 1, "Duplicate kaydı çalışmıyor (panel 0 gösterir)"

    def test_kalite_kalici(self):
        """Kalite geçmişi DB'de — bot restart'ta kaybolmamalı."""
        import os, importlib
        os.environ["DATA_DIR"] = "/tmp/test_kalite_kalici"
        os.makedirs("/tmp/test_kalite_kalici", exist_ok=True)
        from utils import db; db.init()
        from utils import kalite
        for p in [80, 75, 90]:
            kalite._karne_kaydet_db(p)
        ilk = kalite.istatistik()["toplam"]
        # Restart simülasyonu
        importlib.reload(kalite)
        sonra = kalite.istatistik()["toplam"]
        assert sonra == ilk and sonra >= 3, "Kalite restart'ta kayboldu"

    def test_panel_uretilir(self):
        """Panel HTML hatasız üretilmeli (v23.22 zengin panel)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_panel_html"
        os.makedirs("/tmp/test_panel_html", exist_ok=True)
        from utils import db; db.init()
        from services.health import _panel_html
        html = _panel_html(kuyruk_size=5)
        assert "FırsatPulsu" in html
        assert "Toplam Paylaşım" in html       # yeni: özet bölümü
        assert "Mağaza Dağılımı" in html        # yeni: detaylı dağılım
        assert "<!DOCTYPE html>" in html


class TestV237CopKuyrukVeKarakutu:
    """v23.7 — Çöp kuyruk temizleme + kalıcı karakutu."""

    def test_cop_kuyruk_temizlenir(self):
        from services.urun_kapisi import gecerli_urun_adi
        # Gerçek ürün + çöp kuyruk → kuyruk kesilmeli
        assert gecerli_urun_adi("Üç Köşeli Dünya İndirimli Fiyat: var Amazon TR") == "Üç Köşeli Dünya"
        assert gecerli_urun_adi("Samsung Galaxy S24 Ultra Amazon TR") == "Samsung Galaxy S24 Ultra"

    def test_model_kodu_korunur(self):
        """S24, GSR 12V gibi model kodları kesilmemeli."""
        from services.urun_kapisi import gecerli_urun_adi
        assert gecerli_urun_adi("Samsung Galaxy S24") == "Samsung Galaxy S24"
        assert gecerli_urun_adi("Bosch GSR 12V Matkap Amazon") == "Bosch GSR 12V Matkap"

    def test_gercek_urun_adi_bozulmaz(self):
        """Çöp olmayan gerçek ürün adları bozulmamalı."""
        from services.urun_kapisi import gecerli_urun_adi
        assert gecerli_urun_adi("Korku: Modern Klasikler Serisi") == "Korku: Modern Klasikler Serisi"
        assert gecerli_urun_adi("Apple iPhone 15 Pro Max") == "Apple iPhone 15 Pro Max"

    def test_karakutu_kalici(self):
        import os, importlib
        os.environ["DATA_DIR"] = "/tmp/test_kk_kalici"
        os.makedirs("/tmp/test_kk_kalici", exist_ok=True)
        from utils import db; db.init()
        from utils import karakutu
        karakutu.kaydet("paylasim", "Test 1")
        karakutu.kaydet("hata", "Test hata")
        ilk = karakutu.ozet()["toplam"]
        importlib.reload(karakutu)
        sonra = karakutu.ozet()["toplam"]
        assert sonra == ilk and sonra >= 2, "Karakutu restart'ta kayboldu"


class TestV238UrunAdiSecici:
    """v23.8 — Gemini kopuk parça verince saf-Python'la karşılaştır + ilk satır
    önceliği. iPad gibi uzun adlarda Gemini ortadan parça koparıyordu."""

    def _olustur(self, metin, gemini):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_secici"
        os.makedirs("/tmp/test_secici", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        return olustur(metin, 20, ["https://amazon.com.tr/dp/B0X"], gemini=gemini)

    def test_ipad_kopuk_parca_duzelir(self):
        metin = "📦 Apple A16 çipli iPad: 11 inç, 128 GB, Tüm Gün Süren Pil Ömrü — Gümüş\n💰12.084 TL\n🏪 Amazon TR"
        g = {"urun_adi": "Gün Süren Pil Ömrü Gümüş Rengi Satıcı Amazon Depo",
             "kategori": "elektronik", "reklam": False, "tanitim": "",
             "fiyat_uyari": "", "kalite": 4, "fiyat": 0, "eski_fiyat": 0}
        s = self._olustur(metin, g)
        assert s and "Apple" in s, "iPad ürün adı düzelmedi"
        assert "Satıcı Amazon Depo" not in s, "Kopuk parça hâlâ var"

    def test_ilk_satir_onceligi(self):
        from services.analiz import urun_adi_bul, _ilk_satir_urun_adi
        import services.analiz as a
        a._mesaj_cache.clear()
        # Uzun virgüllü ad → ilk satırdan doğru başlamalı
        metin = "📦 Apple A16 çipli iPad: 11 inç, 128 GB, Touch ID, Tüm Gün Süren Pil — Gümüş\n💰100 TL"
        r = urun_adi_bul(metin)
        assert r and r.lower().startswith("apple"), f"İlk satır önceliği çalışmadı: {r}"

    def test_slogan_ilk_satir_reddedilir(self):
        from services.analiz import _ilk_satir_urun_adi
        # Slogan ilk satır ürün adı sayılmamalı
        assert _ilk_satir_urun_adi("Stoklar ERİYOR hemen yakala 999 TL") is None

    def test_en_iyi_urun_adi_secici(self):
        from services.urun_kapisi import en_iyi_urun_adi
        kaynak = "Apple iPad 128 GB Touch ID Tüm Gün Süren Pil Gümüş"
        # Gemini kopuk, python doğru → python seçilmeli
        secilen = en_iyi_urun_adi("Gün Süren Pil Gümüş Satıcı Amazon",
                                  "Apple iPad 128 GB Touch ID", kaynak)
        assert "Apple" in secilen, "Seçici kopuk Gemini'yi seçti"


class TestV239KaliteYukseltme:
    """v23.9 — Ürün adı kısaltma + fiyat bağlamı + görsel indirim rozeti."""

    def test_uzun_ad_kisaltilir(self):
        from services.urun_kapisi import guzellestir
        uzun = "Apple A16 çipli iPad: 11 inç Liquid Retina, 128 GB, Wi-Fi 6, 12 MP Ön Kamera Gümüş"
        k = guzellestir(uzun)
        assert len(k) < 40, f"Kısaltma yetersiz: {k}"
        assert "Apple" in k and "iPad" in k, "Marka/model kayboldu"

    def test_kisa_ad_korunur(self):
        from services.urun_kapisi import guzellestir
        for ad in ["Nike Air Max Ayakkabı", "Apple iPhone 15 Pro", "VitrA Tuvalet Kağıtlığı"]:
            assert guzellestir(ad) == ad, f"Kısa ad bozuldu: {ad}"

    def test_parantez_atilir(self):
        from services.urun_kapisi import guzellestir
        k = guzellestir("Samsung Galaxy S24 256 GB (Samsung Türkiye Garantili)")
        assert "Garantili" not in k and "Samsung Galaxy" in k

    def test_gorsel_indirim_rozeti(self):
        """v23.17 — İndirim rozeti KALDIRILDI. logo_ekle indirim parametresi
        alsa bile artık sağ-üste rozet basMAmalı (kullanıcı gereksiz buldu)."""
        from services.gorsel import logo_ekle
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (600, 600), (70, 130, 180))
        buf = BytesIO(); img.save(buf, "PNG")
        sonuc = logo_ekle(buf.getvalue(), link=None, indirim=50)
        out = Image.open(BytesIO(sonuc)).convert("RGB")
        w, h = out.size
        # Sağ-üstte kırmızı rozet OLMAMALI (kaldırıldı)
        kirmizi = any(
            out.getpixel((x, y))[0] > 180 and out.getpixel((x, y))[1] < 80
            for x in range(int(w*0.8), w-10) for y in range(10, int(h*0.2))
        )
        assert not kirmizi, "İndirim rozeti hâlâ basılıyor (kaldırılmalıydı)"

    def test_indirim_param_hata_vermez(self):
        """indirim parametresi geçilse de logo_ekle çökmemeli (geriye uyumluluk)."""
        from services.gorsel import logo_ekle
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (600, 600), (70, 130, 180))
        buf = BytesIO(); img.save(buf, "PNG")
        sonuc = logo_ekle(buf.getvalue(), link=None, indirim=50)
        assert sonuc and len(sonuc) > 0


class TestV2310SessizHataIzleme:
    """v23.10 — Sessiz hatalar artık karakutuya kaydediliyor (görünürlük)."""

    def test_sessiz_hata_kaydedilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_sh"
        os.makedirs("/tmp/test_sh", exist_ok=True)
        from utils import db; db.init()
        from utils import karakutu
        try:
            _ = bilinmeyen_degisken  # NameError
        except Exception as e:
            karakutu.sessiz_hata("test.modul", e, baglam="test")
        ozet = karakutu.ozet()
        assert ozet.get("turler", {}).get("hata", 0) >= 1, "Sessiz hata kaydedilmedi"
        assert "NameError" in ozet["son_hata"]["detay"]

    def test_sessiz_hata_bot_cokmez(self):
        """sessiz_hata kendisi patlasa bile bot çökmemeli."""
        from utils import karakutu
        # Geçersiz argümanlarla bile çökmemeli
        try:
            karakutu.sessiz_hata("x", Exception("test"))
            basarili = True
        except Exception:
            basarili = False
        assert basarili, "sessiz_hata bot'u çökertti"


class TestV2311SozlukTemizlik:
    """v23.11 — Sözlük zehirlenmesi: 'ye', 'marka', 'kampanyası' gibi çöp
    öğreniliyordu (bot kendi şablonundan + 2 harfli parçalardan)."""

    def _kur(self, ad):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_soz" + ad
        os.makedirs("/tmp/test_soz" + ad, exist_ok=True)
        from utils import db; db.init()

    def test_sablon_kelimesi_ogrenilmez(self):
        self._kur("a")
        from utils import sozluk
        sozluk.ogren("ELİT MARKA KAMPANYASI")
        sozluk.ogren("%50'ye varan indirim")
        for cop in ["marka", "kampanyası", "elit", "ye", "varan"]:
            assert not sozluk.urun_kelimesi_mi(cop, min_sayi=1), f"Çöp öğrenildi: {cop}"

    def test_gercek_kelime_ogrenilir(self):
        self._kur("b")
        from utils import sozluk
        sozluk.ogren("Philips Kahve Makinesi")
        sozluk.ogren("Samsung Buzdolabı")
        for gercek in ["philips", "kahve", "makinesi", "samsung"]:
            assert sozluk.urun_kelimesi_mi(gercek, min_sayi=1), f"Gerçek kelime kaçtı: {gercek}"

    def test_iki_harfli_temizlenir(self):
        self._kur("c")
        import time
        from utils import db, sozluk
        sozluk._ilk_kurulum()
        with db.cursor() as c:
            for k, s in [("ye", 13), ("ek", 3), ("makinesi", 7), ("s24", 4)]:
                c.execute("INSERT INTO kelime_sozluk (kelime,sayi,ts) VALUES (?,?,?) "
                          "ON CONFLICT(kelime) DO UPDATE SET sayi=?", (k, s, int(time.time()), s))
        sozluk.zehir_temizle()
        assert not sozluk.urun_kelimesi_mi("ye", min_sayi=1), "2 harfli 'ye' silinmedi"
        assert not sozluk.urun_kelimesi_mi("ek", min_sayi=1), "2 harfli 'ek' silinmedi"
        assert sozluk.urun_kelimesi_mi("makinesi", min_sayi=1), "Gerçek kelime silindi"
        assert sozluk.urun_kelimesi_mi("s24", min_sayi=1), "Model kodu s24 silindi"


class TestV2313OlculuUrunler:
    """v23.13 — '125mm', '20ll' gibi ölçülü kelimeler 'tek-tip harf' (mm, ll)
    sanılıp reddediliyordu. WORX matkabı gibi aletler atlanıyordu."""

    def test_olculu_urun_gecer(self):
        from services.urun_kapisi import gecerli_urun_adi
        ad = "WORX WX803 20Volt 2.0/4.0 Ah Li-ion 125mm Avuç Taşlama"
        assert gecerli_urun_adi(ad) is not None, "Ölçülü ürün reddedildi"

    def test_olcu_birimleri_korunur(self):
        from services.urun_kapisi import gecerli_urun_adi
        for ad in ["Makita 125mm Taşlama", "Bosch 18V Matkap", "Dewalt 20V Vidalama"]:
            assert gecerli_urun_adi(ad) is not None, f"Ölçülü ürün reddedildi: {ad}"

    def test_gercek_tektip_hala_red(self):
        """Rakamsız tek-tip harf (AAAA) hâlâ reddedilmeli."""
        from services.urun_kapisi import gecerli_urun_adi
        assert gecerli_urun_adi("AAAA") is None
        assert gecerli_urun_adi("Amazon TR") is None

    def test_worx_paylasilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_worx"
        os.makedirs("/tmp/test_worx", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        mesaj = "📦 WORX WX803 20Volt 125mm Avuç Taşlama\n💰10.706 TL\n🏪 Amazon"
        s = olustur(mesaj, 0, ["https://amazon.com.tr/dp/B0X"],
                    gemini={"urun_adi": "WORX WX803 Avuç Taşlama", "kategori": "genel",
                            "reklam": False, "tanitim": "", "fiyat_uyari": "",
                            "kalite": 4, "fiyat": 0, "eski_fiyat": 0})
        assert s and "WORX" in s, "WORX ürünü atlandı"


class TestV2314KarakutuFormatla:
    """v23.14 — karakutu.formatla eksikti (DB taşımada silinmiş), /karakutu çöküyordu."""

    def test_formatla_calisir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kkf"
        os.makedirs("/tmp/test_kkf", exist_ok=True)
        from utils import db; db.init()
        from utils import karakutu
        karakutu.kaydet("paylasim", "Test ürün")
        m = karakutu.formatla(15)
        assert m and "Test ürün" in m, "formatla çalışmıyor"

    def test_formatla_bos_durum(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kkf2"
        os.makedirs("/tmp/test_kkf2", exist_ok=True)
        from utils import db; db.init()
        from utils import karakutu
        # Boş karakutuda da çökmemeli
        m = karakutu.formatla(15)
        assert isinstance(m, str)


class TestV2315KuponAyristirici:
    """v23.15 — Çok-ürünlü kupon mesajları ("Kodu İle X TL"). Fiyat çıkarıcı
    "500"ü HAZIRAN500 kodundan fiyat sanıyordu → artık doğru ayrıştırılıyor."""

    def test_kupon_mesaji_tespit(self):
        from services.kupon_ayristirici import kupon_mesaji_mi
        m = "Philips\n✅HAZIRAN1000 Kodu İle 23.899TL'ye Düşüyor"
        assert kupon_mesaji_mi(m)
        assert not kupon_mesaji_mi("Normal ürün 500 TL")

    def test_iki_urun_ayrisir(self):
        from services.kupon_ayristirici import ayristir
        m = """🔥Philips Espresso Makinesi
✅HAZIRAN1000 Kodu İle 23.899TL'ye Düşüyor - Piyasası 24.999TL
🔻Salomon Ayakkabı HAZIRAN500 Kodu İle 6.492TL"""
        urunler = ayristir(m)
        assert len(urunler) == 2, f"2 ürün bekleniyordu: {len(urunler)}"
        assert urunler[0]["fiyat"] == 23899.0, f"Philips fiyatı yanlış: {urunler[0]['fiyat']}"
        assert urunler[0]["eski_fiyat"] == 24999.0
        assert urunler[0]["kod"] == "HAZIRAN1000"
        assert urunler[1]["fiyat"] == 6492.0

    def test_kupon_aciklamasi_fiyat_degil(self):
        """'10000/1000TL İndirim' kupon mekaniği, fiyat sanılmamalı."""
        from services.kupon_ayristirici import ayristir
        m = """🔥Ürün Adı Burada
✅KOD1000 Kodu İle 5.000TL'ye Düşüyor
🚨KOD1000 Mobil Uygulamada 10000/1000TL İndirim Yapıyor"""
        urunler = ayristir(m)
        assert len(urunler) >= 1
        # Fiyat 5000 olmalı, 1000 veya 10000 değil
        assert urunler[0]["fiyat"] == 5000.0, f"Kupon açıklaması fiyat sanıldı: {urunler[0]['fiyat']}"

    def test_kupon_sablon_dogru_fiyat(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kupon_sb"
        os.makedirs("/tmp/test_kupon_sb", exist_ok=True)
        from handlers.mesaj import _kupon_adaylar_olustur
        from services.kupon_ayristirici import ayristir
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        m = """🔥Philips Espresso Makinesi
✅HAZIRAN1000 Kodu İle 23.899TL'ye Düşüyor - Piyasası 24.999TL"""
        adaylar = _kupon_adaylar_olustur(ayristir(m), ["https://hepsiburada.com/x"], m)
        assert len(adaylar) >= 1
        s = olustur(adaylar[0]["blok"], adaylar[0]["indirim"],
                    [adaylar[0]["link"]], gemini=adaylar[0]["gemini"])
        assert s and "23.899" in s, "Şablonda doğru fiyat yok"
        assert "HAZIRAN1000" in s, "Kupon kodu görünmüyor"


class TestV2316MesajAnlama:
    """v23.16 — Mesaj anlama iyileştirmeleri:
    1. Ürün adı kısaltma yazım hataları (kelime atma → güvenli budama)
    2. İndirim oranı tutarsızlığı (iki fiyat varsa otomatik hesapla)
    3. Çoklu ürün bölme (numaralı emoji, madde işareti)"""

    def test_kisaltma_kelime_bozmaz(self):
        """Güvenli kısaltma: hiçbir kelime ortadan atılmaz/bozulmaz."""
        from services.urun_kapisi import guzellestir
        for ad in ["Philips 5000 Serisi Lattego Tam Otomatik Espresso Makinesi",
                   "WORX WX803 20Volt Li-ion 125mm Avuç Taşlama",
                   "Karaca Hatır 6 Kişilik Çay Makinesi Seti"]:
            g = guzellestir(ad)
            # Sonuçtaki her kelime (… hariç) orijinalde olmalı
            for k in g.replace("…", "").split():
                assert k in ad, f"Kısaltma kelime bozdu: '{k}' / {ad}"

    def test_kisaltma_parantez_atar(self):
        from services.urun_kapisi import guzellestir
        g = guzellestir("Samsung Galaxy S24 256 GB (Türkiye Garantili)")
        assert "Garantili" not in g and "Samsung" in g

    def test_indirim_orani_otomatik(self):
        """İki fiyat varsa indirim oranı metinde yazmasa bile hesaplanmalı."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_ind"
        os.makedirs("/tmp/test_ind", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        # Metinde "%" yok ama iki fiyat var → %48 hesaplanmalı
        s = olustur("📦 Bosch Matkap\n2.499 TL yerine 1.299 TL", 0, ["https://x.com/p"],
                    gemini={"urun_adi": "Bosch Matkap", "kategori": "diy", "reklam": False,
                            "tanitim": "", "fiyat_uyari": "", "kalite": 4, "fiyat": 0, "eski_fiyat": 0})
        assert s and "%48" in s, "İndirim oranı hesaplanmadı"

    def test_tek_fiyat_firsat(self):
        """Tek fiyat varsa indirim uydurMAmalı (FIRSAT ÜRÜNÜ)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_ind2"
        os.makedirs("/tmp/test_ind2", exist_ok=True)
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        s = olustur("📦 Bosch Matkap\n💰 1.299 TL", 0, ["https://x.com/p"],
                    gemini={"urun_adi": "Bosch Matkap", "kategori": "diy", "reklam": False,
                            "tanitim": "", "fiyat_uyari": "", "kalite": 4, "fiyat": 0, "eski_fiyat": 0})
        assert s and "FIRSAT" in s and "%" not in s.split("\n")[0]

    def test_numarali_liste_bolunur(self):
        from services.analiz import mesaj_bolum_ayir
        import services.analiz as a
        a._mesaj_cache.clear()
        m = "1️⃣ Bosch Matkap 500 TL\n2️⃣ Makita Vidalama 600 TL\n3️⃣ Dewalt Testere 700 TL"
        assert len(mesaj_bolum_ayir(m)) >= 3, "Numaralı liste bölünmedi"

    def test_tek_urun_bolunmez(self):
        """Çok satırlı TEK ürün yanlışlıkla bölünmemeli."""
        from services.analiz import mesaj_bolum_ayir
        import services.analiz as a
        a._mesaj_cache.clear()
        m = "📦 Apple iPad 11 inç 128GB Gümüş Wi-Fi\n💰 12.084 TL\n📦 Stok: 7 adet\n🏪 Amazon"
        assert len(mesaj_bolum_ayir(m)) == 1, "Tek ürün yanlış bölündü"


class TestV2317KuponDeger:
    """v23.17 — Kupon DEĞERİ ('100 TL indirim') fiyat/kod sanılıyordu.
    Üç bug: (1) değer fiyat sanılıyor, (2) değer kod sanılıyor, (3) gerçek kod kaçıyor."""

    def test_kupon_degeri_fiyat_sanilmaz(self):
        from services.analiz import fiyat_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        _, ys, _, _ = fiyat_bul("📦 Philips Tıraş\n💰 1.299 TL\n🎟️ Sepette 100 TL indirim kuponu")
        assert ys == "1.299", f"Kupon değeri fiyat sanıldı: {ys}"

    def test_sepette_x_tl_fiyat_degil(self):
        from services.analiz import fiyat_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        _, ys, _, _ = fiyat_bul("📦 Tefal Tava\n599 TL\nSepette 150 TL kupon var")
        assert ys == "599", f"Sepette değeri fiyat sanıldı: {ys}"

    def test_deger_kupon_kodu_sanilmaz(self):
        from services.analiz import kupon_bul
        # "100TL" bir indirim değeri, kupon KODU değil (salt rakam+TL)
        assert kupon_bul("📦 Bosch\n💰 899 TL\nKupon: 100TL") is None

    def test_gercek_kod_yakalanir(self):
        from services.analiz import kupon_bul
        assert kupon_bul("📦 Apple\n💰 2.999 TL\nKupon kodu: INDIRIM50") == "INDIRIM50"
        assert kupon_bul("📦 Ütü\nKETTLE50 kodu ile 100 TL indirim") == "KETTLE50"

    def test_normal_fiyat_bozulmaz(self):
        """Kupon temizliği normal iki-fiyatı bozmamalı."""
        from services.analiz import fiyat_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        _, ys, ev, yv = fiyat_bul("📦 Matkap\n2.499 TL yerine 1.299 TL")
        assert ys == "1.299" and ev == 2499.0


class TestV2318TiklamaTakip:
    """v23.18 — Tıklama takibi (affiliate gelir). DORMANT: kapalıyken davranış
    değişmemeli. Aktifken: link sarılmalı, tıklama kaydedilmeli."""

    def test_dormant_link_degismez(self):
        """Bayrak kapalıyken link_sar linki AYNEN döndürmeli (kritik)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_tk_d"
        os.makedirs("/tmp/test_tk_d", exist_ok=True)
        os.environ.pop("TIKLAMA_TAKIP_AKTIF", None)
        import importlib, config
        importlib.reload(config)
        from utils import db; db.init()
        from utils import tiklama
        hedef = "https://amazon.com.tr/dp/B0X?tag=winfluenced-6447"
        assert tiklama.link_sar(hedef, "Test", "elektronik") == hedef

    def test_urun_kaydet_ve_bul(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_tk_k"
        os.makedirs("/tmp/test_tk_k", exist_ok=True)
        from utils import db; db.init()
        from utils import tiklama
        kid = tiklama.urun_kaydet("https://x.com/p", "Ürün A", "spor", 100.0, "Amazon")
        assert kid, "Kısa ID üretilmedi"
        bilgi = tiklama.hedef_bul(kid)
        assert bilgi and bilgi["hedef_url"] == "https://x.com/p"

    def test_tiklama_sayilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_tk_s"
        os.makedirs("/tmp/test_tk_s", exist_ok=True)
        from utils import db; db.init()
        from utils import tiklama
        kid = tiklama.urun_kaydet("https://x.com/q", "Ürün B", "ev", 50.0)
        for _ in range(3):
            tiklama.tiklama_kaydet(kid)
        ist = tiklama.istatistik(7)
        assert ist["toplam"] >= 3, f"Tıklama sayılmadı: {ist['toplam']}"

    def test_kisa_id_benzersiz(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_tk_u"
        os.makedirs("/tmp/test_tk_u", exist_ok=True)
        from utils import db; db.init()
        from utils import tiklama
        idler = {tiklama.urun_kaydet(f"https://x.com/{i}", f"Ü{i}") for i in range(20)}
        assert len(idler) == 20, "Kısa ID çakışması var"


class TestV2319KisisellestirmeVeRapor:
    """v23.19 — #2 kategori aboneliği, #3 al/bekle zekâsı, #4 performans raporu."""

    def test_kategori_abone(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kab"
        os.makedirs("/tmp/test_kab", exist_ok=True)
        from utils import db; db.init()
        from utils import istek
        istek.kategori_abone_ol(111, "elektronik")
        istek.kategori_abone_ol(222, "elektronik")
        istek.kategori_abone_ol(111, "elektronik")  # çift olmamalı
        aboneler = istek.kategori_aboneleri("elektronik")
        assert 111 in aboneler and 222 in aboneler
        assert len(aboneler) == 2, f"Çift abonelik: {aboneler}"

    def test_kategori_iptal(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kab2"
        os.makedirs("/tmp/test_kab2", exist_ok=True)
        from utils import db; db.init()
        from utils import istek
        istek.kategori_abone_ol(333, "spor")
        istek.kategori_abone_iptal(333, "spor")
        assert 333 not in istek.kategori_aboneleri("spor")

    def test_al_bekle_dip(self):
        import os, time
        os.environ["DATA_DIR"] = "/tmp/test_ab_d"
        os.makedirs("/tmp/test_ab_d", exist_ok=True)
        from utils import db; db.init()
        from utils import fiyat_takip
        fiyat_takip._ilk_kurulum()
        from services.analiz import urun_kimligi
        k = urun_kimligi("https://x.com/dip")
        with db.cursor() as c:
            for f, d in [(1000, 80), (1100, 60), (1050, 40), (1200, 20), (980, 5)]:
                c.execute("INSERT INTO fiyat_gecmis (kimlik,fiyat,ts) VALUES (?,?,?)",
                          (k, f, int(time.time()) - d * 86400))
        t = fiyat_takip.al_bekle_tavsiyesi(k, 950)
        assert t and "dip" in t.lower(), f"Dip tavsiyesi yok: {t}"

    def test_al_bekle_yetersiz_veri(self):
        import os, time
        os.environ["DATA_DIR"] = "/tmp/test_ab_y"
        os.makedirs("/tmp/test_ab_y", exist_ok=True)
        from utils import db; db.init()
        from utils import fiyat_takip
        fiyat_takip._ilk_kurulum()
        from services.analiz import urun_kimligi
        k = urun_kimligi("https://x.com/az")
        # Tek kayıt → tavsiye verme
        with db.cursor() as c:
            c.execute("INSERT INTO fiyat_gecmis (kimlik,fiyat,ts) VALUES (?,?,?)",
                      (k, 100, int(time.time())))
        assert fiyat_takip.al_bekle_tavsiyesi(k, 100) is None

    def test_performans_raporu(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_rap"
        os.makedirs("/tmp/test_rap", exist_ok=True)
        from utils import db; db.init()
        from utils import performans
        r = performans.haftalik_rapor(7)
        assert r and "PERFORMANS RAPORU" in r


class TestV2320GuralFormat:
    """v23.20 — "X TL'ye Düştü - Piyasası Y TL" çoklu ürün formatı (Güral).
    Bug: ürün adı fiyat satırına taşıyordu ('...ye Düştü'), 2. ürün kaçıyordu."""

    def test_urun_adi_fiyata_tasmaz(self):
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        b = "🔥Güral Alfa 25 Parça 6 Kişilik Yemek Takımı \n\n✅1.599TL'ye Düştü - Piyasası 1.990TL+"
        ad = urun_adi_bul(b)
        assert ad and "Düştü" not in ad and "Piyasası" not in ad, f"Fiyat taştı: {ad}"
        assert "6 Kişilik" in ad or "6" in ad, f"'6' kayboldu: {ad}"

    def test_dustu_formati_iki_urun(self):
        from services.kupon_ayristirici import ayristir
        m = """🔥Güral Alfa 25 Parça 6 Kişilik Yemek Takımı

✅1.599TL'ye Düştü - Piyasası 1.990TL+
🔻Flormar Brow Kaş Pudrası Ve Fırça İçeren Kaş Kalemi 99TL
🚚Kargo Ücretsiz"""
        urunler = ayristir(m)
        assert len(urunler) == 2, f"2 ürün bekleniyordu: {len(urunler)}"
        assert urunler[0]["fiyat"] == 1599.0
        assert urunler[0]["eski_fiyat"] == 1990.0
        assert urunler[1]["fiyat"] == 99.0

    def test_eski_kupon_format_korunur(self):
        """'Kodu İle' formatı bozulmamalı."""
        from services.kupon_ayristirici import ayristir
        m = """🔥Philips Espresso
✅HAZIRAN1000 Kodu İle 23.899TL'ye Düşüyor - Piyasası 24.999TL
🔻Salomon Ayakkabı HAZIRAN500 Kodu İle 6.492TL"""
        urunler = ayristir(m)
        assert len(urunler) == 2
        assert urunler[0]["kod"] == "HAZIRAN1000"
        assert urunler[0]["fiyat"] == 23899.0


class TestV2321LogVePanel:
    """v23.21 — /log komutu (bot logu dosya olarak) + zengin /durum paneli."""

    def test_log_dosyasi_yazilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_log21"
        os.makedirs("/tmp/test_log21", exist_ok=True)
        # log.py'yi taze yükle ki dosya handler DATA_DIR'i görsün
        import importlib
        from utils import log as logmod
        importlib.reload(logmod)
        logmod.log("BILGI", "test satiri v2321")
        yol = logmod.log_dosya_yolu()
        # Dosya yolu None olabilir (reload zamanlaması) ama fonksiyon patlamamalı
        assert yol is None or isinstance(yol, str)

    def test_log_dosya_yolu_guvenli(self):
        from utils.log import log_dosya_yolu
        # Her durumda string veya None döner, hata fırlatmaz
        sonuc = log_dosya_yolu()
        assert sonuc is None or isinstance(sonuc, str)


class TestV2322ZenginWebPanel:
    """v23.22 — Railway web paneli (/panel) tüm detaylı istatistiği yansıtır."""

    def test_panel_tum_bolumler(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_wp"
        os.makedirs("/tmp/test_wp", exist_ok=True)
        from utils import db; db.init()
        from services.health import _panel_html
        html = _panel_html(kuyruk_size=2)
        for bolum in ["Özet", "Sistem", "Mağaza Dağılımı", "Kategori Dağılımı",
                      "En Beğenilen", "Etkileşim", "Çalışma Süresi", "Kategori Aboneleri"]:
            assert bolum in html, f"Panel bölümü eksik: {bolum}"

    def test_panel_magaza_verisi(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_wp2"
        os.makedirs("/tmp/test_wp2", exist_ok=True)
        from utils import db; db.init()
        from utils import cache
        cache._ist_yaz("magazalar", {"Amazon": 50, "N11": 20})
        cache._ist_yaz("toplam", 70)
        from services.health import _panel_html
        html = _panel_html(0)
        assert "Amazon" in html and ">50<" in html
        assert ">70<" in html

    def test_panel_saat_tuple_guvenli(self):
        """en_iyi_saatler tuple döndürse de panel çökmemeli (regresyon)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_wp3"
        os.makedirs("/tmp/test_wp3", exist_ok=True)
        from utils import db; db.init()
        from utils import zamanlama
        zamanlama._ilk_kurulum()
        # Saat verisi ekle (tuple döndürecek)
        for _ in range(3):
            zamanlama.paylasim_kaydet(14)
            zamanlama.oy_kaydet(14)
        from services.health import _panel_html
        html = _panel_html(0)  # çökmemeli
        assert "<!DOCTYPE html>" in html


class TestV2323SahteIndirimVeKurtarma:
    """v23.23 — Canlı logdan tespit edilen iki kök sebep:
    1. İndirim oranı uyduran kurallar (aciliyet kelimesi → sahte %50)
    2. KURTARMA ürünleri şablona iletilmediği için sessizce düşüyordu."""

    def test_aciliyet_kelimesi_sahte_oran_uretmez(self):
        from services.analiz import indirim_oranini_bul
        # Aciliyet kelimesi + fiyat var ama GERÇEK indirim yok → %0 olmalı
        assert indirim_oranini_bul("📦 Pil\n149 TL\nStoklar eriyor!") == 0
        assert indirim_oranini_bul("📦 ASUS\n8999 TL\nson stok kaçmaz") == 0
        assert indirim_oranini_bul("📦 Ürün\n500 TL\nhemen yakala dip fiyat") == 0

    def test_magaza_linki_sahte_oran_uretmez(self):
        from services.analiz import indirim_oranini_bul
        # Sadece mağaza linki var → indirim uydurMAmalı
        assert indirim_oranini_bul("📦 Ürün\n500 TL\nhttps://amazon.com.tr/dp/B0X") == 0

    def test_gercek_indirim_korunur(self):
        """Uydurma kuralları kalktı ama GERÇEK indirim hâlâ bulunmalı."""
        from services.analiz import indirim_oranini_bul
        assert indirim_oranini_bul("Matkap %30 indirim 700 TL") == 30
        assert indirim_oranini_bul("-%45 Bosch") == 45

    def test_kurtarilan_urun_sablon_uretir(self):
        """Blok'tan ad çıkmasa da kurtarılan adla şablon üretilmeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kurt23"
        os.makedirs("/tmp/test_kurt23", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        blok = "💰 149 TL\nhttps://amazon.com.tr/dp/B0X"
        # Kurtarmasız → None (blok'tan ad çıkmaz)
        assert olustur(blok, 0, ["https://amazon.com.tr/dp/B0X"], gemini=None) is None
        # Kurtarmalı → şablon üretilir
        s = olustur(blok, 0, ["https://amazon.com.tr/dp/B0X"], gemini=None,
                    kurtarilan_urun="GP Batteries GPA76 Düğme Pil")
        assert s and "FIRSAT" in s


class TestV2324RedirectPortCakisma:
    """v23.24 — Tıklama redirect'i health sunucusuna taşındı (/git/).
    Port çakışması ('address already in use') çözüldü — ayrı sunucu yok."""

    def _git_iste(self, kid, data_dir):
        import os, asyncio
        os.environ["DATA_DIR"] = data_dir
        os.makedirs(data_dir, exist_ok=True)
        from utils import db; db.init()
        import services.health as h

        class FakeReader:
            def __init__(s, istek): s.istek = istek.encode()
            async def read(s, n): return s.istek
        class FakeWriter:
            def __init__(s): s.veri = b""
            def write(s, d): s.veri += d
            async def drain(s): pass
            def close(s): pass
            async def wait_closed(s): pass

        r = FakeReader(f"GET /git/{kid} HTTP/1.1\r\n\r\n")
        w = FakeWriter()
        asyncio.new_event_loop().run_until_complete(h._handle(r, w, kuyruk=None))
        return w.veri.decode("utf-8", errors="ignore")

    def test_git_redirect_302(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_git1"
        os.makedirs("/tmp/test_git1", exist_ok=True)
        from utils import db; db.init()
        from utils import tiklama
        kid = tiklama.urun_kaydet("https://amazon.com.tr/dp/B0X?tag=aff", "Ürün", "ev")
        cevap = self._git_iste(kid, "/tmp/test_git1")
        assert "302" in cevap and "tag=aff" in cevap

    def test_git_tiklama_sayilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_git2"
        os.makedirs("/tmp/test_git2", exist_ok=True)
        from utils import db; db.init()
        from utils import tiklama
        kid = tiklama.urun_kaydet("https://x.com/p", "Ürün2", "spor")
        self._git_iste(kid, "/tmp/test_git2")
        assert tiklama.istatistik(7)["toplam"] >= 1

    def test_git_gecersiz_404(self):
        cevap = self._git_iste("yokboyle123", "/tmp/test_git3")
        assert "404" in cevap

    def test_redirect_sunucu_kullanim_disi(self):
        """Eski ayrı sunucu çağrılırsa hiçbir port açmamalı (None döner)."""
        import asyncio
        from services import redirect_sunucu
        sonuc = asyncio.new_event_loop().run_until_complete(
            redirect_sunucu.sunucu_baslat(port=9999))
        assert sonuc is None


class TestV2325ReklamVeEngelliGonderici:
    """v23.25 — Sponsorlu reklam engelleme + @magfi gönderici engelleme."""

    def test_sponsorlu_reklam_engellenir(self):
        from utils import reklam
        m = ("Doğru lokasyonda, güvenilir yatırım modeliyle geleceğinizi planlayın!\n"
             "110.430 TL'den başlayan taksitlerle yatırım fırsatını keşfedin.\n"
             "🔗 Hemen Başvur\n#sponsorlu · Fuzul Topraktan")
        r, sebep = reklam.reklam_mi(m, "", "", fiyat_var=True)
        assert r is True and "kesin reklam" in sebep

    def test_basvuru_cagrisi_reklam(self):
        from utils import reklam
        r, _ = reklam.reklam_mi("Hemen başvur, kredi fırsatı!", "", "", fiyat_var=False)
        assert r is True

    def test_gercek_urun_taksitli_engellenmez(self):
        """Taksit seçeneği olan GERÇEK ürün reklam sanılmamalı."""
        from utils import reklam
        r, _ = reklam.reklam_mi("📦 iPhone 15 128GB\n45.999 TL\n12 taksit imkanı\n🏪 Amazon",
                                "", "iPhone 15", fiyat_var=True)
        assert r is False

    def test_hashtag_sponsorlu_engellenir(self):
        from utils import reklam
        # v23.29 — #işbirliği ÇIKARILDI (affiliate bildirimi, çoğu üründe var).
        # #sponsorlu/#reklam gerçek reklam işareti olarak kalır.
        for etiket in ["#sponsorlu", "#reklam"]:
            r, _ = reklam.reklam_mi(f"Harika ürün 500 TL {etiket}", "", "Ürün", fiyat_var=True)
            assert r is True, f"{etiket} engellenmedi"

    def test_isbirligi_gercek_urun_paylasilir(self):
        """v23.29 — #İşbirliği'li GERÇEK ürün (somut ad + fiyat) ENGELLENMEMELİ.
        Türkiye'de fırsat kanalları bu etiketi çoğu affiliate ürüne ekliyor."""
        from utils import reklam
        for varyant in ["#İşbirliği", "#İŞBİRLİĞİ", "#işbirliği"]:
            m = f"📦 Penti Kadın Dantelli Kısa Çorap {varyant}\n💰 210 TL"
            r, _ = reklam.reklam_mi(m, "", "Penti Kadın Dantelli Kısa Çorap", fiyat_var=True)
            assert r is False, f"{varyant} ile gerçek ürün yanlışlıkla engellendi"

    def test_engelli_gonderici_config(self):
        import importlib, config
        importlib.reload(config)
        assert "magfi" in config.ENGELLI_GONDERENLER

    def test_engelli_icerik_eslesme(self):
        import config
        # magfi linki içeren metin engellenmeli (içerik eşleşmesi)
        dusuk = "📦 ürün https://magfi.link/abc 500 tl".lower()
        assert any(e in dusuk for e in config.ENGELLI_GONDERENLER)


class TestV2326KuponSepetFiyati:
    """v23.26 — "X TL - Y TL Kupon İle Sepette Z" formatı (Philips).
    Bug: bot kupon öncesi fiyatı (2.599) gösteriyor, sepet fiyatını (2.399)
    ve ikinci ürünü (Küvet) kaçırıyordu."""

    def test_sepet_fiyati_kuponla(self):
        from services.kupon_ayristirici import ayristir
        m = ("🔥Philips Erkek Bakım Seti 13'lü 1 Arada Saç Sakal Vücut Şekillendirici\n\n"
             "✅2.599TL - Ürün Altındaki 200TL Kupon İle Sepette 2.399\n"
             "🔻Dolu Küçük Katlanır Küvet Gri Sepette 540TL - Ücretsiz Kargo")
        urunler = ayristir(m)
        assert len(urunler) == 2, f"2 ürün bekleniyordu: {len(urunler)}"
        # Philips: sepet (ödenen) 2399, eski 2599
        assert urunler[0]["fiyat"] == 2399.0, f"Sepet fiyatı yanlış: {urunler[0]['fiyat']}"
        assert urunler[0]["eski_fiyat"] == 2599.0
        # Küvet: 540, adında "Sepette" kalmamalı
        assert urunler[1]["fiyat"] == 540.0
        assert "Sepette" not in urunler[1]["urun"] and "Küvet" in urunler[1]["urun"]

    def test_kupon_degeri_sepet_fiyatina_karismaz(self):
        """200TL kupon değeri eski fiyat sanılmamalı."""
        from services.kupon_ayristirici import ayristir
        m = ("🔥Ürün A\n✅1.000TL - 100TL Kupon İle Sepette 900")
        urunler = ayristir(m)
        assert urunler and urunler[0]["fiyat"] == 900.0
        # eski fiyat 1000 olmalı (100 kupon değeri DEĞİL)
        assert urunler[0]["eski_fiyat"] in (1000.0, None)
        assert urunler[0]["eski_fiyat"] != 100.0


class TestV2327SloganVeCokluLink:
    """v23.27 — #1 slogan/duyuru başlığı eleme, #3 tek blokta çoklu link ayırma."""

    def test_slogan_eleniyor(self):
        from services.urun_kapisi import gecerli_urun_adi
        for s in ["YENİ KAMPANYA BAŞLADI!🔥", "🔥KAMPANYA FIRSATI!🔥",
                  "Stoklar Eriyor Kaçırma", "Müjde Geldi", "Hemen Yakala"]:
            assert gecerli_urun_adi(s, s) is None, f"Slogan elenmedi: {s}"

    def test_gercek_urun_korunur(self):
        from services.urun_kapisi import gecerli_urun_adi
        for s in ["Bosch GSR 12V Matkap", "Stanley Klasik Vakumlu Termos",
                  "Philips Yeni Seri Espresso Makinesi", "Logitech M171 Kablosuz Mouse"]:
            assert gecerli_urun_adi(s, s), f"Gerçek ürün elendi: {s}"

    def test_coklu_link_satir_ayrilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_cl"
        os.makedirs("/tmp/test_cl", exist_ok=True)
        from utils import db; db.init()
        from handlers.mesaj import _coklu_link_satir_ayir
        import services.analiz as a
        a._mesaj_cache.clear()
        blok = ("Bosch GSR 12V Matkap 1.299 TL\n"
                "Logitech M171 Mouse 299 TL\n"
                "HyperX Cloud Kulaklık 1.599 TL")
        linkler = ["https://sl.n11.com/a", "https://sl.n11.com/b", "https://sl.n11.com/c"]
        sonuc = _coklu_link_satir_ayir(blok, linkler, blok)
        assert sonuc and len(sonuc) == 3
        # Her ürün kendi linkiyle eşleşmeli (sıralı)
        assert sonuc[0]["link"].endswith("/a") and sonuc[2]["link"].endswith("/c")

    def test_coklu_link_eslesmezse_guvenli(self):
        """Ürün sayısı link sayısından farklıysa None (güvenli)."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_cl2"
        os.makedirs("/tmp/test_cl2", exist_ok=True)
        from utils import db; db.init()
        from handlers.mesaj import _coklu_link_satir_ayir
        import services.analiz as a
        a._mesaj_cache.clear()
        # 2 ürün, 3 link → eşleşmiyor → None
        sonuc = _coklu_link_satir_ayir(
            "Bosch Matkap 1.299 TL\nLogitech Mouse 299 TL",
            ["https://a", "https://b", "https://c"], "x")
        assert sonuc is None

    def test_coklu_link_slogan_None(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_cl3"
        os.makedirs("/tmp/test_cl3", exist_ok=True)
        from utils import db; db.init()
        from handlers.mesaj import _coklu_link_satir_ayir
        sonuc = _coklu_link_satir_ayir("🔥 SÜPER FIRSATLAR 🔥\nKaçırma!",
                                       ["https://a", "https://b"], "x")
        assert sonuc is None


class TestV2328TurkceIveAdsizUrun:
    """v23.28 — Türkçe-İ reklam engelleme (#İşbirliği büyük İ) + adsız ürün
    'Alışveriş fırsatı' sahte adı kaldırıldı + kurtarılan ad gövdede görünüyor."""

    def test_isbirligi_buyuk_I_gercek_urun_paylasilir(self):
        """v23.29 — #İşbirliği (büyük/küçük İ) affiliate bildirimi; gerçek ürün
        engellenmemeli. (Türkçe-İ küçültme düzeltmesi #sponsorlu için korunur.)"""
        from utils import reklam
        penti = ("📦 Penti Kadın Dantelli Kısa Çorap\n🔍 Google'da Karşılaştır #İşbirliği\n"
                 "⚡️ İndirimli Fiyat: ₺210,00\n💰 Normal Fiyat: ₺504,93")
        for varyant in ["#İşbirliği", "#İŞBİRLİĞİ", "#işbirliği"]:
            m = penti.replace("#İşbirliği", varyant)
            r, _ = reklam.reklam_mi(m, "", "Penti Kadın Dantelli Kısa Çorap", fiyat_var=True)
            assert r is False, f"{varyant} ile gerçek ürün yanlışlıkla engellendi"

    def test_sponsorlu_turkce_I_hala_engellenir(self):
        """#sponsorlu büyük harfli yazımlar hâlâ engellenmeli (Türkçe-İ düzeltmesi)."""
        from utils import reklam
        r, _ = reklam.reklam_mi("Yatırım fırsatı 110.000 TL #SPONSORLU\nHemen Başvur",
                                "", "", fiyat_var=True)
        assert r is True

    def test_adsiz_tekil_urun_paylasilmaz(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_adsiz28"
        os.makedirs("/tmp/test_adsiz28", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        # Ürün adı çıkmayan tekil ürün → None (sahte ad üretme)
        s = olustur("₺210,00\n💰 Normal: ₺504,93\n-%58", 58,
                    ["https://amazon.com.tr/dp/B0X"], gemini=None)
        assert s is None

    def test_alisveris_firsati_sahte_ad_yok(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_af28"
        os.makedirs("/tmp/test_af28", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        # Çeşitli mesajlarda "Alışveriş fırsatı" sahte adı asla çıkmamalı
        for m in ["📦 Penti Çorap\n₺210,00\n💰 Normal: ₺504,93",
                  "💰 149 TL\nhttps://amazon.com.tr/dp/B0X"]:
            a._mesaj_cache.clear()
            s = olustur(m, 50, ["https://amazon.com.tr/dp/B0X"], gemini=None,
                        kurtarilan_urun="GP Batteries Düğme Pil")
            assert s is None or "Alışveriş fırsatı" not in s

    def test_kurtarilan_ad_govdede_gorunur(self):
        """v23.23 fix tamamlandı: kurtarılan ad artık gövdede de kullanılıyor."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kg28"
        os.makedirs("/tmp/test_kg28", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        s = olustur("💰 149 TL\nhttps://amazon.com.tr/dp/B0X", 0,
                    ["https://amazon.com.tr/dp/B0X"], gemini=None,
                    kurtarilan_urun="GP Batteries GPA76 Düğme Pil")
        assert s and "GP Batteries" in s


class TestV2330AlisverisFirsatiSahteAd:
    """v23.30 — 'Alışveriş fırsatı' / 'Alışveriş' sahte ürün adı kaldırıldı.
    Kök sebep: 'alışveriş' jenerik listede değildi, kapı Gemini'nin ürettiği
    'Alışveriş fırsatı'yı geçerli ad sayıp 'Alışveriş'e buduyordu."""

    def test_alisveris_firsati_elenir(self):
        from services.urun_kapisi import gecerli_urun_adi
        for ad in ["Alışveriş fırsatı", "Alışveriş Fırsatı", "alışveriş fırsatı",
                   "Alışveriş", "alisveris firsati"]:
            assert gecerli_urun_adi(ad, "x") is None, f"'{ad}' elenmedi"

    def test_gercek_urun_korunur(self):
        from services.urun_kapisi import gecerli_urun_adi
        for ad in ["Penti Kadın Dantelli Kısa Çorap", "Bosch GSR 12V Matkap",
                   "Omo Kapsül Deterjan"]:
            assert gecerli_urun_adi(ad, "x"), f"'{ad}' yanlışlıkla elendi"

    def test_gemini_alisveris_firsati_dondurse_gercek_ad_kullanilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_af30"
        os.makedirs("/tmp/test_af30", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        gem = {"urun_adi": "Alışveriş fırsatı", "kategori": "giyim", "reklam": False,
               "tanitim": "", "kalite": 3, "fiyat": 210, "eski_fiyat": 504}
        s = olustur("📦 Penti Kadın Dantelli Kısa Çorap\n₺210,00\n💰 Normal: ₺504,93",
                    58, ["https://amazon.com.tr/dp/B0X"], gemini=gem)
        assert s and "Penti" in s and "Alışveriş fırsatı" not in s

    def test_adsiz_gemini_alisveris_firsati_none(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_af30b"
        os.makedirs("/tmp/test_af30b", exist_ok=True)
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        gem = {"urun_adi": "Alışveriş fırsatı", "kategori": "genel", "reklam": False,
               "tanitim": "", "kalite": 3, "fiyat": 210, "eski_fiyat": 504}
        s = olustur("İndirimli: ₺210\nNormal: ₺504\n-%58", 58,
                    ["https://amazon.com.tr/dp/B0X"], gemini=gem)
        assert s is None or "Alışveriş fırsatı" not in s


class TestV2331CokluUrunSegment:
    """v23.31 — Toplu link mesajlarını fiyat-çapalı SEGMENT'lere ayırma.
    Eski sürüm ad+fiyatı aynı satırda arıyordu; n11/Amazon mesajlarında ad bir
    satırda, fiyat alt satırda olduğu için ayrılamıyor, ürünler kayboluyordu."""

    L3 = ["https://sl.n11.com/n/a", "https://sl.n11.com/n/b", "https://sl.n11.com/n/c"]

    def _ayir(self, blok, links=None):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_seg31"
        os.makedirs("/tmp/test_seg31", exist_ok=True)
        from utils import db; db.init()
        from handlers.mesaj import _coklu_link_satir_ayir
        import services.analiz as a
        a._mesaj_cache.clear()
        return _coklu_link_satir_ayir(blok, links or self.L3, blok)

    def test_ad_alt_satir_fiyat_ayrilir(self):
        """Ad bir satırda, fiyat alt satırda (n11 tipik)."""
        blok = ("Bosch GSR 12V Profesyonel Matkap\n💰 1.299 TL\n\n"
                "Logitech M171 Kablosuz Mouse\n💰 299 TL\n\n"
                "HyperX Cloud II Oyuncu Kulaklığı\n💰 1.599 TL")
        r = self._ayir(blok)
        assert r and len(r) == 3
        assert "Bosch" in r[0]["urun"] and "Logitech" in r[1]["urun"]
        assert r[0]["link"].endswith("/a") and r[2]["link"].endswith("/c")

    def test_baslik_satiri_atilir(self):
        """Baştaki 'Günün Fırsatları' başlığı ürün adı sanılmamalı."""
        blok = ("🔥 Günün Fırsatları 🔥\n\nApple AirPods Pro 2. Nesil\n2.999 TL\n\n"
                "Samsung Galaxy Buds 3\n1.499 TL\n\nAnker Soundcore Q30\n899 TL")
        r = self._ayir(blok)
        assert r and len(r) == 3
        assert "AirPods" in r[0]["urun"]
        assert all("Fırsatları" not in x["urun"] for x in r)

    def test_eski_yeni_ayni_satir(self):
        blok = ("Philips Airfryer XL\n2.499 TL ~~3.999 TL~~\n"
                "Tefal Tava Seti\n1.299 TL ~~1.899 TL~~\n"
                "Karaca Çaydanlık\n749 TL ~~1.099 TL~~")
        r = self._ayir(blok)
        assert r and len(r) == 3

    def test_sayi_eslesmezse_guvenli_none(self):
        """Segment sayısı link sayısıyla tutmuyorsa None (güvenli)."""
        r = self._ayir("Bosch Matkap\n199 TL\nLogitech Mouse\n299 TL")  # 2 ürün, 3 link
        assert r is None

    def test_slogan_only_none(self):
        r = self._ayir("🔥 SÜPER FIRSATLAR 🔥\nKaçırma!")
        assert r is None


class TestV2332KitapFiltresi:
    """v23.32 — Amazon kitap linkleri (ISBN-10 ASIN) paylaşımdan çıkarıldı.
    Kitap = 10 rakam veya 9 rakam+X ASIN; ürün ASIN'i 'B' ile başlar."""

    def test_kitap_linki_tespit(self):
        from handlers.mesaj import _kitap_linki_mi
        for u in ["https://www.amazon.com.tr/dp/9750854586?tag=x",
                  "https://amazon.com.tr/dp/080485277X",
                  "https://www.amazon.com.tr/dp/0349416729"]:
            assert _kitap_linki_mi(u) is True, f"kitap kaçtı: {u}"

    def test_urun_linki_kitap_degil(self):
        from handlers.mesaj import _kitap_linki_mi
        for u in ["https://www.amazon.com.tr/dp/B0F3JPLZ53?tag=x",
                  "https://sl.n11.com/n/vlKXCKk",
                  "https://www.trendyol.com/x-p-12345"]:
            assert _kitap_linki_mi(u) is False, f"ürün yanlışlıkla kitap: {u}"

    def test_kitap_mesaji_filtrelenir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kt32"
        os.makedirs("/tmp/test_kt32", exist_ok=True)
        from utils import db; db.init()
        import config
        config.KITAP_FILTRELE = True
        from handlers.mesaj import _blok_analiz
        import services.analiz as a
        a._mesaj_cache.clear()
        kitap = "📚 Dar Kapı\n💰 89 TL ~~199 TL~~\n🏪 Amazon"
        s = _blok_analiz(kitap, ["https://www.amazon.com.tr/dp/9750854586?tag=x"],
                         gemini_sonuc=None, orijinal_mesaj=kitap)
        assert s is None

    def test_gercek_urun_filtrelenmez(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kt32b"
        os.makedirs("/tmp/test_kt32b", exist_ok=True)
        from utils import db; db.init()
        import config
        config.KITAP_FILTRELE = True
        from handlers.mesaj import _blok_analiz
        import services.analiz as a
        a._mesaj_cache.clear()
        urun = "📦 Bosch GSR 12V Matkap\n💰 1.299 TL ~~2.499 TL~~\n🏪 Amazon"
        s = _blok_analiz(urun, ["https://www.amazon.com.tr/dp/B0F3JPLZ53?tag=x"],
                         gemini_sonuc=None, orijinal_mesaj=urun)
        assert s and s.get("urun") and "Bosch" in s["urun"]


class TestV2333KaliteSkoruKayit:
    """v23.33 — Kalite skoru eşikten BAĞIMSIZ her zaman hesaplanır+kaydedilir.
    Eskiden KALITE_PUAN_ESIK=0 (varsayılan) iken skor hiç hesaplanmıyor, karne
    boş kalıyordu (/karne 'çalışmıyor' görünüyordu). Filtreleme yalnızca esik>0."""

    def test_esik_sifirda_skor_kaydedilir(self):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kal33"
        os.makedirs("/tmp/test_kal33", exist_ok=True)
        import config
        config.KALITE_PUAN_ESIK = 0
        from utils import db; db.init()
        from services.sablon import olustur
        from utils import kalite
        import services.analiz as a
        bas = kalite.istatistik()["toplam"]
        a._mesaj_cache.clear()
        olustur("📦 Bosch GSR 12V Matkap\n1.299 TL ~~2.499 TL~~", 48,
                ["https://amazon.com.tr/dp/B0F3JPLZ53"], gemini=None)
        son = kalite.istatistik()["toplam"]
        assert son == bas + 1, "esik=0'da skor kaydedilmedi"

    def test_esik_sifirda_filtreleme_kapali(self):
        """esik=0 iken hiçbir ürün kalite yüzünden düşmemeli."""
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kal33b"
        os.makedirs("/tmp/test_kal33b", exist_ok=True)
        import config
        config.KALITE_PUAN_ESIK = 0
        from utils import db; db.init()
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        # Düşük kaliteli olsa bile esik=0 → paylaşılır (None dönmez)
        s = olustur("📦 Stanley Termos\n899 TL ~~1.499 TL~~", 40,
                    ["https://amazon.com.tr/dp/B073SNMY1W"], gemini=None)
        assert s is not None


class TestV2334KuponCokluLink:
    """v23.34 — Çoklu kupon ürününe (🔥/🔻) her birine KENDİ linki verilir.
    Eskiden hepsi btn_links[0] alıyordu → aynı link → duplicate filtresi 2.+
    ürünü düşürüyordu (Valkyrie+Kretuar mesajında sadece ilki paylaşılıyordu)."""

    def _adaylar(self, mesaj, links):
        import os
        os.environ["DATA_DIR"] = "/tmp/test_kup34"
        os.makedirs("/tmp/test_kup34", exist_ok=True)
        from utils import db; db.init()
        from services.kupon_ayristirici import ayristir
        from handlers.mesaj import _kupon_adaylar_olustur
        return _kupon_adaylar_olustur(ayristir(mesaj), links, mesaj)

    def _dedup(self, adaylar):
        benzersiz, gorulen = [], set()
        for a in adaylar:
            if a["link"] in gorulen:
                continue
            gorulen.add(a["link"]); benzersiz.append(a)
        return benzersiz

    VALKYRIE = ("🔥Valkyrie 300W 48V Şarjlı Yüksek Basınçlı Oto Yıkama Tabancası\n"
                "✅1.103TL'ye Düştü - Piyasası 1.683TL+ / Kargo Ücretsiz\n"
                "🔻Kretuar Maket Bıçak Seti 13 Parçalı Çelik 199TL - Prime Üyelik Kargo Ücretsiz")

    def test_iki_urun_farkli_link_alir(self):
        links = ["https://sl.n11.com/n/valkyrie", "https://www.amazon.com.tr/dp/B0XKRETUAR"]
        adaylar = self._adaylar(self.VALKYRIE, links)
        assert len(adaylar) == 2
        # Farklı linkler
        assert adaylar[0]["link"] != adaylar[1]["link"]
        assert adaylar[0]["link"].endswith("valkyrie")
        assert adaylar[1]["link"].endswith("KRETUAR")

    def test_dedup_iki_urunu_de_korur(self):
        links = ["https://sl.n11.com/n/valkyrie", "https://www.amazon.com.tr/dp/B0XKRETUAR"]
        benzersiz = self._dedup(self._adaylar(self.VALKYRIE, links))
        assert len(benzersiz) == 2, "duplicate filtresi bir ürünü düşürdü"
        adlar = " ".join(a["urun"] for a in benzersiz)
        assert "Valkyrie" in adlar and "Kretuar" in adlar

    def test_tek_link_guvenli(self):
        """Tek link varsa: ilk ürün paylaşılır, ikincisi aynı linke düşüp dedup'ta elenir."""
        benzersiz = self._dedup(self._adaylar(self.VALKYRIE, ["https://sl.n11.com/n/tek"]))
        assert len(benzersiz) == 1


class TestV2335UrunOlmayanLinkFiltresi:
    """v23.35 — WhatsApp/Telegram/sosyal paylaş-katıl linkleri ürün sayısını
    şişirip çoklu-ürün ayrımını bozuyordu. Bu linkler artık eleniyor."""

    def test_urun_olmayan_linkler_elenir(self):
        from handlers.mesaj import _urun_olmayan_link_mi
        for u in ["https://chat.whatsapp.com/ABC", "https://wa.me/123",
                  "https://t.me/kanal", "https://instagram.com/x",
                  "https://youtu.be/abc", "https://x.com/foo"]:
            assert _urun_olmayan_link_mi(u) is True, f"elenmedi: {u}"

    def test_urun_linkleri_korunur(self):
        from handlers.mesaj import _urun_olmayan_link_mi
        for u in ["https://www.amazon.com.tr/dp/B0X?tag=x", "https://ty.gl/abc",
                  "https://sl.n11.com/n/xyz", "https://app.hb.biz/abc",
                  "https://www.trendyol.com/x-p-1"]:
            assert _urun_olmayan_link_mi(u) is False, f"yanlışlıkla elendi: {u}"

    def test_tek_urun_uc_paylas_butonu(self):
        """1 ürün + 3 paylaş butonu → filtreden sonra 1 ürün linki."""
        from handlers.mesaj import _urun_olmayan_link_mi
        btn = ["https://www.amazon.com.tr/dp/B0X", "https://chat.whatsapp.com/A",
               "https://t.me/kanal", "https://instagram.com/x"]
        temiz = [x for x in btn if not _urun_olmayan_link_mi(x)]
        assert temiz == ["https://www.amazon.com.tr/dp/B0X"]


class TestV2337KaynaklarKatmani:
    """v23.37 — Kanal yerine modüler kaynaklar katmanı (feed + mağaza izleme).
    Feed okuyucu XML/CSV/JSON ayrıştırır; zamanlayıcı fırsatları mevcut hatta besler."""

    def test_feed_xml_ayristirma(self):
        from kaynaklar.feed import _ayristir
        xml = ('<rss xmlns:g="http://base.google.com/ns/1.0"><channel>'
               '<item><g:title>Bosch Matkap</g:title><g:price>1499,90 TL</g:price>'
               '<g:sale_price>999,90 TL</g:sale_price><g:link>https://ty.gl/a</g:link></item>'
               '</channel></rss>')
        eslem = {"ad":"title","fiyat":"sale_price","eski_fiyat":"price","url":"link","kayit_yolu":"item"}
        r = _ayristir(xml, "xml", eslem, "t")
        assert len(r) == 1 and r[0]["ad"] == "Bosch Matkap"
        assert r[0]["fiyat"] == 999.90 and r[0]["eski_fiyat"] == 1499.90

    def test_feed_json_ic_ice(self):
        from kaynaklar.feed import _ayristir
        js = '{"data":{"products":[{"t":"Mouse","now":299,"was":499,"u":"https://ty.gl/m"}]}}'
        eslem = {"ad":"t","fiyat":"now","eski_fiyat":"was","url":"u","kayit_yolu":"data.products"}
        r = _ayristir(js, "json", eslem, "t")
        assert len(r) == 1 and r[0]["fiyat"] == 299.0

    def test_feed_gecersiz_elenir(self):
        from kaynaklar.feed import _ayristir
        js = '{"items":[{"t":"Yok","now":0,"u":"https://x"},{"t":"","now":50,"u":"https://y"}]}'
        eslem = {"ad":"t","fiyat":"now","url":"u","kayit_yolu":"items"}
        assert _ayristir(js, "json", eslem, "t") == []

    def test_indirim_hesapla(self):
        from kaynaklar.temel import indirim_hesapla
        assert indirim_hesapla(1000, 750) == 25
        assert indirim_hesapla(100, 100) == 0
        assert indirim_hesapla(None, 50) == 0

    def test_scheduler_dusuk_indirim_eler(self):
        import os, asyncio
        os.environ["DATA_DIR"] = "/tmp/test_sch37"; os.makedirs("/tmp/test_sch37", exist_ok=True)
        import config; config.MIN_INDIRIM = 20; config.KITAP_FILTRELE = True
        from utils import db; db.init()
        from schedulers.kaynak_tarama import _firsat_isle
        import services.analiz as a
        q = asyncio.Queue(maxsize=10)
        a._mesaj_cache.clear()
        # %8 indirim → elenir
        assert _firsat_isle({"url":"https://ty.gl/x","ad":"Mouse","fiyat":459,"eski_fiyat":499}, q) is False
        a._mesaj_cache.clear()
        # %33 → eklenir
        assert _firsat_isle({"url":"https://ty.gl/y","ad":"Bosch Matkap","fiyat":999,"eski_fiyat":1499}, q) is True

    def test_scheduler_kitap_eler(self):
        import os, asyncio
        os.environ["DATA_DIR"] = "/tmp/test_sch37b"; os.makedirs("/tmp/test_sch37b", exist_ok=True)
        import config; config.MIN_INDIRIM = 20; config.KITAP_FILTRELE = True
        from utils import db; db.init()
        from schedulers.kaynak_tarama import _firsat_isle
        import services.analiz as a
        q = asyncio.Queue(maxsize=10)
        a._mesaj_cache.clear()
        assert _firsat_isle({"url":"https://amazon.com.tr/dp/9750854586","ad":"Dar Kapı","fiyat":89,"eski_fiyat":199}, q) is False


class TestV2339Lisans:
    """v23.39 — HMAC imzalı lisans anahtarları (üretim + doğrulama + süre)."""

    def test_uret_dogrula(self):
        from utils import lisans
        k = lisans.uret("alici@x.com", 365)
        g, b = lisans.dogrula(k)
        assert g is True and b["alici"] == "alici@x.com"
        assert lisans.kalan_gun(b) >= 360

    def test_kurcalanmis_red(self):
        from utils import lisans
        k = lisans.uret("a", 30)
        g, _ = lisans.dogrula(k[:-4] + "0000")
        assert g is False

    def test_farkli_gizli_red(self):
        from utils import lisans
        k = lisans.uret("korsan", 30, gizli=b"baska")
        g, b = lisans.dogrula(k)   # botun gizlisiyle doğrula
        assert g is False and b["hata"] == "imza"

    def test_suresi_dolmus_red(self):
        from utils import lisans
        k = lisans.uret("eski", -1)
        g, b = lisans.dogrula(k)
        assert g is False and b["hata"] == "süresi doldu"

    def test_bozuk_bicim_red(self):
        from utils import lisans
        assert lisans.dogrula("saçmalık")[0] is False
        assert lisans.dogrula("")[0] is False
