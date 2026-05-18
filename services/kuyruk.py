"""
Kuyruk worker: kuyruktaki mesajları bekleyerek kanala gönderir.
lnk: str (tek ürün) veya list[tuple[str,str]] (çift ürün → 2 inline buton)
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

def _buton_olustur(link, bot_client_var: bool):
    """link: str (tek) veya list[tuple[url, ad]] (çift ürün)."""
    from telethon.tl.types import (
        KeyboardButtonUrl, KeyboardButtonCallback,
        KeyboardButtonRow, ReplyInlineMarkup,
    )

    satirlar = []

    if isinstance(link, list):
        # Çift ürün — her ürün için ayrı satır
        for url, ad in link:
            if url:
                satirlar.append(KeyboardButtonRow(buttons=[
                    KeyboardButtonUrl(text=f"🔗 {ad}", url=url),
                ]))
        if bot_client_var:
            satirlar.append(KeyboardButtonRow(buttons=[
                KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
                KeyboardButtonCallback(text="❌ Sahte İndirim",  data=b"vote_fake"),
            ]))
    else:
        # Tek ürün
        if bot_client_var:
            satirlar.append(KeyboardButtonRow(buttons=[
                KeyboardButtonUrl(text="🔗 Fırsata Git",    url=link),
                KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
                KeyboardButtonCallback(text="❌ Sahte İndirim",  data=b"vote_fake"),
            ]))
        else:
            satirlar.append(KeyboardButtonRow(buttons=[
                KeyboardButtonUrl(text="🔗 Fırsata Git", url=link),
            ]))

    return ReplyInlineMarkup(rows=satirlar) if satirlar else None


# ── Gönderim (retry destekli) ───────────────────────────────────

async def _gonder_retry(gonderi_client, hedef, metin, **kw):
    son_hata = None
    for attempt in range(_MAX_RETRY):
        try:
            return await gonderi_client.send_message(hedef, metin, **kw)
        except Exception as e:
            son_hata = e
            if attempt < _MAX_RETRY - 1:
                bekle = 5 * (2 ** attempt)
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

            while state.durduruldu:
                log("BILGI", "Bot duraklatıldı — worker bekliyor…")
                await asyncio.sleep(15)

            sessiz = gece_modu_aktif()
            if sessiz:
                log("BILGI", "Gece modu – sessiz bildirim")

            buton = _buton_olustur(link, bool(bot_client)) if link else None

            # Metin + link: buton varsa sadece sablon, yoksa link satırı ekle
            if buton:
                metin = sablon
            elif isinstance(link, list):
                ekler = "\n".join(f"🔗 <a href='{u}'>{ad}</a>" for u, ad in link if u)
                metin = sablon + "\n\n" + ekler if ekler else sablon
            elif link:
                metin = sablon + f"\n\n🔗 <a href='{link}'>Fırsata Git</a>"
            else:
                metin = sablon

            gonderi_client = bot_client if (bot_client and link) else client

            # ── Görsel ile gönder ────────────────────────────────
            msg = None
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
