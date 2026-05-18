"""
Watchdog: saatte bir admin'e durum raporu gönderir,
görülmüş önbelleğini temizler, istatistiği diske yazar.
"""
import asyncio
from datetime import datetime

from telethon import TelegramClient

import config
from utils.cache import ist_yukle, ist_kaydet, gorulmus_temizle
from utils.log import log, simdi_tr


async def admin_bildir(client: TelegramClient, mesaj: str) -> None:
    if not config.ADMIN_ID:
        return
    try:
        await client.send_message(int(config.ADMIN_ID), f"FırsatPulsu:\n{mesaj}")
    except Exception:
        pass


async def kanal_dogrula(client: TelegramClient) -> list[str]:
    """Geçersiz kanalları listeden çıkarır, geçerli listeyi döndürür."""
    gecerli = []
    log("BILGI", f"{len(config.KAYNAK_KANALLAR)} kanal doğrulanıyor…")
    for kanal in config.KAYNAK_KANALLAR:
        try:
            await client.get_entity(kanal)
            gecerli.append(kanal)
            log("OK", f"{kanal} aktif")
        except Exception as e:
            log("UYARI", f"{kanal} bulunamadı: {e}")
    log("BILGI", f"{len(gecerli)} kanal aktif")
    return gecerli


async def calistir(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    while True:
        await asyncio.sleep(config.WATCHDOG_ARALIK)
        ist = ist_yukle()
        bugun = simdi_tr().strftime("%Y-%m-%d")
        await admin_bildir(
            client,
            f"✅ Bot çalışıyor\n"
            f"Bugün: {ist.get('gunluk', {}).get(bugun, 0)}\n"
            f"Toplam: {ist.get('toplam', 0)}\n"
            f"Kuyruk: {kuyruk.qsize()}",
        )
        gorulmus_temizle()
        ist_kaydet()
