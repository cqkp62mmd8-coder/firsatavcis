"""Pytest yoksa kullanılabilen basit test koşucu."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# conftest yerine env'i burada setle
import os
os.environ.setdefault("API_ID",         "12345")
os.environ.setdefault("API_HASH",       "0" * 32)
os.environ.setdefault("SESSION_STRING", "x" * 200)
os.environ.setdefault("CHANNEL_ID",     "@test_kanal")
os.environ.setdefault("MIN_INDIRIM",    "20")
os.environ.setdefault("MIN_KALITE",     "15")
os.environ.setdefault("KUYRUK_BEKLEME", "180")

import inspect, traceback, importlib

modules = ["test_analiz", "test_sablon", "test_integration", "test_v18", "test_gercek_mesajlar"]
total = 0
basari = 0
hatalar = []

for mod_ad in modules:
    try:
        mod = importlib.import_module(mod_ad)
    except Exception as e:
        print(f"❌ Modül yüklenemedi: {mod_ad}: {e}")
        continue

    siniflar = [
        (ad, obj) for ad, obj in inspect.getmembers(mod, inspect.isclass)
        if ad.startswith("Test")
    ]
    for sinif_ad, sinif in siniflar:
        instance = sinif()
        testler = [m for m in dir(instance) if m.startswith("test_")]
        for t_ad in testler:
            total += 1
            try:
                getattr(instance, t_ad)()
                basari += 1
            except Exception as e:
                hatalar.append((f"{mod_ad}::{sinif_ad}::{t_ad}", e, traceback.format_exc()))

print(f"\n{'='*60}")
print(f"Test sonucu: {basari}/{total} geçti")
if hatalar:
    print(f"\n{len(hatalar)} hata:")
    for ad, e, tb in hatalar[:5]:
        print(f"\n❌ {ad}")
        print(f"   {type(e).__name__}: {e}")
sys.exit(0 if basari == total else 1)
