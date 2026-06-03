"""
═══════════════════════════════════════════════════════════════════════
SÜRÜM & BÜTÜNLÜK KONTROLÜ — karışık deploy'u otomatik yakalar

Sorun: Dosyalar Railway'e parça parça gidince eski+yeni karışıyor,
sessizce hatalı çalışıyor.

Çözüm: Bot başlarken tüm kritik modüllerin (a) yüklenebildiğini ve
(b) beklenen fonksiyon/imzalara sahip olduğunu kontrol eder. Eksik
veya eski bir dosya varsa admin'e NET bildirir — "şu dosya eski/eksik".

Böylece karışık deploy artık sessiz kalmaz, anında fark edilir.
═══════════════════════════════════════════════════════════════════════
"""
try:
    import config
    SURUM = config.SURUM
except Exception:
    SURUM = "v21.5"

# Her kritik modülde bulunması GEREKEN şeyler (karışık deploy tespiti).
# (modül_yolu, [olması gereken öznitelikler])
_BEKLENEN = [
    ("utils.gemini",        ["analiz_et", "kisa_metin", "istatistik", "kullanilabilir"]),
    ("utils.saglik",        ["kaydet", "saglik_kontrol", "ozet"]),
    ("utils.ml_dataset",    ["EGITIM_VERISI", "TOPLAM_ORNEK"]),
    ("services.analiz",     ["urun_adi_bul", "urun_kimligine_gore_grupla",
                             "_karsilastir_ctasi_temizle", "_urun_adi_makul"]),
    ("services.sablon",     ["olustur", "_sablon_kalite_gecer"]),
    ("utils.segment",       ["oy_sayilari", "en_cok_oylanan", "begenilen_kategoriler"]),
]


def butunluk_kontrol() -> list[str]:
    """Tüm kritik modülleri kontrol et. Eksik/eski olanların listesini döner.
    Boş liste = her şey güncel ve uyumlu."""
    eksikler: list[str] = []
    import importlib
    for modul_yolu, ozellikler in _BEKLENEN:
        try:
            mod = importlib.import_module(modul_yolu)
        except Exception as e:
            eksikler.append(f"❌ {modul_yolu} YÜKLENEMEDİ ({type(e).__name__}) — dosya eksik/bozuk")
            continue
        for oz in ozellikler:
            if not hasattr(mod, oz):
                eksikler.append(f"⚠️ {modul_yolu}.{oz} YOK — bu dosya ESKİ sürüm")
    return eksikler


def ozet() -> str:
    """Kısa bütünlük özeti (log/rapor için)."""
    eksikler = butunluk_kontrol()
    if not eksikler:
        try:
            from utils.ml_dataset import TOPLAM_ORNEK
            return f"✅ Sürüm {SURUM} — tüm modüller güncel (ML: {TOPLAM_ORNEK} örnek)"
        except Exception:
            return f"✅ Sürüm {SURUM} — tüm modüller güncel"
    return (f"🚨 Sürüm {SURUM} — KARIŞIK DEPLOY tespit edildi:\n" +
            "\n".join(eksikler) +
            "\n\n→ DEPLOY_REHBERI.md ile eksik dosyaları yükleyin.")
