"""
Kalıcı depolama: görülmüş (duplikat önleme) ve istatistik JSON dosyaları.
"""
import json
from datetime import datetime, timezone
from config.settings import (
    GORULMUS_FILE, ISTATISTIK_FILE,
    GORULMUS_MAX, GORULMUS_TTL,
)
from utils.logger import log

# ─── Görülmüş ──────────────────────────────────────────────────
_gorulmus_cache: dict | None = None
_istatistik_cache: dict | None = None
_ist_degisim_sayac = 0


def gorulmus_yukle() -> dict:
    global _gorulmus_cache
    if _gorulmus_cache is not None:
        return _gorulmus_cache
    try:
        with open(GORULMUS_FILE, "r") as f:
            _gorulmus_cache = json.load(f)
    except Exception:
        _gorulmus_cache = {}
    return _gorulmus_cache


def gorulmus_kaydet() -> None:
    global _gorulmus_cache
    if _gorulmus_cache is None:
        return
    try:
        if len(_gorulmus_cache) > GORULMUS_MAX:
            sirali = sorted(_gorulmus_cache.items(), key=lambda x: x[1], reverse=True)
            _gorulmus_cache = dict(sirali[:GORULMUS_MAX])
        with open(GORULMUS_FILE, "w") as f:
            json.dump(_gorulmus_cache, f)
    except Exception as e:
        log("HATA", f"gorulmus kaydetme: {e}")


def gorulmus_temizle() -> None:
    global _gorulmus_cache
    gorulmus_yukle()
    if not _gorulmus_cache:
        return
    simdi = datetime.now(timezone.utc).timestamp()
    onceki = len(_gorulmus_cache)
    _gorulmus_cache = {k: v for k, v in _gorulmus_cache.items() if simdi - v < GORULMUS_TTL}
    if len(_gorulmus_cache) > GORULMUS_MAX:
        sirali = sorted(_gorulmus_cache.items(), key=lambda x: x[1], reverse=True)
        _gorulmus_cache = dict(sirali[:GORULMUS_MAX])
    temizlenen = onceki - len(_gorulmus_cache)
    if temizlenen > 0:
        log("BILGI", f"{temizlenen} eski görülmüş kaydı temizlendi")
    gorulmus_kaydet()


def gorulmus_var_mi(mid: str) -> bool:
    return mid in gorulmus_yukle()


def gorulmus_ekle(mid: str) -> None:
    gorulmus_yukle()
    _gorulmus_cache[mid] = datetime.now(timezone.utc).timestamp()  # type: ignore[index]
    gorulmus_kaydet()


# ─── İstatistik ────────────────────────────────────────────────
def istatistik_yukle() -> dict:
    global _istatistik_cache
    if _istatistik_cache is not None:
        return _istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "r") as f:
            _istatistik_cache = json.load(f)
    except Exception:
        _istatistik_cache = {
            "toplam": 0, "kanallar": {}, "gunluk": {},
            "kategoriler": {}, "magazalar": {},
        }
    return _istatistik_cache


def istatistik_kaydet() -> None:
    global _istatistik_cache
    try:
        with open(ISTATISTIK_FILE, "w") as f:
            json.dump(_istatistik_cache, f)
    except Exception:
        pass


def istatistik_guncelle(kanal_adi: str, magaza: str, kategori: str) -> None:
    global _ist_degisim_sayac
    ist = istatistik_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal_adi] = ist["kanallar"].get(kanal_adi, 0) + 1
    ist["magazalar"][magaza] = ist["magazalar"].get(magaza, 0) + 1
    ist["kategoriler"][kategori] = ist["kategoriler"].get(kategori, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    _ist_degisim_sayac += 1
    if _ist_degisim_sayac >= 10:
        istatistik_kaydet()
        _ist_degisim_sayac = 0
