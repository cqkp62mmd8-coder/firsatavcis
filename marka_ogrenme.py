"""
═══════════════════════════════════════════════════════════════════════
Marka Otomatik Öğrenme

Yeni markalar (Sumo Performance, Eve Cosmetics, vb.) eğitim setinde yok,
ama mesajlarda tekrar tekrar görülürler. Bu modül:

1. Her başarılı tahmin için ürün adındaki tokenları kaydeder
2. Sık geçen (≥3 kez) ve bilinmeyen tokenları "marka adayı" sayar
3. Bu adayların kategorileri tutarlıysa → "marka" sözlüğüne eklenir
4. ML modeline yeni eğitim örnekleri olarak besler

Dış kütüphane yok — pure Python.
═══════════════════════════════════════════════════════════════════════
"""
import collections
import json
import os
import re
from typing import Optional

import config
from utils.log import log, simdi_tr

_MARKA_FILE = os.path.join(config.DATA_DIR, "marka_havuzu.json")

# Marka adayı eşikleri
_MIN_TEKRAR = 3        # En az kaç kez görülmeli
_MIN_TUTARLILIK = 0.7  # Aynı kategoride görülme oranı
_MAKS_HAVUZ = 5000     # Toplam adayı tut (eski sürümleri temizle)

# Belirli yerlerden token çekme — ürün adının ilk 1-2 kelimesi marka olur genelde
_BASLIK_TOKEN = re.compile(r"^([A-ZÇĞİÖŞÜ][a-zçğıöşüâî]{2,15}(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşüâî]{2,15})?)")

# Global durum
_havuz: dict[str, dict] = {}   # marka_token → {kategoriler: {kat: sayim}, ilk_gorulen, son_gorulen, marka: bool}
_yuklendi: bool = False


def _yukle() -> None:
    global _havuz, _yuklendi
    if _yuklendi:
        return
    if os.path.exists(_MARKA_FILE):
        try:
            with open(_MARKA_FILE, encoding="utf-8") as f:
                _havuz = json.load(f)
        except Exception as e:
            log("UYARI", f"Marka havuzu yükleme: {e}")
            _havuz = {}
    _yuklendi = True


def _kaydet() -> None:
    """Atomic write — kısmi yazılma korunur."""
    try:
        os.makedirs(os.path.dirname(_MARKA_FILE) or ".", exist_ok=True)
        gecici = _MARKA_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(_havuz, f, ensure_ascii=False)
        os.replace(gecici, _MARKA_FILE)
    except Exception as e:
        log("UYARI", f"Marka havuzu kaydet: {e}")


def _ilk_kelimeleri_cek(urun: str) -> list[str]:
    """Ürün adının ilk 1-2 kelimesini marka adayı olarak çıkar."""
    if not urun:
        return []
    # 'Sumo Performance Pro koşu ayakkabısı' → ['Sumo', 'Sumo Performance']
    kelimeler = urun.split()
    if not kelimeler:
        return []
    # İlk kelime tek başına
    adaylar = []
    if len(kelimeler[0]) >= 3 and kelimeler[0][0].isupper():
        adaylar.append(kelimeler[0])
    # İlk iki kelime birlikte (compound marka adı)
    if len(kelimeler) >= 2 and len(kelimeler[1]) >= 3 and kelimeler[1][0].isupper():
        adaylar.append(f"{kelimeler[0]} {kelimeler[1]}")
    return adaylar


def kaydet(urun_adi: str, kategori: str) -> None:
    """Yüksek güvenli bir ürün adının ilk kelimelerini havuza kaydet.

    Eğer aynı token birden çok kez aynı kategoride görülürse, marka olur.
    """
    if not urun_adi or not kategori or kategori == "genel":
        return
    _yukle()

    adaylar = _ilk_kelimeleri_cek(urun_adi)
    now_iso = simdi_tr().isoformat()

    for aday in adaylar:
        key = aday.lower()
        if key not in _havuz:
            _havuz[key] = {
                "orijinal":     aday,
                "kategoriler":  {},
                "ilk_gorulen":  now_iso,
                "son_gorulen":  now_iso,
                "marka":        False,
            }
        entry = _havuz[key]
        entry["kategoriler"][kategori] = entry["kategoriler"].get(kategori, 0) + 1
        entry["son_gorulen"] = now_iso

        # Marka eşiğini kontrol et
        toplam = sum(entry["kategoriler"].values())
        if toplam >= _MIN_TEKRAR and not entry["marka"]:
            # Tutarlılık kontrolü — en sık kategori toplamın %70'i mi?
            en_sik_kat, en_sik_sayim = max(entry["kategoriler"].items(), key=lambda x: x[1])
            tutarlilik = en_sik_sayim / toplam
            if tutarlilik >= _MIN_TUTARLILIK:
                entry["marka"] = True
                entry["ana_kategori"] = en_sik_kat
                log("OK", f"Yeni marka öğrenildi: '{aday}' → {en_sik_kat} ({toplam} örnek, %{tutarlilik*100:.0f} tutarlı)")

    # Boyut sınırı
    if len(_havuz) > _MAKS_HAVUZ:
        _temizle()

    # Periyodik kayıt (her 20 ekleme)
    if hash(urun_adi) % 20 == 0:
        _kaydet()


def _temizle() -> None:
    """Eski/marka-olmayan kayıtları sil."""
    global _havuz
    # En eski 'marka olmayan' kayıtları sil (havuzun %30'u)
    silinecek = sorted(
        ((k, v) for k, v in _havuz.items() if not v.get("marka")),
        key=lambda x: x[1].get("son_gorulen", "")
    )[:int(_MAKS_HAVUZ * 0.3)]
    for k, _ in silinecek:
        del _havuz[k]


def marka_mi(token: str) -> Optional[str]:
    """Verilen token bir marka mı? Markaysa ana kategorisini döner."""
    _yukle()
    entry = _havuz.get(token.lower())
    if entry and entry.get("marka"):
        return entry.get("ana_kategori")
    return None


def marka_listesi() -> list[dict]:
    """Tüm öğrenilmiş markaları listele."""
    _yukle()
    return [
        {
            "marka": v["orijinal"],
            "kategori": v.get("ana_kategori", ""),
            "sayim": sum(v["kategoriler"].values()),
            "son_gorulen": v.get("son_gorulen", ""),
        }
        for v in _havuz.values()
        if v.get("marka")
    ]


def aday_listesi(limit: int = 50) -> list[dict]:
    """Henüz marka olmamış ama yaklaşan adayları listele."""
    _yukle()
    adaylar = []
    for k, v in _havuz.items():
        if v.get("marka"):
            continue
        toplam = sum(v["kategoriler"].values())
        if toplam < 2:
            continue
        adaylar.append({
            "aday": v["orijinal"],
            "toplam": toplam,
            "kategoriler": dict(v["kategoriler"]),
        })
    adaylar.sort(key=lambda x: -x["toplam"])
    return adaylar[:limit]


def istatistik() -> dict:
    _yukle()
    toplam = len(_havuz)
    marka_sayi = sum(1 for v in _havuz.values() if v.get("marka"))
    aday_sayi = toplam - marka_sayi
    return {
        "toplam_kayit":      toplam,
        "ogrenilen_marka":   marka_sayi,
        "marka_adayi":       aday_sayi,
        "dosya":             _MARKA_FILE,
    }


def temizle_hepsi() -> int:
    """Tüm havuzu sıfırla."""
    global _havuz
    n = len(_havuz)
    _havuz = {}
    _kaydet()
    return n
