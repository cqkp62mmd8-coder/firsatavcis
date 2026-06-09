"""Çok-kiracılı (multi-tenant) SaaS katmanı testleri — v23.42."""
import os
import sys
import importlib
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("SESSION_STRING", "x")
os.environ.setdefault("CHANNEL_ID", "@test")
os.environ.setdefault("ADMIN_ID", "1")


def _temiz():
    """Her test için taze, izole bir DB + yeniden yüklenmiş modüller."""
    import config
    tmp = tempfile.mkdtemp(prefix="ck_test_")
    config.DATA_DIR = tmp
    from utils import db
    importlib.reload(db)
    from cok_kiraci import depo
    importlib.reload(depo)
    depo._KURULDU = False
    depo.kur()
    from cok_kiraci import musteri
    importlib.reload(musteri)
    return musteri, depo


class TestLisansKey:
    def test_format(self):
        musteri, _ = _temiz()
        k = musteri.lisans_key_uret()
        assert k.startswith("FP-")
        parcalar = k.split("-")
        assert len(parcalar) == 4               # FP + 3 blok
        assert all(len(p) == 4 for p in parcalar[1:])

    def test_benzersiz(self):
        musteri, _ = _temiz()
        anahtarlar = {musteri.lisans_key_uret() for _ in range(200)}
        assert len(anahtarlar) == 200           # çakışma yok


class TestMusteriYasamDongusu:
    def test_olustur_ve_giris(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur(ad="Test Kanalı", plan="aylik", gun=30)
        assert m["id"] >= 1 and m["lisans_key"].startswith("FP-")
        # doğru anahtarla giriş başarılı
        giren = musteri.giris(m["lisans_key"])
        assert giren is not None and giren["id"] == m["id"]

    def test_bilinmeyen_anahtar_reddedilir(self):
        musteri, _ = _temiz()
        assert musteri.giris("FP-XXXX-XXXX-XXXX") is None
        assert musteri.giris("") is None

    def test_askidaki_musteri_giremez(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur(gun=30)
        musteri.askiya_al(m["id"])
        assert musteri.giris(m["lisans_key"]) is None
        assert musteri.aktif_mi(m["id"]) is False

    def test_suresi_dolan_giremez(self):
        musteri, depo = _temiz()
        from utils.log import simdi_tr
        m = musteri.musteri_olustur(gun=30)
        gecmis = (simdi_tr() - timedelta(days=1)).isoformat()
        depo.musteri_guncelle(m["id"], bitis=gecmis)
        assert musteri.giris(m["lisans_key"]) is None
        assert musteri.aktif_mi(m["id"]) is False

    def test_abonelik_uzat(self):
        musteri, _ = _temiz()
        from utils.log import simdi_tr
        from datetime import datetime
        m = musteri.musteri_olustur(gun=30)
        yeni = musteri.abonelik_uzat(m["id"], 30)
        # ~60 gün ileride olmalı
        kalan = (datetime.fromisoformat(yeni) - simdi_tr()).days
        assert 58 <= kalan <= 61
        assert musteri.aktif_mi(m["id"]) is True

    def test_uzatma_suresi_dolmusu_canlandirir(self):
        musteri, depo = _temiz()
        from utils.log import simdi_tr
        from datetime import datetime
        m = musteri.musteri_olustur(gun=30)
        depo.musteri_guncelle(m["id"], bitis=(simdi_tr() - timedelta(days=10)).isoformat(),
                              durum="pasif")
        yeni = musteri.abonelik_uzat(m["id"], 30)
        kalan = (datetime.fromisoformat(yeni) - simdi_tr()).days
        assert 28 <= kalan <= 31                # geçmişten değil bugünden eklenir
        assert musteri.aktif_mi(m["id"]) is True


class TestAyar:
    def test_varsayilan_ayar(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        a = musteri.ayar_getir(m["id"])
        assert a["min_indirim"] == 20 and a["kategoriler"] == [] and a["sablon"] == "klasik"
        assert a["aktif"] is True

    def test_ayar_kaydet_getir(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], kanal="@benimkanal", min_indirim=40,
                            kategoriler=["elektronik", "moda"], sablon="modern", aktif=False)
        a = musteri.ayar_getir(m["id"])
        assert a["kanal"] == "@benimkanal"
        assert a["min_indirim"] == 40
        assert a["kategoriler"] == ["elektronik", "moda"]
        assert a["sablon"] == "modern"
        assert a["aktif"] is False

    def test_min_indirim_sinirlanir(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=150)
        assert musteri.ayar_getir(m["id"])["min_indirim"] == 99
        musteri.ayar_kaydet(m["id"], min_indirim=-5)
        assert musteri.ayar_getir(m["id"])["min_indirim"] == 0

    def test_kismi_guncelleme_digerlerini_bozmaz(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], kanal="@a", min_indirim=30)
        musteri.ayar_kaydet(m["id"], sablon="modern")   # sadece şablon
        a = musteri.ayar_getir(m["id"])
        assert a["kanal"] == "@a" and a["min_indirim"] == 30 and a["sablon"] == "modern"


class TestAffiliate:
    def test_kaydet_listele(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        musteri.affiliate_kaydet(m["id"], "Amazon", "benimtag-21")
        musteri.affiliate_kaydet(m["id"], "trendyol", "TY12345")
        af = musteri.affiliate_getir(m["id"])
        assert af["amazon"] == "benimtag-21"     # platform küçük harfe normalize
        assert af["trendyol"] == "TY12345"

    def test_etiket_guncellenir(self):
        musteri, _ = _temiz()
        m = musteri.musteri_olustur()
        musteri.affiliate_kaydet(m["id"], "amazon", "eski-21")
        musteri.affiliate_kaydet(m["id"], "amazon", "yeni-21")
        assert musteri.affiliate_getir(m["id"])["amazon"] == "yeni-21"

    def test_musteriler_ayrik(self):
        musteri, _ = _temiz()
        a = musteri.musteri_olustur()
        b = musteri.musteri_olustur()
        musteri.affiliate_kaydet(a["id"], "amazon", "a-21")
        musteri.affiliate_kaydet(b["id"], "amazon", "b-21")
        assert musteri.affiliate_getir(a["id"])["amazon"] == "a-21"
        assert musteri.affiliate_getir(b["id"])["amazon"] == "b-21"


class TestGonderimLog:
    def test_musteri_basina_tekrar_engelleme(self):
        musteri, depo = _temiz()
        from utils.log import simdi_tr
        a = musteri.musteri_olustur()
        b = musteri.musteri_olustur()
        anahtar = "amazon:B0ABC123"
        assert depo.gonderildi_mi(a["id"], anahtar) is False
        depo.gonderim_kaydet(a["id"], anahtar, simdi_tr().isoformat())
        assert depo.gonderildi_mi(a["id"], anahtar) is True
        # aynı ürün B müşterisi için hâlâ gönderilebilir (ayrık)
        assert depo.gonderildi_mi(b["id"], anahtar) is False


# ════════════════════════════════════════════════════════════════
# Faz 2 — Ortak fırsat havuzu + müşteri-başına yönlendirme
# ════════════════════════════════════════════════════════════════
def _temiz_havuz():
    musteri, depo = _temiz()
    from cok_kiraci import havuz
    importlib.reload(havuz)
    return musteri, depo, havuz


def _firsat(anahtar=None, magaza="amazon", kategori="elektronik", indirim=30,
            url=None, baslik="Ürün"):
    return {
        "urun_anahtar": anahtar,
        "magaza": magaza,
        "kategori": kategori,
        "indirim": indirim,
        "urun_url": url or f"https://example.com/p/{anahtar or baslik}",
        "baslik": baslik,
        "fiyat": 100.0,
        "eski_fiyat": 150.0,
    }


class TestHavuzEkle:
    def test_yeni_ve_tekrar(self):
        _, _, havuz = _temiz_havuz()
        assert havuz.firsat_ekle(_firsat(anahtar="amazon:A1", indirim=30)) is True
        assert havuz.firsat_ekle(_firsat(anahtar="amazon:A1", indirim=35)) is False
        assert havuz.firsat_sayisi() == 1
        assert havuz.son_firsatlar()[0]["indirim"] == 35   # güncellendi

    def test_anahtar_uretimi_query_yoksayar(self):
        _, _, havuz = _temiz_havuz()
        havuz.firsat_ekle(_firsat(anahtar=None, url="https://x.com/p/1?ref=a", magaza="trendyol"))
        havuz.firsat_ekle(_firsat(anahtar=None, url="https://x.com/p/1?ref=b", magaza="trendyol"))
        assert havuz.firsat_sayisi() == 1                  # query farkı → aynı ürün
        havuz.firsat_ekle(_firsat(anahtar=None, url="https://x.com/p/2", magaza="trendyol"))
        assert havuz.firsat_sayisi() == 2


class TestHavuzYonlendirme:
    def test_min_indirim(self):
        musteri, _, havuz = _temiz_havuz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=40, kategoriler=[])
        havuz.firsat_ekle(_firsat(anahtar="a:1", indirim=30))
        havuz.firsat_ekle(_firsat(anahtar="a:2", indirim=50))
        sonuc = havuz.musteri_icin_firsatlar(m["id"], musteri.ayar_getir(m["id"]))
        assert {d["urun_anahtar"] for d in sonuc} == {"a:2"}

    def test_kategori_filtre(self):
        musteri, _, havuz = _temiz_havuz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=0, kategoriler=["elektronik"])
        havuz.firsat_ekle(_firsat(anahtar="a:1", kategori="elektronik"))
        havuz.firsat_ekle(_firsat(anahtar="a:2", kategori="moda"))
        sonuc = havuz.musteri_icin_firsatlar(m["id"], musteri.ayar_getir(m["id"]))
        assert {d["urun_anahtar"] for d in sonuc} == {"a:1"}

    def test_bos_kategori_tumunu_alir(self):
        musteri, _, havuz = _temiz_havuz()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=0, kategoriler=[])
        havuz.firsat_ekle(_firsat(anahtar="a:1", kategori="elektronik"))
        havuz.firsat_ekle(_firsat(anahtar="a:2", kategori="moda"))
        sonuc = havuz.musteri_icin_firsatlar(m["id"], musteri.ayar_getir(m["id"]))
        assert len(sonuc) == 2

    def test_gonderilmis_haric_tutulur(self):
        musteri, depo, havuz = _temiz_havuz()
        from utils.log import simdi_tr
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=0, kategoriler=[])
        havuz.firsat_ekle(_firsat(anahtar="a:1"))
        havuz.firsat_ekle(_firsat(anahtar="a:2"))
        depo.gonderim_kaydet(m["id"], "a:1", simdi_tr().isoformat())
        sonuc = havuz.musteri_icin_firsatlar(m["id"], musteri.ayar_getir(m["id"]))
        assert {d["urun_anahtar"] for d in sonuc} == {"a:2"}

    def test_musteriler_farkli_alir(self):
        musteri, _, havuz = _temiz_havuz()
        a = musteri.musteri_olustur()
        b = musteri.musteri_olustur()
        musteri.ayar_kaydet(a["id"], min_indirim=0, kategoriler=["elektronik"])
        musteri.ayar_kaydet(b["id"], min_indirim=0, kategoriler=["moda"])
        havuz.firsat_ekle(_firsat(anahtar="x:1", kategori="elektronik"))
        havuz.firsat_ekle(_firsat(anahtar="x:2", kategori="moda"))
        sa = havuz.musteri_icin_firsatlar(a["id"], musteri.ayar_getir(a["id"]))
        sb = havuz.musteri_icin_firsatlar(b["id"], musteri.ayar_getir(b["id"]))
        assert {d["urun_anahtar"] for d in sa} == {"x:1"}
        assert {d["urun_anahtar"] for d in sb} == {"x:2"}


class TestHavuzYardimci:
    def test_eski_temizle(self):
        _, _, havuz = _temiz_havuz()
        from utils import db
        havuz.firsat_ekle(_firsat(anahtar="a:1"))
        with db.cursor() as c:
            c.execute("UPDATE firsatlar SET eklendi=? WHERE urun_anahtar=?",
                      ("2000-01-01T00:00:00", "a:1"))
        assert havuz.eski_temizle(60) == 1
        assert havuz.firsat_sayisi() == 0


# ════════════════════════════════════════════════════════════════
# Faz 3 — Şablonlar + affiliate enjeksiyonu + gönderim hattı
# ════════════════════════════════════════════════════════════════
def _temiz_gonderim():
    musteri, depo, havuz = _temiz_havuz()
    from cok_kiraci import sablonlar, affiliate, gonderim
    importlib.reload(sablonlar)
    importlib.reload(affiliate)
    importlib.reload(gonderim)
    return musteri, depo, havuz, sablonlar, affiliate, gonderim


class _SahteGonderici:
    """Test için: çağrıları kaydeder, başarı/başarısızlık taklit eder."""
    def __init__(self, basarili=True):
        self.basarili = basarili
        self.cagrilar = []
    def __call__(self, kanal, mesaj, gorsel):
        self.cagrilar.append((kanal, mesaj, gorsel))
        return self.basarili


class TestSablonRender:
    def test_uc_sablon_calisir(self):
        *_, sablonlar, _, _ = _temiz_gonderim()
        f = _firsat(anahtar="a:1", baslik="Test Ürünü", indirim=40)
        for sid in sablonlar.sablon_listesi():
            m = sablonlar.render(sid, f, "https://link")
            assert "Test Ürünü" in m and "https://link" in m

    def test_indirim_gosterilir(self):
        *_, sablonlar, _, _ = _temiz_gonderim()
        f = _firsat(anahtar="a:1", indirim=45)
        assert "45" in sablonlar.render("klasik", f, "https://l")

    def test_bilinmeyen_sablon_klasige_duser(self):
        *_, sablonlar, _, _ = _temiz_gonderim()
        f = _firsat(anahtar="a:1", baslik="XÜrün")
        m = sablonlar.render("yokboyle", f, "https://l")
        assert "XÜrün" in m and "https://l" in m

    def test_eski_fiyat_yoksa_patlamaz(self):
        *_, sablonlar, _, _ = _temiz_gonderim()
        f = _firsat(anahtar="a:1")
        f["eski_fiyat"] = None
        assert "https://l" in sablonlar.render("vurgulu", f, "https://l")

    def test_sablon_listesi(self):
        *_, sablonlar, _, _ = _temiz_gonderim()
        assert set(sablonlar.sablon_listesi()) == {"klasik", "minimal", "vurgulu"}


class TestAffiliateEnjekte:
    def test_amazon_tag_ekler(self):
        *_, affiliate, _ = _temiz_gonderim()
        s = affiliate.enjekte("https://www.amazon.com.tr/dp/B0ABC", "amazon", "benimtag-21")
        assert "tag=benimtag-21" in s

    def test_amazon_mevcut_tag_degistirir(self):
        *_, affiliate, _ = _temiz_gonderim()
        s = affiliate.enjekte("https://www.amazon.com.tr/dp/B0ABC?tag=eski-21", "amazon", "yeni-21")
        assert "tag=yeni-21" in s and "eski-21" not in s

    def test_diger_platform_degismez(self):
        *_, affiliate, _ = _temiz_gonderim()
        url = "https://www.trendyol.com/p/123"
        assert affiliate.enjekte(url, "trendyol", "TY1") == url

    def test_etiket_yoksa_degismez(self):
        *_, affiliate, _ = _temiz_gonderim()
        url = "https://www.amazon.com.tr/dp/B0ABC"
        assert affiliate.enjekte(url, "amazon", "") == url

    def test_destek_durumu(self):
        *_, affiliate, _ = _temiz_gonderim()
        assert affiliate.desteklenen_platform("amazon") is True
        assert affiliate.desteklenen_platform("trendyol") is False


class TestGonderimHatti:
    def _hazirla(self, musteri, havuz):
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], kanal="@musteri_kanal", min_indirim=0,
                            kategoriler=[], sablon="klasik")
        musteri.affiliate_kaydet(m["id"], "amazon", "mytag-21")
        havuz.firsat_ekle(_firsat(anahtar="amazon:A1", magaza="amazon",
                                  url="https://amazon.com.tr/dp/B0X", indirim=30))
        return m

    def test_gonderir_kaydeder_ve_tekrar_etmez(self):
        musteri, depo, havuz, *_ , gonderim = _temiz_gonderim()
        m = self._hazirla(musteri, havuz)
        g = _SahteGonderici()
        assert gonderim.musteri_gonder(m["id"], g) == 1
        kanal, mesaj, _gorsel = g.cagrilar[0]
        assert kanal == "@musteri_kanal"
        assert "tag=mytag-21" in mesaj                  # affiliate enjekte edildi
        assert gonderim.musteri_gonder(m["id"], g) == 0  # gonderim_log → tekrar yok

    def test_pasif_musteri_gondermez(self):
        musteri, depo, havuz, *_, gonderim = _temiz_gonderim()
        m = self._hazirla(musteri, havuz)
        musteri.askiya_al(m["id"])
        assert gonderim.musteri_gonder(m["id"], _SahteGonderici()) == 0

    def test_yayini_kapali_gondermez(self):
        musteri, depo, havuz, *_, gonderim = _temiz_gonderim()
        m = self._hazirla(musteri, havuz)
        musteri.ayar_kaydet(m["id"], aktif=False)
        assert gonderim.musteri_gonder(m["id"], _SahteGonderici()) == 0

    def test_kanal_yoksa_gondermez(self):
        musteri, depo, havuz, *_, gonderim = _temiz_gonderim()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], min_indirim=0, kategoriler=[])  # kanal yok
        havuz.firsat_ekle(_firsat(anahtar="a:1"))
        assert gonderim.musteri_gonder(m["id"], _SahteGonderici()) == 0

    def test_basarisiz_gonderim_yeniden_denenir(self):
        musteri, depo, havuz, *_, gonderim = _temiz_gonderim()
        m = self._hazirla(musteri, havuz)
        assert gonderim.musteri_gonder(m["id"], _SahteGonderici(basarili=False)) == 0
        # log'a yazılmadı → başarılı gönderici ile yeniden denenebilir
        assert gonderim.musteri_gonder(m["id"], _SahteGonderici(basarili=True)) == 1

    def test_tum_musteriler_gonder(self):
        musteri, depo, havuz, *_, gonderim = _temiz_gonderim()
        a = musteri.musteri_olustur()
        b = musteri.musteri_olustur()
        for c in (a, b):
            musteri.ayar_kaydet(c["id"], kanal=f"@k{c['id']}", min_indirim=0, kategoriler=[])
        havuz.firsat_ekle(_firsat(anahtar="x:1", indirim=10))
        sonuc = gonderim.tum_musteriler_gonder(_SahteGonderici())
        assert sonuc.get(a["id"]) == 1 and sonuc.get(b["id"]) == 1


# ════════════════════════════════════════════════════════════════
# Faz 4 — Müşteri web paneli (oturum + form + sayfa mantığı)
# ════════════════════════════════════════════════════════════════
def _temiz_panel():
    musteri, depo, havuz, sablonlar, affiliate, gonderim = _temiz_gonderim()
    from cok_kiraci import panel
    importlib.reload(panel)
    return musteri, panel


class TestPanelOturum:
    def test_token_cozulur(self):
        musteri, panel = _temiz_panel()
        t = panel.oturum_token("FP-ABCD-EFGH-JKLM")
        assert panel.oturum_coz(t) == "FP-ABCD-EFGH-JKLM"

    def test_kurcalanmis_token_reddedilir(self):
        musteri, panel = _temiz_panel()
        t = panel.oturum_token("FP-ABCD-EFGH-JKLM")
        sahte = t[:-1] + ("0" if t[-1] != "0" else "1")
        assert panel.oturum_coz(sahte) is None
        assert panel.oturum_coz("") is None
        assert panel.oturum_coz("FP-XXXX.yanlisimza") is None

    def test_cerezden_aktif_musteri(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        t = panel.oturum_token(m["lisans_key"])
        giren = panel.cerezden_musteri(t)
        assert giren is not None and giren["id"] == m["id"]

    def test_cerezden_pasif_musteri_yok(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        musteri.askiya_al(m["id"])
        t = panel.oturum_token(m["lisans_key"])
        assert panel.cerezden_musteri(t) is None


class TestPanelForm:
    def test_form_ayar_kaydeder(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        panel.form_isle(m["id"], {
            "kanal": "@benimkanal", "min_indirim": "35",
            "kategoriler": "elektronik, moda", "sablon": "vurgulu",
            "aktif": "1", "aff_amazon": "tag-21",
        })
        a = musteri.ayar_getir(m["id"])
        assert a["kanal"] == "@benimkanal"
        assert a["min_indirim"] == 35
        assert a["kategoriler"] == ["elektronik", "moda"]
        assert a["sablon"] == "vurgulu"
        assert a["aktif"] is True
        assert musteri.affiliate_getir(m["id"])["amazon"] == "tag-21"

    def test_yayin_duraklatma(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        panel.form_isle(m["id"], {"aktif": "0"})
        assert musteri.ayar_getir(m["id"])["aktif"] is False

    def test_gecersiz_min_indirim_yoksayilir(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        panel.form_isle(m["id"], {"min_indirim": "abc"})   # patlamamalı
        assert musteri.ayar_getir(m["id"])["min_indirim"] == 20


class TestPanelSayfa:
    def test_giris_sayfasi(self):
        musteri, panel = _temiz_panel()
        h = panel.giris_html()
        assert 'action="/musteri/giris"' in h and 'name="lisans"' in h

    def test_giris_hata_gosterir(self):
        musteri, panel = _temiz_panel()
        assert "Lisans hatalı" in panel.giris_html("Lisans hatalı")

    def test_panel_mevcut_degerleri_gosterir(self):
        musteri, panel = _temiz_panel()
        m = musteri.musteri_olustur()
        musteri.ayar_kaydet(m["id"], kanal="@gorunsun", min_indirim=42, sablon="minimal")
        musteri.affiliate_kaydet(m["id"], "amazon", "amztag-21")
        h = panel.panel_html(m, musteri.ayar_getir(m["id"]), musteri.affiliate_getir(m["id"]))
        assert "@gorunsun" in h                 # mevcut kanal
        assert 'value="42"' in h                # mevcut min indirim
        assert "amztag-21" in h                 # mevcut affiliate etiketi
        assert "aff_amazon" in h and "aff_trendyol" in h
        assert "minimal" in h                   # şablon seçeneği
