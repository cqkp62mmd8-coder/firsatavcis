"""
Her Pazar 20:00'de haftalık istatistik raporu gönderir.
"""
import asyncio
from datetime import datetime, timedelta

from telethon import TelegramClient

import config
from services.kuyruk import tepki_ekle
from utils.cache import ist_yukle, ist_kaydet
from utils.log import log


async def gonder(client: TelegramClient) -> None:
    ist = ist_yukle()
    ist_kaydet()
    simdi = datetime.now()
    haftalik = sum(
        ist.get("gunluk", {}).get((simdi - timedelta(days=i)).strftime("%Y-%m-%d"), 0)
        for i in range(7)
    )
    kategoriler = ist.get("kategoriler", {})
    magazalar   = ist.get("magazalar", {})
    en_kat = max(kategoriler, key=kategoriler.get) if kategoriler else "genel"
    en_mag = max(magazalar,   key=magazalar.get)   if magazalar   else "Bilinmiyor"
    kanal  = config.HEDEF_KANAL.lstrip("@")

    satirlar = [
        "📊 <b>HAFTALIK FIRSAT RAPORU</b>", "",
        f"Bu hafta <b>{haftalik} fırsat</b> paylaştık!", "",
        f"🏆 En popüler kategori: <b>{config.KATEGORI_YAZI.get(en_kat, en_kat)}</b>",
        f"🏪 En çok paylaşılan: <b>{en_mag}</b>",
        f"📈 Toplam: <b>{ist.get('toplam', 0)} fırsat</b>", "",
        "Bildirimleri açık tutun! 🔔", "",
        "#HaftalıkRapor #FırsatPulsu",
        f"📢 @{kanal}",
    ]
    try:
        msg = await client.send_message(config.HEDEF_KANAL, "\n".join(satirlar), parse_mode="html")
        if msg:
            await tepki_ekle(client, msg)
        log("OK", "Haftalık rapor gönderildi")
    except Exception as e:
        log("HATA", f"Haftalık rapor: {e}")


async def zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = datetime.now()
        gunler = (6 - simdi.weekday()) % 7
        if gunler == 0 and simdi.hour >= 20:
            gunler = 7
        hedef = (simdi + timedelta(days=gunler)).replace(hour=20, minute=0, second=0, microsecond=0)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Haftalık rapor: {int(bekle // 3600)}s sonra")
        await asyncio.sleep(bekle)
        await gonder(client)
