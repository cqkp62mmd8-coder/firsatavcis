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
