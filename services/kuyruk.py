"""
Kuyruk worker: kuyruktaki mesajları 3 dakika arayla kanala gönderir.
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



# ── Buton fabrikası ─────────────────────────────────────────────

def _buton_olustur(link: str, bot_client_var: bool):
    from telethon.tl.types import (
        KeyboardButtonUrl, KeyboardButtonCallback,
        KeyboardButtonRow, ReplyInlineMarkup,
    )
    if bot_client_var:
        return ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text="🔗 Fırsata Git",    url=link),
            KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
            KeyboardButtonCallback(text="❌ Sahte İndirim", data=b"vote_fake"),
        ])])
    return ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[
        KeyboardButtonUrl(text="🔗 Fırsata Git", url=link),
    ])])


# ── Gönderim (retry destekli) ───────────────────────────────────

async def _gonder_retry(gonderi_client, hedef, metin, **kw):
    """Exponential backoff ile en fazla _MAX_RETRY kez dener."""
    son_hata = None
    for attempt in range(_MAX_RETRY):
        try:
            return await gonderi_client.send_message(hedef, metin, **kw)
        except Exception as e:
            son_hata = e
            if attempt < _MAX_RETRY - 1:
                bekle = 5 * (2 ** attempt)   # 5 → 10 → 20 sn
                log("UYARI", f"Gönderim hatası ({attempt+1}/{_MAX_RETRY}): {e} — {bekle}s bekleniyor")
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
            sablon, gorsel_medya, link, magaza, kat, kanal_adi, indirim = veri[:7]
            fs_skor = veri[7] if len(veri) > 7 else 0.0

            # FIX: Duraklatma kontrolü mesaj alındıktan sonra yapılır;
            # mesajı atmak yerine kısa bekleyip tekrar deneriz.
            while state.durduruldu:
                log("BILGI", "Bot duraklatıldı — worker bekliyor…")
                await asyncio.sleep(15)

            sessiz = gece_modu_aktif()
            if sessiz:
                log("BILGI", "Gece modu – sessiz bildirim")

            buton = _buton_olustur(link, bool(bot_client)) if link else None
            metin = sablon if buton else (sablon + f"\n\n🔗 <a href='{link}'>Fırsata Git</a>" if link else sablon)

            # ── Gönder ──────────────────────────────────────────
            msg = None
            gonderi_client = bot_client if (bot_client and link) else client

            if gorsel_medya:
                try:
                    raw = await client.download_media(gorsel_medya, bytes)
                    if not raw or len(raw) < 1_000:
                        raise ValueError("Görsel çok küçük")
                    buf = BytesIO(logo_ekle(raw))
                    buf.name = "urun.jpg"
                    kw = dict(file=buf, parse_mode="html", silent=sessiz)
                    if bot_client and link:
                        kw["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw)
                except Exception as e:
                    log("UYARI", f"Görsel gönderilemedi, metinle devam: {e}")
                    kw2 = dict(parse_mode="html")
                    if bot_client and link:
                        kw2["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw2)
            else:
                kw3 = dict(parse_mode="html")
                if bot_client and link:
                    kw3["buttons"] = buton
                msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw3)

            if msg:
                await tepki_ekle(client, msg)

            # Yüksek skor → sabitle
            if msg and fs_skor >= 9.0:
                try:
                    await client.pin_message(config.HEDEF_KANAL, msg.id, notify=False)
                    log("OK", f"Sabitlendi (skor {fs_skor}/10)")
                except Exception as e:
                    log("UYARI", f"Pin hatası: {e}")

            ist_guncelle(kanal_adi, magaza, kat)
            log("OK", f"Gönderildi [{magaza}] %{indirim} | kuyruk={kuyruk.qsize()}")

            kuyruk.task_done()
            await asyncio.sleep(config.KUYRUK_BEKLEME)

        except Exception as e:
            log("HATA", f"Worker: {e}")
            await asyncio.sleep(10)
