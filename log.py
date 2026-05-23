"""
Python standart logging modülü tabanlı log sistemi.

Seviyeler: DEBUG / INFO / WARNING / ERROR / CRITICAL
LOG_SEVIYE env var ile (default INFO).

Geriye dönük uyumluluk için log(seviye, mesaj) imzası korundu —
ama artık altta gerçek logging modülünü çağırıyor.

Türkiye saati ile timestamp atılır.
"""
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

# ── Türkiye saati ───────────────────────────────────────────────
TR_TZ = timezone(timedelta(hours=3))


def simdi_tr() -> datetime:
    return datetime.now(TR_TZ)


class _TRFormatter(logging.Formatter):
    """Log timestamp'lerini TR saati ile basar."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=TR_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%H:%M:%S")


# ── Root logger kurulumu ────────────────────────────────────────
_LOG_SEVIYE_AD = os.environ.get("LOG_SEVIYE", "INFO").upper()
_LOG_SEVIYE = getattr(logging, _LOG_SEVIYE_AD, logging.INFO)

_logger = logging.getLogger("firsatpulsu")
_logger.setLevel(_LOG_SEVIYE)
_logger.propagate = False

# Aynı modül 2 kez import edilirse handler eklenmesin
if not _logger.handlers:
    _formatter = _TRFormatter("[%(asctime)s] [%(levelname)s] %(message)s")
    _stream = logging.StreamHandler(sys.stdout)
    _stream.setFormatter(_formatter)
    _logger.addHandler(_stream)


# ── Eski log() API'si — uyumluluk için korundu ──────────────────
# Eski seviye isimleri → standart logging level
_SEVIYE_HARITA = {
    "DEBUG":     logging.DEBUG,
    "BILGI":     logging.INFO,
    "OK":        logging.INFO,
    "TEST":      logging.INFO,
    "ADMIN":     logging.INFO,
    "LLM":       logging.INFO,
    "FILTRE":    logging.INFO,
    "SISTEM":    logging.INFO,
    "INFO":      logging.INFO,
    "UYARI":     logging.WARNING,
    "WARNING":   logging.WARNING,
    "HATA":      logging.ERROR,
    "ERROR":     logging.ERROR,
    "KRITIK":    logging.CRITICAL,
    "CRITICAL":  logging.CRITICAL,
}


def log(seviye: str, mesaj: str) -> None:
    """Eski API — yeni kodlarda doğrudan logging modülü tercih edilmeli."""
    lvl = _SEVIYE_HARITA.get(seviye.upper(), logging.INFO)
    _logger.log(lvl, f"[{seviye}] {mesaj}")


# ── Gece modu ───────────────────────────────────────────────────
def gece_modu_aktif() -> bool:
    """23:00–08:00 arası gece modu — sessiz bildirim."""
    return simdi_tr().hour >= 23 or simdi_tr().hour < 8
