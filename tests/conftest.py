"""Test fixtures — pytest tüm test dosyalarından önce çalıştırır."""
import os
import sys
from pathlib import Path

# Proje kökünü Python path'ine ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test öncesi gerekli env var'ları setle (config.py import edilince çakışmasın)
os.environ.setdefault("API_ID",         "12345")
os.environ.setdefault("API_HASH",       "0" * 32)
os.environ.setdefault("SESSION_STRING", "x" * 200)
os.environ.setdefault("CHANNEL_ID",     "@test_kanal")
os.environ.setdefault("MIN_INDIRIM",    "20")
os.environ.setdefault("MIN_KALITE",     "15")
os.environ.setdefault("KUYRUK_BEKLEME", "180")
