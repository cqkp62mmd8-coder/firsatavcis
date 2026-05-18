"""Tarihli loglama ve gece modu kontrolü."""
from datetime import datetime


def log(seviye: str, mesaj: str) -> None:
    zaman = datetime.now().strftime("%H:%M:%S")
    print(f"[{zaman}] [{seviye}] {mesaj}", flush=True)


def gece_modu_aktif() -> bool:
    """23:00–08:00 arası gece modu (sessiz bildirim)."""
    saat = datetime.now().hour
    return saat >= 23 or saat < 8
