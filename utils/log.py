"""Tarihli loglama, gece modu kontrolü ve Türkiye saatine sabit zaman."""
from datetime import datetime, timezone, timedelta

# Türkiye sabit UTC+3 (yıl boyunca, DST yok)
TR_TZ = timezone(timedelta(hours=3))


def simdi_tr() -> datetime:
    """Türkiye saatine göre şu an."""
    return datetime.now(TR_TZ)


def log(seviye: str, mesaj: str) -> None:
    zaman = simdi_tr().strftime("%H:%M:%S")
    print(f"[{zaman}] [{seviye}] {mesaj}", flush=True)


def gece_modu_aktif() -> bool:
    """23:00–08:00 arası (Türkiye saati) gece modu — sessiz bildirim."""
    return simdi_tr().hour >= 23 or simdi_tr().hour < 8
