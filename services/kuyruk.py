"""
Kuyruk worker: kuyruktaki mesajları 3 dakika arayla kanala gönderir.
Tuple formatı: (sablon, gorsel, lnk, magaza, kat, kanal_adi, indirim, fs, extra_lnk?)
  extra_lnk → varsa 2. ürün butonu eklenir (çoklu fırsat mesajları)
"""
import asyncio
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

import config
import state
from services.gorsel import logo_ekle
from utils.cache import ist_guncelle
from utils.log import log, gece_modu_aktif

_MAX_RETRY = 3


# ── Tepki ───────────────────────────────────────────────────────

async def tepki_ekle(client: TelegramClient, mesaj) -> None:
    try:
        await client(SendReactionRequest(
            peer=config.HEDEF_KANAL,
            msg_id=mesaj.id,
            reaction=[ReactionEmoji(emoticon="🔥")],
        ))
    except Exception as e:
        log("UYARI", f"Tepki eklenemedi: {e}")


# ── Buton fabrikası ─────────────────────────────────────────────

def _buton_olustur(link: str, bot_client_var: bool, extra_lnk: str | None = None):
    from telethon.tl.types import (
        KeyboardButtonUrl, KeyboardButtonCallback,
        KeyboardButtonRow, ReplyInlineMarkup,
    )
    satirlar = []

    if extra_lnk:
        # Çoklu ürün: her ürüne ayrı buton, yan yana
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text="1️⃣ Ürün 1", url=link),
            KeyboardButtonUrl(text="2️⃣ Ürün 2", url=extra_lnk),
        ]))
    else:
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text="🔗 Fırsata Git", url=link),
        ]))

    if bot_client_var:
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
            KeyboardButtonCallback(text="❌ Sahte İndirim", data=b"vote_fake"),
        ]))

    return ReplyInlineMarkup(rows=satirlar)


# ── Retry ───────────────────────────────────────────────────────

async def _gonder_retry(gonderi_client, hedef, metin, **kw):
    son_hata = None
    for attempt in range(_MAX_RETRY):
        try:
            return await gonderi_client.send_message(hedef, metin, **kw)
        except Exception as e:
            son_hata = e
            if attempt < _MAX_RETRY - 1:
                bekle = 5 * (2 ** attempt)
                log("UYARI", f"Gönderim hatası ({attempt+1}/{_MAX_RETRY}): {e} — {bekle}s")
                await asyncio.sleep(bekle)
    raise son_hata


# ── Worker ──────────────────────────────────────────────────────

async def worker(
    client: TelegramClient,
    bot_client: TelegramClient | None,
    kuyruk: asyncio.Queue,
) -> None:
    log("BILGI", "Kuyruk worker başladı")
    while True:
        try:
            veri = await kuyruk.get()
            sablon, gorsel_medya, lnk_giris, magaza, kat, kanal_adi, indirim = veri[:7]
            fs_skor = veri[7] if len(veri) > 7 else 0.0

            # Link tek string ya da liste olabilir → normalize
            if isinstance(lnk_giris, (list, tuple)):
                linkler = [l for l in lnk_giris if l]
            elif lnk_giris:
                linkler = [lnk_giris]
            else:
                linkler = []
            lnk       = linkler[0] if linkler else None
            extra_lnk = linkler[1] if len(linkler) > 1 else None

            while state.durduruldu:
                log("BILGI", "Gece modu / duraklama — worker bekliyor…")
                await asyncio.sleep(15)

            sessiz = gece_modu_aktif()
            buton  = _buton_olustur(lnk, bool(bot_client), extra_lnk) if lnk else None

            # Bot yoksa ya da link yoksa, link metne göm
            if lnk and not buton:
                metin = sablon + f"\n\n🔗 <a href='{lnk}'>Fırsata Git</a>"
            else:
                metin = sablon

            msg = None
            gonderi_client = bot_client if (bot_client and lnk) else client

            if gorsel_medya:
                try:
                    raw = await client.download_media(gorsel_medya, bytes)
                    if not raw or len(raw) < 1_000:
                        raise ValueError("Görsel çok küçük")
                    buf = BytesIO(logo_ekle(raw))
                    buf.name = "urun.jpg"
                    kw = dict(file=buf, parse_mode="html", silent=sessiz)
                    if buton:
                        kw["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw)
                except Exception as e:
                    log("UYARI", f"Görsel gönderilemedi, metinle devam: {e}")
                    kw2 = dict(parse_mode="html")
                    if buton:
                        kw2["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw2)
            else:
                kw3 = dict(parse_mode="html")
                if buton:
                    kw3["buttons"] = buton
                msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw3)

            if msg:
                await tepki_ekle(client, msg)

            if msg and fs_skor >= 9.0:
                try:
                    await client.pin_message(config.HEDEF_KANAL, msg.id, notify=False)
                    log("OK", f"Sabitlendi (skor {fs_skor}/10)")
                except Exception as e:
                    log("UYARI", f"Pin hatası: {e}")

            ist_guncelle(kanal_adi, magaza, kat)
            tip = "çoklu" if extra_lnk else "tekli"
            log("OK", f"Gönderildi [{magaza}] %{indirim} ({tip}) | kuyruk={kuyruk.qsize()}")

            kuyruk.task_done()
            await asyncio.sleep(config.KUYRUK_BEKLEME)

        except Exception as e:
            log("HATA", f"Worker: {e}")
            await asyncio.sleep(10)
