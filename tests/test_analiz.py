"""
services/analiz.py birim testleri.
Saf fonksiyonlar — dış bağımlılık yok, hızlı çalışır.
"""


# ── markdown_temizle ────────────────────────────────────────────

class TestMarkdownTemizle:
    def test_bold_temizleme(self):
        from services.analiz import markdown_temizle
        assert markdown_temizle("**kalın metin**") == "kalın metin"
        assert markdown_temizle("*italik*") == "italik"

    def test_kod_temizleme(self):
        from services.analiz import markdown_temizle
        assert markdown_temizle("`kod`") == "kod"

    def test_bos_metin(self):
        from services.analiz import markdown_temizle
        assert markdown_temizle("") == ""
        assert markdown_temizle(None) is None


# ── indirim_oranini_bul ─────────────────────────────────────────

class TestIndirimOranini:
    def test_yuzde_kalip(self):
        from services.analiz import indirim_oranini_bul
        assert indirim_oranini_bul("İndirim %57") == 57
        assert indirim_oranini_bul("-%30 indirim") == 30
        assert indirim_oranini_bul("60% off") == 60

    def test_kuponlu_format(self):
        from services.analiz import indirim_oranini_bul
        # 900₺ kupon + 15.099₺ → tasarruf 900, oran ~6
        sonuc = indirim_oranini_bul("Roborock 900₺ Kuponla 15.099₺")
        # KUPON_MIN_TL >= 500 olduğu için MIN_INDIRIM (20) garantisi var
        assert sonuc >= 20

    def test_sahte_yuzde_yok(self):
        from services.analiz import indirim_oranini_bul
        assert indirim_oranini_bul("Test ürün açıklaması") == 0

    def test_tum_aralik(self):
        from services.analiz import indirim_oranini_bul
        assert indirim_oranini_bul("%99 indirim") == 99
        assert indirim_oranini_bul("%1 indirim") == 1
        assert indirim_oranini_bul("%150 indirim") == 0    # geçersiz, alınmaz


# ── fiyat_bul ───────────────────────────────────────────────────

class TestFiyatBul:
    def test_etiketli_fiyat(self):
        from services.analiz import fiyat_bul
        m = "İndirimli Fiyat: 100 TL\nNormal Fiyat: 200 TL"
        eski_s, yeni_s, eski_v, yeni_v = fiyat_bul(m)
        assert eski_v == 200.0
        assert yeni_v == 100.0

    def test_tr_binlik_ayrac(self):
        from services.analiz import fiyat_bul, _parse
        # "1.499,00" Türkçe → 1499.00
        assert _parse("1.499,00") == 1499.0
        assert _parse("1.499") == 1499.0
        assert _parse("15.099") == 15099.0
        assert _parse("299,90") == 299.9

    def test_tek_fiyat(self):
        from services.analiz import fiyat_bul
        eski, yeni, ev, yv = fiyat_bul("Sadece 100 TL")
        assert yeni == "100"
        assert eski is None


# ── urun_adi_bul ────────────────────────────────────────────────

class TestUrunAdi:
    def test_temel(self):
        from services.analiz import urun_adi_bul
        sonuc = urun_adi_bul("📦 Jack & Jones Erkek Şort")
        assert "Jack & Jones" in sonuc

    def test_fiyat_ve_yuzde_temizleme(self):
        from services.analiz import urun_adi_bul
        sonuc = urun_adi_bul("🔥 Samsung 65 inç 4K TV 1499 TL %57 indirim")
        # Fiyat ve yüzde silinmiş olmalı
        assert "1499" not in sonuc
        assert "%57" not in sonuc
        assert "Samsung" in sonuc

    def test_hashtag_iceren_satir_atlanir(self):
        from services.analiz import urun_adi_bul
        sonuc = urun_adi_bul("🛍️ Hepsiburada #işbirliği")
        assert sonuc != "Hepsiburada"

    def test_etiket_satiri_atlanir(self):
        from services.analiz import urun_adi_bul
        # Sadece "İndirimli Fiyat:" satırı varsa ürün adı çıkarılamamalı
        assert urun_adi_bul("⚡️ İndirimli Fiyat:") is None
        assert urun_adi_bul("Stokta var") is None


# ── link_bul / link_temizle ─────────────────────────────────────

class TestLink:
    def test_buton_oncelikli(self):
        from services.analiz import link_bul
        sonuc = link_bul("metin", ["https://amzn.to/abc"])
        assert "amzn.to" in sonuc

    def test_t_me_reddedilir(self):
        from services.analiz import link_bul
        assert link_bul("metin", ["https://t.me/bot"]) is None

    def test_google_reddedilir(self):
        from services.analiz import link_bul
        assert link_bul("metin", ["https://google.com/search?q=x"]) is None

    def test_bilinen_magaza_oncelikli(self):
        from services.analiz import link_bul
        sonuc = link_bul("", [
            "https://example.com/abc",
            "https://trendyol.com/abc",
        ])
        assert "trendyol.com" in sonuc

    def test_temizle_amazon_affiliate(self):
        from services.analiz import link_temizle
        url = "https://amazon.com.tr/dp/B09?tag=aff-21&creative=x&utm_source=tg"
        sonuc = link_temizle(url)
        assert "tag=" not in sonuc
        assert "creative=" not in sonuc
        assert "utm_source=" not in sonuc
        assert "/dp/B09" in sonuc

    def test_kisaltilmis_link_dokunulmaz(self):
        from services.analiz import link_temizle
        url = "https://ty.gl/abc123?ref=tg"
        # Kısaltılmış linkler değiştirilmemeli
        assert link_temizle(url) == url


# ── magaza_bul ──────────────────────────────────────────────────

class TestMagaza:
    def test_metinden(self):
        from services.analiz import magaza_bul
        assert magaza_bul("Trendyol'da indirim") == "Trendyol"
        assert magaza_bul("Amazon TR fırsatı") == "Amazon TR"

    def test_linkten(self):
        from services.analiz import magaza_bul
        assert magaza_bul("", "https://amzn.to/x") == "Amazon TR"
        assert magaza_bul("", "https://ty.gl/x") == "Trendyol"
        assert magaza_bul("", "https://hb.biz/x") == "Hepsiburada"


# ── mesaj_bolum_ayir ────────────────────────────────────────────

class TestMesajBolum:
    def test_tek_urun(self):
        from services.analiz import mesaj_bolum_ayir
        m = "🔥 Tek ürün 100 TL yerine 50 TL %50 indirim"
        assert len(mesaj_bolum_ayir(m)) == 1

    def test_cok_urun(self):
        from services.analiz import mesaj_bolum_ayir
        m = """🔥 Ürün A 200 TL yerine 100 TL

🔥 Ürün B 400 TL yerine 200 TL"""
        bloklar = mesaj_bolum_ayir(m)
        assert len(bloklar) == 2

    def test_max_iki_blok(self):
        from services.analiz import mesaj_bolum_ayir
        m = """🔥 A 200 TL yerine 100 TL

🔥 B 400 TL yerine 200 TL

🔥 C 600 TL yerine 300 TL"""
        assert len(mesaj_bolum_ayir(m)) == 2

    def test_kisa_mesaj_bolunmez(self):
        from services.analiz import mesaj_bolum_ayir
        assert len(mesaj_bolum_ayir("Kısa")) == 1


# ── indirim_turu ────────────────────────────────────────────────

class TestIndirimTuru:
    def test_marka_kampanyasi(self):
        from services.analiz import indirim_turu
        assert indirim_turu("Adidas ürünlerinde %60 indirim") == "marka"
        assert indirim_turu("Hepsiburada satıcılı %60'a varan") == "marka"
        assert indirim_turu("Tüm ürünlerde %30") == "marka"

    def test_urun(self):
        from services.analiz import indirim_turu
        assert indirim_turu("Samsung TV 100 TL") == "urun"


# ── kategori_bul ────────────────────────────────────────────────

class TestKategori:
    def test_elektronik(self):
        from services.analiz import kategori_bul
        kat, _, _ = kategori_bul("Samsung TV satıyor")
        assert kat == "elektronik"

    def test_giyim(self):
        from services.analiz import kategori_bul
        kat, _, _ = kategori_bul("Nike ayakkabı")
        assert kat == "giyim"

    def test_genel_fallback(self):
        from services.analiz import kategori_bul
        kat, _, _ = kategori_bul("Bilinmeyen şey")
        assert kat == "genel"
