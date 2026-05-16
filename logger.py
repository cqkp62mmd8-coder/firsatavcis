from datetime import datetime


def gece_modu_aktif() -> bool:
    saat = datetime.now().hour
    return saat >= 23 or saat < 8


def log(seviye: str, mesaj: str) -> None:
    zaman = datetime.now().strftime("%H:%M:%S")
    print(f"[{zaman}] [{seviye}] {mesaj}")
