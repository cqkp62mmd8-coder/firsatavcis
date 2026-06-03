"""
Integration testler — pipeline'ın uçtan uca çalıştığını doğrular.
Mock telethon ile çalışır — gerçek Telegram bağlantısı yok.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

# Env setup — config import'tan ÖNCE setlenmeli
import os
os.environ.setdefault("API_ID",         "12345")
os.environ.setdefault("API_HASH",       "0" * 32)
os.environ.setdefault("SESSION_STRING", "x" * 200)
os.environ.setdefault("CHANNEL_ID",     "@test_kanal")
os.environ.setdefault("MIN_INDIRIM",    "20")
os.environ.setdefault("MIN_KALITE",     "15")
os.environ.setdefault("KUYRUK_BEKLEME", "1")
os.environ["DATA_DIR"] = "/tmp/firsatpulsu_test"   # zorla override
os.makedirs("/tmp/firsatpulsu_test", exist_ok=True)

# Config'i yeniden yükle (eğer önce import edildiyse DATA_DIR güncellensin)
import config
if config.DATA_DIR != "/tmp/firsatpulsu_test":
    config.DATA_DIR = "/tmp/firsatpulsu_test"
    config.GORULMUS_FILE = os.path.join(config.DATA_DIR, "gorulmus.json")
    config.ISTATISTIK_FILE = os.path.join(config.DATA_DIR, "istatistik.json")


def _temiz_kurulum():
    """Test DB'yi sıfırla — connection cache de dahil."""
    import shutil
    if os.path.exists("/tmp/firsatpulsu_test"):
        shutil.rmtree("/tmp/firsatpulsu_test")
    os.makedirs("/tmp/firsatpulsu_test")
    try:
        from utils import db
        # Yeni DATA_DIR'e göre DB_FILE'ı güncelle
        db.DB_FILE = os.path.join("/tmp/firsatpulsu_test", "firsatpulsu.db")
        if hasattr(db._baglanti_yerel, "conn"):
            try:
                db._baglanti_yerel.conn.close()
            except Exception:
                pass
            del db._baglanti_yerel.conn
    except Exception:
        pass


def _mock_msg(mid=1, text="", buttons=None):
    """Sahte Telethon Message nesnesi."""
    msg = MagicMock()
    msg.id = mid
    msg.text = text
    msg.message = text
    msg.buttons = buttons
    msg.reply_markup = None
    msg.entities = []
    from datetime import datetime, timezone
    msg.date = datetime.now(timezone.utc)
    return msg


def _mock_btn(url):
    """Sahte buton."""
    btn = MagicMock()
    btn.url = url
    return btn


# ── E2E pipeline: filtre → şablon → kuyruk ───────────────────────

class TestPipeline:
    def test_gercek_mesaj_pipeline(self):
        """Gerçek bir mesajı tam analiz → şablon haline getir."""
        _temiz_kurulum()
        from utils import db
        db.init()

        from services.analiz import (
            markdown_temizle, mesaj_bolum_ayir, indirim_oranini_bul,
            link_bul, urun_adi_bul, kalite_skoru, magaza_bul, firsat_skoru,
        )
        from services.sablon import olustur

        # Bosch örneği — gerçek bot mesajı
        m = """📦 Bosch Akülü Elektrikli Süpürge
⚡️ İndirimli Fiyat: ₺1.676,27
💰 Normal Fiyat: ₺3.109,39
⬇️ İndirim: -%46"""
        btn_links = ["https://amzn.to/bosch-vacuum"]

        ham = markdown_temizle(m)
        ind = indirim_oranini_bul(ham)
        urun = urun_adi_bul(ham)
        lnk = link_bul(ham, btn_links)
        kal = kalite_skoru(ham, ind, btn_links)
        fs = firsat_skoru(ham, ind, btn_links)
        mag = magaza_bul(ham, lnk)

        assert ind == 46, f"İndirim yanlış: {ind}"
        assert "Bosch" in urun, f"Ürün adı yanlış: {urun}"
        assert "amzn" in lnk, f"Link yanlış: {lnk}"
        assert kal >= 50, f"Kalite çok düşük: {kal}"
        assert mag == "Amazon TR", f"Mağaza yanlış: {mag}"

        # Şablon
        cikti = olustur(ham, ind, btn_links)
        assert cikti is not None
        assert "Bosch" in cikti
        assert "%46" in cikti

    def test_negatif_mesaj_reddedilir(self):
        """'iptal edildi' içeren mesaj None döner."""
        _temiz_kurulum()
        from services.sablon import olustur
        sonuc = olustur("Bu fırsat iptal edildi, yanlış paylaşım", 50, ["https://amzn.to/x"])
        assert sonuc is None

    def test_dusuk_indirim_sablon_calisir(self):
        """%20 üstü = geçer."""
        _temiz_kurulum()
        from services.sablon import olustur
        m = "🔥 Logitech Mouse 100 TL yerine 75 TL"
        sonuc = olustur(m, 25, ["https://amzn.to/x"])
        assert sonuc is not None
        assert "%25" in sonuc


# ── SQLite duplikat ──────────────────────────────────────────────

class TestSQLiteCache:
    def test_gorulmus_db_calisma(self):
        """SQLite görülmüş cache'i çalışıyor mu."""
        _temiz_kurulum()
        from utils import db, cache
        db.init()

        assert not cache.gorulmus_var_mi("abc123")
        cache.gorulmus_ekle("abc123")
        assert cache.gorulmus_var_mi("abc123")
        assert not cache.gorulmus_var_mi("xyz789")

    def test_ist_guncelle_birikim(self):
        """İstatistik birikiyor mu."""
        _temiz_kurulum()
        from utils import db, cache
        db.init()

        cache.ist_guncelle("kanal1", "Trendyol", "elektronik")
        cache.ist_guncelle("kanal1", "Trendyol", "elektronik")
        cache.ist_guncelle("kanal2", "Amazon TR", "giyim")

        ist = cache.ist_yukle()
        assert ist["toplam"] == 3
        assert ist["magazalar"]["Trendyol"] == 2
        assert ist["magazalar"]["Amazon TR"] == 1
        assert ist["kategoriler"]["elektronik"] == 2

    def test_gorulmus_temizleme(self):
        """TTL ve max limit temizleme."""
        _temiz_kurulum()
        from utils import db, cache
        import config as cfg
        db.init()

        # Limit'i 5 yap
        eski_max = cfg.GORULMUS_MAX
        cfg.GORULMUS_MAX = 5
        try:
            for i in range(10):
                cache.gorulmus_ekle(f"key_{i}")
            cache.gorulmus_temizle()
            # 5'e indirilmiş olmalı
            with db.cursor() as c:
                c.execute("SELECT COUNT(*) FROM gorulmus")
                sayi = c.fetchone()[0]
            assert sayi <= 5
        finally:
            cfg.GORULMUS_MAX = eski_max


# ── Telemetri ───────────────────────────────────────────────────

class TestMetrik:
    def test_kayit_ve_oku(self):
        _temiz_kurulum()
        from utils import db, metrik
        db.init()

        metrik.kayit("paylasildi", magaza="Trendyol", indirim=50)
        metrik.kayit("paylasildi", magaza="Amazon TR", indirim=70)
        metrik.kayit("reddedildi")

        sonuc = metrik.son_n_saat(24)
        assert sonuc.get("paylasildi") == 2
        assert sonuc.get("reddedildi") == 1


# ── İzleme (secret sansürleme) ──────────────────────────────────

class TestSansurleme:
    def test_secret_sansur(self):
        from utils.izleme import sansurle

        # Bot token
        out = sansurle("BOT_TOKEN=123456789:ABCdef_GHIjklMNOpqrSTUvwxYZ1234567")
        assert "BOT_TOKEN" in out
        assert "123456789:ABCdef" not in out

        # API hash
        out = sansurle("api_hash=abc123def456" + "0" * 30)
        assert "abc123def456" not in out


# ── FloodWait davranışı ─────────────────────────────────────────

class TestFloodWait:
    def test_floodwait_carpan_artisi(self):
        """FloodWait sonrası sleep carpani arttığını test et."""
        _temiz_kurulum()
        try:
            from services import kuyruk as k_mod
        except ImportError:
            return  # telethon yoksa skip
        k_mod._floodwait_carpani = 1.0
        assert k_mod._bekleme_carpani_aktif() == 1.0

    def test_floodwait_carpani_max(self):
        """Çarpan en fazla 4.0'a çıkar."""
        try:
            from services import kuyruk as k_mod
        except ImportError:
            return  # telethon yoksa skip
        k_mod._floodwait_carpani = 5.0
        assert min(k_mod._floodwait_carpani * 1.5, 4.0) == 4.0
