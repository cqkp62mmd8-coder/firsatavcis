"""
═══════════════════════════════════════════════════════════════════════
Sahte İndirim Tespiti — heuristik kurallar + mağaza geçmişi
═══════════════════════════════════════════════════════════════════════
"""
import collections
import json
import os
from typing import Optional

import config
from utils.log import log

_GECMIS_FILE = os.path.join(config.DATA_DIR, "indirim_gecmisi.json")
_MAKS_GECMIS = 100

_magaza_gecmis: dict[str, list[int]] = collections.defaultdict(list)
_yuklendi = False


def _yukle() -> None:
    global _magaza_gecmis, _yuklendi
    if _yuklendi:
        return
    if os.path.exists(_GECMIS_FILE):
        try:
            with open(_GECMIS_FILE, encoding="utf-8") as f:
                _magaza_gecmis = collections.defaultdict(list, json.load(f))
        except Exception as e:
            log("UYARI", f"İndirim geçmişi yükle: {e}")
    _yuklendi = True


def _kaydet() -> None:
    try:
        os.makedirs(os.path.dirname(_GECMIS_FILE) or ".", exist_ok=True)
        gecici = _GECMIS_FILE + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(dict(_magaza_gecmis), f, ensure_ascii=False)
        os.replace(gecici, _GECMIS_FILE)
    except Exception as e:
        log("UYARI", f"İndirim geçmişi kaydet: {e}")


def _ortalama(liste: list[int]) -> float:
    return sum(liste) / len(liste) if liste else 0.0


def sahte_mi(eski_fiyat: Optional[float], yeni_fiyat: Optional[float],
             indirim: int, magaza: str = "") -> tuple[bool, str]:
    """Sahte indirim mi? Döner: (sahte_mi, sebep)."""
    _yukle()

    if indirim >= 95:
        return True, f"sahte: %{indirim} indirim — gerçekçi değil"

    if eski_fiyat and yeni_fiyat and yeni_fiyat > 0:
        oran = eski_fiyat / yeni_fiyat
        if oran > 50:
            return True, f"sahte: fiyat oranı {oran:.0f}x"

    if yeni_fiyat is not None and 0 < yeni_fiyat < 10 and eski_fiyat and eski_fiyat > 100:
        return True, f"sahte: yeni fiyat {yeni_fiyat} TL aşırı düşük"

    if magaza:
        gecmis = _magaza_gecmis.get(magaza, [])
        if len(gecmis) >= 20:
            ort = _ortalama(gecmis)
            if indirim > ort * 2.5 and indirim > 70:
                return True, (f"şüpheli: {magaza} ortalama %{ort:.0f}, "
                              f"bu mesaj %{indirim}")

    return False, ""


def gecmise_ekle(magaza: str, indirim: int) -> None:
    _yukle()
    if not magaza or indirim < 0:
        return
    _magaza_gecmis[magaza].append(indirim)
    if len(_magaza_gecmis[magaza]) > _MAKS_GECMIS:
        _magaza_gecmis[magaza] = _magaza_gecmis[magaza][-_MAKS_GECMIS:]
    if hash(magaza) % 25 == 0:
        _kaydet()


def magaza_profili(magaza: str) -> dict:
    _yukle()
    gecmis = _magaza_gecmis.get(magaza, [])
    if not gecmis:
        return {"magaza": magaza, "ornek": 0}
    return {
        "magaza": magaza, "ornek": len(gecmis),
        "ortalama": round(_ortalama(gecmis), 1),
        "min": min(gecmis), "maks": max(gecmis), "son_5": gecmis[-5:],
    }


def tum_magaza_profilleri() -> list[dict]:
    _yukle()
    return [magaza_profili(m) for m in sorted(_magaza_gecmis.keys())]
