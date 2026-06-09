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
