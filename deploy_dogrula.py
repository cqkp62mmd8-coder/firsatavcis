#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════
DEPLOY DOĞRULAMA — Tüm dosyalar eksiksiz mi?

Karışık deploy sorununu yakalar. Deploy öncesi VEYA sonrası çalıştır:
  python3 deploy_dogrula.py

Eksik/bozuk dosya varsa söyler. Railway'de de çalışabilir (başlangıçta).
═══════════════════════════════════════════════════════════════════════
"""
import ast
import os
import sys

# Sistemin çalışması için ZORUNLU dosyalar
ZORUNLU = [
    "main.py", "config.py", "client.py", "state.py", "watchdog.py",
    "Procfile", "requirements.txt",
    "handlers/mesaj.py", "handlers/admin.py", "handlers/callback.py",
    "services/analiz.py", "services/sablon.py", "services/kuyruk.py",
    "services/gorsel.py", "services/health.py", "services/scraping.py",
    "services/stok_takip.py", "services/zenginlestir.py",
    "utils/gemini.py", "utils/saglik.py", "utils/ml_dataset.py",
    "utils/ml_kategori.py", "utils/urun_taniyici.py", "utils/reklam.py",
    "utils/segment.py", "utils/urun_hafiza.py", "utils/db.py", "utils/log.py", "utils/cache.py",
    "schedulers/gunluk.py", "schedulers/surpriz.py", "schedulers/haftalik.py",
]


def dogrula(kok: str = ".") -> bool:
    eksik = []
    bozuk = []
    for yol in ZORUNLU:
        tam = os.path.join(kok, yol)
        if not os.path.exists(tam):
            eksik.append(yol)
            continue
        # Python dosyaysa syntax kontrol
        if yol.endswith(".py"):
            try:
                ast.parse(open(tam, encoding="utf-8").read())
            except SyntaxError as e:
                bozuk.append(f"{yol}: satır {e.lineno}")

    print("=" * 55)
    print("DEPLOY BÜTÜNLÜK KONTROLÜ")
    print("=" * 55)
    if not eksik and not bozuk:
        print(f"✅ Tüm {len(ZORUNLU)} zorunlu dosya mevcut ve sağlam.")
        print("   Deploy güvenli.")
        return True
    if eksik:
        print(f"\n❌ EKSİK DOSYALAR ({len(eksik)}):")
        for e in eksik:
            print(f"   • {e}")
        print("\n   → Bu dosyalar GitHub'a yüklenmemiş. Karışık deploy riski!")
    if bozuk:
        print(f"\n❌ BOZUK DOSYALAR ({len(bozuk)}):")
        for b in bozuk:
            print(f"   • {b}")
    return False


def klasor_ozeti(kok: str = ".") -> None:
    """Her klasördeki .py dosya sayısını yazdırır.
    GitHub'da görünen sayılarla karşılaştırılır — eksik klasör tespiti için."""
    print("=" * 55)
    print("KLASÖR DOSYA SAYILARI (GitHub ile karşılaştırın)")
    print("=" * 55)
    beklenen = {
        ".": 6, "handlers": 4, "services": 9, "utils": 22, "schedulers": 4,
    }
    for klasor, bekle in beklenen.items():
        yol = kok if klasor == "." else os.path.join(kok, klasor)
        try:
            if klasor == ".":
                n = len([f for f in os.listdir(yol)
                         if f.endswith(".py") and os.path.isfile(os.path.join(yol, f))])
                ad = "Kök (ana)"
            else:
                n = len([f for f in os.listdir(yol) if f.endswith(".py")])
                ad = klasor + "/"
            isaret = "✅" if n >= bekle else "❌ EKSİK"
            print(f"   {isaret} {ad:14} {n}/{bekle} .py dosyası")
        except FileNotFoundError:
            print(f"   ❌ {klasor}/ KLASÖR YOK!")


if __name__ == "__main__":
    kok_dizin = os.path.dirname(os.path.abspath(__file__))
    klasor_ozeti(kok_dizin)
    print()
    ok = dogrula(kok_dizin)
    sys.exit(0 if ok else 1)
