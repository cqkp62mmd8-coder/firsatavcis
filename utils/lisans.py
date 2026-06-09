"""utils/lisans.py — Lisans anahtarı üretimi ve doğrulaması (v23.39).

İmzalı anahtar = base64(payload).hmac_imza. Payload alıcı, üretim ve bitiş
tarihini taşır. Bot, gömülü gizli anahtarla imzayı doğrular.

DÜRÜST NOT: Kendi-barındırılan (self-hosted) Python kodunda mutlak koruma
yoktur; alıcı kaynağı görüp denetimi devre dışı bırakabilir. Bu sistem
caydırıcıdır + sahiplik kanıtıdır + süre/sürüm sınırı sağlar. Daha güçlü koruma
için çevrimiçi etkinleştirme (sunucu) gerekir; o da kendi maliyet ve tek-arıza
noktasını getirir.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import time

# Satıcı bu gizli anahtarı DEĞİŞTİRİR ve gizli tutar. Üretici script ile bot
# aynı anahtarı kullanır. Env ile de verilebilir (LISANS_GIZLI).
_GIZLI = (os.environ.get("LISANS_GIZLI")
          or "FIRSATPULSU-LISANS-GIZLI-ANAHTAR-DEGISTIRIN").encode()


def _imzala(ham: str, gizli: bytes) -> str:
    return hmac.new(gizli, ham.encode(), hashlib.sha256).hexdigest()[:32]


def uret(alici: str, gun: int = 365, gizli: bytes | None = None) -> str:
    """Bir lisans anahtarı üret (SATICI tarafı)."""
    g = gizli or _GIZLI
    payload = {
        "alici": alici,
        "uretim": int(time.time()),
        "bitis": int(time.time()) + int(gun) * 86400,
    }
    ham = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    return f"{ham}.{_imzala(ham, g)}"


def dogrula(anahtar: str, gizli: bytes | None = None) -> tuple[bool, dict]:
    """Lisans anahtarını doğrula. (gecerli, bilgi) döndürür."""
    g = gizli or _GIZLI
    if not anahtar or "." not in anahtar:
        return False, {"hata": "biçim"}
    try:
        ham, imza = anahtar.strip().split(".", 1)
        if not hmac.compare_digest(imza, _imzala(ham, g)):
            return False, {"hata": "imza"}
        pad = "=" * (-len(ham) % 4)
        payload = json.loads(base64.urlsafe_b64decode(ham + pad))
    except Exception:
        return False, {"hata": "biçim"}
    if payload.get("bitis", 0) < time.time():
        return False, {"hata": "süresi doldu", **payload}
    return True, payload


def kalan_gun(payload: dict) -> int:
    """Lisansın bitişine kalan gün sayısı."""
    try:
        return max(0, int((payload.get("bitis", 0) - time.time()) // 86400))
    except Exception:
        return 0
