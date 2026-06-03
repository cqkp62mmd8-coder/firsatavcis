"""
Günde bir kez, 12:00–19:59 arası rastgele saatte sürpriz fırsat gönderir.
"""
import asyncio
import random
from datetime import datetime, timedelta

from telethon import TelegramClient

import config
from services.analiz import kategori_bul
from services.kuyruk import tepki_ekle
from schedulers.gunluk import liste
from utils.log import log, simdi_tr


async def gonder(client: TelegramClient) -> None:
    urunler = liste()
    if not urunler:
        return
    uygun = [u for u in urunler if u["indirim"] >= 60] or urunler
    u = random.choice(uygun)
    _, ikon, _ = kategori_bul(u["metin"])
    mt = config.MAGAZA_HASHTAG.get(u["magaza"], "")
    kanal = config.HEDEF_KANAL.lstrip("@")

    satirlar = ["🎰 <b>GÜNLÜK SÜRPRİZ FIRSAT!</b>", "", "Her gün bir sürpriz fırsat — bugünkü sürpriz:", ""]
    satirlar.append(f"{ikon} <b>{u['urun'][:60]}</b>")

    # Gemini varsa sürprizi tanıtan kısa, çekici cümle ekle
    try:
        from utils import gemini
        if gemini.kullanilabilir() and u.get("urun"):
            loop = asyncio.get_running_loop()
            talimat = (
                f"'{u['urun'][:60]}' ürünü için bir 'günlük sürpriz fırsat' "
                "tanıtım cümlesi yaz. Tek cümle, en fazla 12 kelime, "
                "merak uyandıran ama abartısız. Sadece cümleyi yaz."
            )
            cumle = await loop.run_in_executor(None, gemini.kisa_metin, talimat, 40)
            if cumle and len(cumle) <= 130:
                satirlar.append(f"<i>{cumle}</i>")
    except Exception:
        pass

    satirlar.append("")
    if u["eski"] and u["yeni"]:
        satirlar += [f"🏷️ Normal:    <s>{u['eski']} TL</s>", f"💰 İndirimli: <b>{u['yeni']} TL</b>", ""]
    satirlar.append(f"🏪 {u['magaza']}  •  🔥 <b>%{u['indirim']} İNDİRİM</b>")
    satirlar += ["", f"#SürprizFırsat #GünlükFırsat {mt} #kacirmabak", f"📢 @{kanal}"]
    if u.get("link"):
        satirlar.append(f"\n🔗 <a href='{u['link']}'>Fırsata Git</a>")

    try:
        msg = await client.send_message(config.HEDEF_KANAL, "\n".join(satirlar), parse_mode="html")
        if msg:
            await tepki_ekle(client, msg)
        log("OK", f"Sürpriz fırsat: {u['urun'][:40]}")
    except Exception as e:
        log("HATA", f"Sürpriz fırsat: {e}")


async def zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = simdi_tr()
        hedef = simdi.replace(
            hour=random.randint(12, 19),
            minute=random.randint(0, 59),
            second=0, microsecond=0,
        )
        if simdi >= hedef:
            hedef = (simdi + timedelta(days=1)).replace(
                hour=random.randint(12, 19),
                minute=random.randint(0, 59),
                second=0, microsecond=0,
            )
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Sürpriz fırsat: {hedef.strftime('%H:%M')} için bekleniyor")
        await asyncio.sleep(bekle)
        await gonder(client)
