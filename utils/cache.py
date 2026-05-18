"""
Görülmüş (duplikat önleme) ve istatistik JSON kalıcı önbelleği.
Tüm okuma/yazma işlemleri bu modül üzerinden yapılır.
"""
import json
from datetime import datetime, timezone

import config
from utils.log import log

# ── İç durum ────────────────────────────────────────────────────
_gorulmus: dict[str, float] | None = None
_istatistik: dict | None = None
_ist_degisim: int = 0


# ════════════════════════════════════════════════════════════════
# Görülmüş
# ════════════════════════════════════════════════════════════════
def _gorulmus_yukle() -> dict[str, float]:
    global _gorulmus
    if _gorulmus is None:
        try:
            with open(config.GORULMUS_FILE) as f:
                _gorulmus = json.load(f)
        except Exception:
            _gorulmus = {}
    return _gorulmus


def _gorulmus_kaydet() -> None:
    if _gorulmus is None:
        return
    try:
        kayit = _gorulmus
        if len(kayit) > config.GORULMUS_MAX:
            kayit = dict(sorted(kayit.items(), key=lambda x: x[1], reverse=True)[: config.GORULMUS_MAX])
            _gorulmus.clear()
            _gorulmus.update(kayit)
        with open(config.GORULMUS_FILE, "w") as f:
            json.dump(_gorulmus, f)
    except Exception as e:
        log("HATA", f"görülmüş kaydetme: {e}")


def gorulmus_var_mi(mid: str) -> bool:
    return mid in _gorulmus_yukle()


def gorulmus_ekle(mid: str) -> None:
    _gorulmus_yukle()[mid] = datetime.now(timezone.utc).timestamp()
    _gorulmus_kaydet()


def gorulmus_temizle() -> None:
    g = _gorulmus_yukle()
    simdi = datetime.now(timezone.utc).timestamp()
    onceki = len(g)
    eskiler = [k for k, v in g.items() if simdi - v >= config.GORULMUS_TTL]
    for k in eskiler:
        del g[k]
    if len(g) > config.GORULMUS_MAX:
        fazla = sorted(g.items(), key=lambda x: x[1])[: len(g) - config.GORULMUS_MAX]
        for k, _ in fazla:
            del g[k]
    temizlenen = onceki - len(g)
    if temizlenen > 0:
        log("BILGI", f"{temizlenen} eski görülmüş kaydı temizlendi")
    _gorulmus_kaydet()


# ════════════════════════════════════════════════════════════════
# İstatistik
# ════════════════════════════════════════════════════════════════
def ist_yukle() -> dict:
    global _istatistik
    if _istatistik is None:
        try:
            with open(config.ISTATISTIK_FILE) as f:
                _istatistik = json.load(f)
        except Exception:
            _istatistik = {
                "toplam": 0,
                "kanallar": {},
                "gunluk": {},
                "kategoriler": {},
                "magazalar": {},
            }
    return _istatistik


def ist_kaydet() -> None:
    # FIX: None guard eklendi — başlatılmamışsa yazmaya çalışma
    if _istatistik is None:
        return
    try:
        with open(config.ISTATISTIK_FILE, "w") as f:
            json.dump(_istatistik, f)
    except Exception as e:
        log("HATA", f"istatistik kaydetme: {e}")


def ist_guncelle(kanal: str, magaza: str, kategori: str) -> None:
    global _ist_degisim
    ist = ist_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal]       = ist["kanallar"].get(kanal, 0) + 1
    ist["magazalar"][magaza]     = ist["magazalar"].get(magaza, 0) + 1
    ist["kategoriler"][kategori] = ist["kategoriler"].get(kategori, 0) + 1
    bugun = datetime.now().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    _ist_degisim += 1
    if _ist_degisim >= 10:
        ist_kaydet()
        _ist_degisim = 0
