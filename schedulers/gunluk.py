"""
21:00'de günün en iyi 3 fırsatını gönderir.
"""
import asyncio
from datetime import datetime, timedelta

from telethon import TelegramClient

import config
from services.analiz import kategori_bul, fiyat_bul, link_bul, urun_adi_bul, magaza_bul
from services.kuyruk import tepki_ekle
from utils.log import log

# Bellek içi günlük liste (en fazla 20 kayıt)
_urunler: list[dict] = []


def ekle(metin: str, indirim: int, buton_linkleri: list[str]) -> None:
    e, y, _, _ = fiyat_bul(metin)
    _urunler.append({
        "metin":   metin,
        "indirim": indirim,
        "link":    link_bul(metin, buton_linkleri),
        "urun":    urun_adi_bul(metin) or "Ürün",
        "magaza":  magaza_bul(metin),
        "eski":    e,
        "yeni":    y,
    })
    _urunler.sort(key=lambda x: x["indirim"], reverse=True)
    del _urunler[20:]


def liste() -> list[dict]:
    # FIX: kopya döndür — dış kod iç listeyi değiştiremez
    return list(_urunler)


async def gonder(client: TelegramClient) -> None:
    if not _urunler:
        log("BILGI", "21:00 – paylaşılacak ürün yok")
        return
    en_iyi = _urunler[:3]
    log("BILGI", f"21:00 – {len(en_iyi)} ürün gönderiliyor")

    try:
        await client.send_message(
            config.HEDEF_KANAL,
            "🏆 <b>GÜNÜN EN İYİ FIRSATLARI</b> 🏆\n\nBugün yakalanan en yüksek indirimli ürünler:",
            parse_mode="html",
        )
        await asyncio.sleep(3)
    except Exception as e:
        log("HATA", f"Başlık: {e}")

    for i, u in enumerate(en_iyi, 1):
        madalya = ["🥇", "🥈", "🥉"][i - 1]
        _, ikon, _ = kategori_bul(u["metin"])
        mt = config.MAGAZA_HASHTAG.get(u["magaza"], "")
        kanal = config.HEDEF_KANAL.lstrip("@")

        satirlar = [f"{madalya} <b>{i}. FIRSAT — %{u['indirim']} İNDİRİM</b>", ""]
        satirlar.append(f"{ikon} {u['urun'][:60]}")
        satirlar.append("")
        if u["eski"] and u["yeni"]:
            satirlar += [f"🏷️ Normal:    <s>{u['eski']} TL</s>", f"💰 İndirimli: <b>{u['yeni']} TL</b>", ""]
        satirlar += [f"🏪 {u['magaza']}", "", f"#GününFırsatı {mt} #FırsatPulsu", f"📢 @{kanal}"]
        if u.get("link"):
            satirlar.append(f"\n🔗 <a href='{u['link']}'>Fırsata Git</a>")

        try:
            msg = await client.send_message(config.HEDEF_KANAL, "\n".join(satirlar), parse_mode="html")
            if msg:
                await tepki_ekle(client, msg)
            await asyncio.sleep(5)
        except Exception as e:
            log("HATA", f"Günün ürünü {i}: {e}")

    _urunler.clear()
    log("BILGI", "21:00 – tamamlandı")


async def zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = datetime.now()
        hedef = simdi.replace(hour=21, minute=0, second=0, microsecond=0)
        if simdi >= hedef:
            hedef += timedelta(days=1)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Günlük özet: {int(bekle // 3600)}s {int((bekle % 3600) // 60)}dk sonra")
        await asyncio.sleep(bekle)
        await gonder(client)
