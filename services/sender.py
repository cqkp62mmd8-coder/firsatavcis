"""
Gönderim servisi: kuyruk worker, tepki ekleme, kanal doğrulama.
"""
import asyncio
from io import BytesIO

from telethon import TelegramClient
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji, MessageMediaPhoto

from config.settings import HEDEF_KANAL, KUYRUK_BEKLEME
from utils.logger import log, gece_modu_aktif
from utils.image import logo_ekle
from core.storage import istatistik_guncelle

# Circular import yoktur; client dışarıdan inject edilir.


async def tepki_ekle(client: TelegramClient, mesaj) -> None:
    try:
        await client(SendReactionRequest(
            peer=HEDEF_KANAL,
            msg_id=mesaj.id,
            reaction=[ReactionEmoji(emoticon="🔥")],
        ))
    except Exception as e:
        log("UYARI", f"Tepki eklenemedi: {e}")


async def kanallari_dogrula(client: TelegramClient, kaynak_kanallar: list) -> list:
    gecerli = []
    log("BILGI", f"{len(kaynak_kanallar)} kanal doğrulanıyor...")
    for kanal in kaynak_kanallar:
        try:
            await client.get_entity(kanal)
            gecerli.append(kanal)
            log("OK", f"{kanal} aktif")
        except Exception as e:
            log("UYARI", f"{kanal} bulunamadı: {e}")
    log("BILGI", f"{len(gecerli)} kanal aktif")
    return gecerli


async def kuyruk_worker(
    client: TelegramClient,
    bot_client: TelegramClient | None,
    mesaj_kuyrugu: asyncio.Queue,
) -> None:
    log("BILGI", "Kuyruk worker aktif")
    while True:
        try:
            kuyruk_verisi = await mesaj_kuyrugu.get()
            sablon, gorsel_medya, link, magaza, kat_adi, kanal_adi, indirim = kuyruk_verisi[:7]
            fs_skor = kuyruk_verisi[7] if len(kuyruk_verisi) > 7 else 0.0

            sessiz = gece_modu_aktif()
            if sessiz:
                log("BILGI", "Gece modu aktif – sessiz bildirim")

            # ── Buton oluştur ──────────────────────────────────
            buton = None
            if link and bot_client:
                from telethon.tl.types import (
                    KeyboardButtonUrl, KeyboardButtonCallback,
                    KeyboardButtonRow, ReplyInlineMarkup,
                )
                buton = ReplyInlineMarkup(rows=[
                    KeyboardButtonRow(buttons=[
                        KeyboardButtonUrl(text="🔗 Fırsata Git", url=link),
                        KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
                        KeyboardButtonCallback(text="❌ Sahte İndirim", data=b"vote_fake"),
                    ])
                ])
            elif link:
                from telethon.tl.types import (
                    KeyboardButtonUrl, KeyboardButtonRow, ReplyInlineMarkup,
                )
                buton = ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[
                    KeyboardButtonUrl(text="🔗 Fırsata Git", url=link)
                ])])

            final_metin = sablon
            if link and not buton:
                final_metin = sablon + f"\n\n🔗 <a href='{link}'>Fırsata Git</a>"

            if mesaj_kuyrugu.full():
                log("UYARI", "Kuyruk dolu! Mesaj atlanıyor.")
                mesaj_kuyrugu.task_done()
                continue

            msg = None

            # ── Görsel gönder ──────────────────────────────────
            if gorsel_medya:
                try:
                    gorsel_bytes = await client.download_media(gorsel_medya, bytes)
                    if gorsel_bytes and len(gorsel_bytes) > 1000:
                        logolu = logo_ekle(gorsel_bytes)
                        buf = BytesIO(logolu)
                        buf.name = "urun.jpg"
                        if bot_client and link:
                            msg = await bot_client.send_message(
                                HEDEF_KANAL, final_metin,
                                file=buf, parse_mode="html", buttons=buton, silent=sessiz,
                            )
                        else:
                            msg = await client.send_message(
                                HEDEF_KANAL, final_metin,
                                file=buf, parse_mode="html", silent=sessiz,
                            )
                    else:
                        raise Exception("Görsel çok küçük")
                except Exception as img_e:
                    log("UYARI", f"Görsel: {img_e}")
                    if bot_client and link:
                        msg = await bot_client.send_message(
                            HEDEF_KANAL, final_metin, parse_mode="html", buttons=buton,
                        )
                    else:
                        msg = await client.send_message(HEDEF_KANAL, final_metin, parse_mode="html")
            else:
                if bot_client and link:
                    msg = await bot_client.send_message(
                        HEDEF_KANAL, final_metin, parse_mode="html", buttons=buton,
                    )
                else:
                    msg = await client.send_message(HEDEF_KANAL, final_metin, parse_mode="html")

            if msg:
                await tepki_ekle(client, msg)

            # Yüksek skorlu mesajları sabitle
            if msg and len(kuyruk_verisi) > 7 and kuyruk_verisi[7] >= 9.0:
                try:
                    await client.pin_message(HEDEF_KANAL, msg.id, notify=False)
                    log("OK", f"Yüksek skor mesaj sabitlendi: {kuyruk_verisi[7]}/10")
                except Exception as pin_e:
                    log("UYARI", f"Pin hatası: {pin_e}")

            istatistik_guncelle(kanal_adi, magaza, kat_adi)
            log("OK", f"Gönderildi [{magaza}] %{indirim} | Kuyrukta: {mesaj_kuyrugu.qsize()}")

            mesaj_kuyrugu.task_done()
            await asyncio.sleep(KUYRUK_BEKLEME)

        except Exception as e:
            log("HATA", f"Worker: {e}")
            await asyncio.sleep(5)
