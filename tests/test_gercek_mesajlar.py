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
        for alt, ikon in [("telefon", "📱"), ("ayakkabi", "👟")]:
            ana = "giyim" if alt == "ayakkabi" else "elektronik"
            g = {"reklam": False, "urun_adi": "Test Ürün", "kategori": ana,
                 "alt_kategori": alt, "kalite": 3, "tanitim": "", "fiyat_uyari": "",
                 "fiyat": 0, "eski_fiyat": 0}
            s = olustur("Test Ürün 1000 TL", 20, ["https://trendyol.com/x-p-1"], gemini=g)
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
            "Apple markasında %20 kampanya",
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
