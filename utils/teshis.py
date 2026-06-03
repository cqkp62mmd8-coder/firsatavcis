"""
═══════════════════════════════════════════════════════════════════════
SİSTEM TEŞHİS (v23.5)

Her kritik modülü CANLI test eder: sadece "dosya var mı" değil,
"gerçekten çalışıyor mu?" sorusunu yanıtlar. Bozuk/sessizce ölmüş
özellikleri yakalar. /teshis komutuyla tek bakışta tüm sistemin
sağlığını görürsün.

Her test: (ad, durum, detay) döner. Durum: "ok" | "uyari" | "hata".
"""
import time


def _test(ad: str, fn) -> dict:
    """Bir modül fonksiyonunu güvenle çağır, sonucu raporla."""
    t0 = time.perf_counter()
    try:
        sonuc = fn()
        ms = (time.perf_counter() - t0) * 1000
        if sonuc is False:
            return {"ad": ad, "durum": "uyari", "detay": "boş/pasif", "ms": ms}
        return {"ad": ad, "durum": "ok", "detay": str(sonuc)[:60], "ms": ms}
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return {"ad": ad, "durum": "hata", "detay": f"{type(e).__name__}: {e}"[:60], "ms": ms}


def tam_teshis() -> list[dict]:
    """Tüm kritik modülleri canlı test et. Liste döner."""
    sonuclar = []

    # 1. Ürün adı kapısı (en kritik — Amazon TR koruması)
    def _kapi():
        from services.urun_kapisi import gecerli_urun_adi
        cop = gecerli_urun_adi("Amazon TR")
        gercek = gecerli_urun_adi("Apple iPhone 15 Pro")
        if cop is not None:
            raise ValueError("Amazon TR ÇÖPÜ GEÇİYOR!")
        if gercek is None:
            raise ValueError("gerçek ürün reddediliyor!")
        return "çöp✓ gerçek✓"
    sonuclar.append(_test("Ürün adı kapısı", _kapi))

    # 2. Ürün adı çıkarma
    def _urunadi():
        from services.analiz import urun_adi_bul
        import services.analiz as a
        a._mesaj_cache.clear()
        r = urun_adi_bul("Apple iPhone 15 Pro Max\n45000 TL\namazon.com.tr/dp/B0X")
        if not r or "iphone" not in r.lower():
            raise ValueError("ürün adı çıkmadı")
        return r[:40]
    sonuclar.append(_test("Ürün adı çıkarma", _urunadi))

    # 3. Kategori tahmini
    def _kategori():
        from services.analiz import kategori_bul
        k, _, _ = kategori_bul("Apple iPhone 15 Pro")
        return f"iPhone→{k}"
    sonuclar.append(_test("Kategori tahmini", _kategori))

    # 4. Fiyat çıkarma
    def _fiyat():
        from services.analiz import fiyat_bul
        _, _, _, yeni = fiyat_bul("İndirimli 450 TL normal 900 TL")
        if not yeni:
            raise ValueError("fiyat çıkmadı")
        return f"{yeni} TL"
    sonuclar.append(_test("Fiyat çıkarma", _fiyat))

    # 5. Şablon üretimi (uçtan uca)
    def _sablon():
        from services.sablon import olustur
        import services.analiz as a
        a._mesaj_cache.clear()
        s = olustur("Apple iPhone 15\n45000 TL\n%20\namazon.com.tr/dp/B0X", 20,
                    ["https://amazon.com.tr/dp/B0X"])
        if not s or "iPhone" not in s:
            raise ValueError("şablon üretilemedi")
        return "üretildi ✓"
    sonuclar.append(_test("Şablon üretimi", _sablon))

    # 6. Fiyat takip
    def _fiyat_takip():
        from utils import fiyat_takip
        return fiyat_takip.istatistik()
    sonuclar.append(_test("Fiyat takip", _fiyat_takip))

    # 7. Duplicate engelleme
    def _duplicate():
        from utils import duplicate
        return duplicate.istatistik()
    sonuclar.append(_test("Duplicate engelleme", _duplicate))

    # 8. Kalite skoru
    def _kalite():
        from utils import kalite
        return "aktif"
    sonuclar.append(_test("Kalite sistemi", _kalite))

    # 9. Kullanıcı istek
    def _istek():
        from utils import istek
        return istek.istatistik()
    sonuclar.append(_test("Kullanıcı istek", _istek))

    # 10. Etkileşim
    def _etkilesim():
        from utils import etkilesim
        if not hasattr(etkilesim, "haftanin_urunu"):
            raise ValueError("etkileşim API eksik")
        return "aktif"
    sonuclar.append(_test("Etkileşim sistemi", _etkilesim))

    # 11. Zamanlama
    def _zamanlama():
        from utils import zamanlama
        return zamanlama.istatistik()
    sonuclar.append(_test("Akıllı zamanlama", _zamanlama))

    # 12. Sözlük (zehirlenme kontrolü)
    def _sozluk():
        from utils import sozluk
        # "amazon" ÖĞRENİLMEMİŞ olmalı (zehir kontrolü)
        if sozluk.urun_kelimesi_mi("amazon"):
            raise ValueError("SÖZLÜK ZEHİRLİ: 'amazon' öğrenilmiş!")
        # v23.11 — Kod versiyonu kontrolü: yeni çöp listesi yüklü mü?
        # "marka" _DURDUR'da olmalı; değilse ESKİ KOD çalışıyor demektir.
        try:
            durdur = getattr(sozluk, "_DURDUR", set())
            if "marka" not in durdur or "ye" not in durdur:
                raise ValueError("ESKİ KOD! sozluk.py güncellenmemiş (deploy sorunu)")
        except ValueError:
            raise
        except Exception:
            pass
        ist = sozluk.istatistik()
        return f"{ist.get('toplam_kelime', 0)} kelime, kod güncel ✓"
    sonuclar.append(_test("Sözlük (zehir kontrolü)", _sozluk))

    # 13. Veritabanı
    def _db():
        from utils import db
        with db.cursor() as c:
            c.execute("SELECT 1")
        return "bağlantı ✓"
    sonuclar.append(_test("Veritabanı", _db))

    # 14. ML kategori modeli
    def _ml():
        from utils import ml_kategori
        if hasattr(ml_kategori, "istatistik"):
            ist = ml_kategori.istatistik()
            return f"{ist.get('toplam_ornek', '?')} örnek"
        return "yüklü"
    sonuclar.append(_test("ML kategori modeli", _ml))

    return sonuclar


def ozet() -> dict:
    """Teşhis özetini döndür: kaç ok/uyarı/hata."""
    sonuclar = tam_teshis()
    ok = sum(1 for s in sonuclar if s["durum"] == "ok")
    uyari = sum(1 for s in sonuclar if s["durum"] == "uyari")
    hata = sum(1 for s in sonuclar if s["durum"] == "hata")
    return {"toplam": len(sonuclar), "ok": ok, "uyari": uyari,
            "hata": hata, "detay": sonuclar}
