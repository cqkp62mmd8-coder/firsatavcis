"""
Kaynak kanallardan gelen yeni mesajları dinler,
filtreler ve işleme kuyruğuna ekler.
Çok ürünlü mesajları otomatik olarak böler.
"""
import asyncio

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto

import config
import state
from services.analiz import (
    markdown_temizle, benzerlik_anahtari,
    indirim_oranini_bul, kalite_skoru, magaza_bul,
    kategori_bul, marka_spam_kontrol, firsat_skoru, link_bul,
    mesaj_bolum_ayir,
)
from services.sablon import olustur as sablon_olustur
from schedulers.gunluk import ekle as gunluk_ekle
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


async def _isle(
    blok: str,
    gorsel,
    btn_links: list[str],
    kanal_adi: str,
    kuyruk: asyncio.Queue,
) -> None:
    """Tek bir ürün bloğunu filtreler ve kuyruğa ekler."""

    if any(yasak in blok.lower() for yasak in config.KARA_LISTE):
        return

    indirim = indirim_oranini_bul(blok)
    if indirim < config.MIN_INDIRIM:
        return

    mid = benzerlik_anahtari(blok)
    if gorulmus_var_mi(mid):
        return
    gorulmus_ekle(mid)

    lnk = link_bul(blok, btn_links)
    if not lnk:
        return

    skor = kalite_skoru(blok, indirim, btn_links)
    if skor < config.MIN_KALITE:
        log("BILGI", f"Düşük kalite (skor={skor}) atlandı")
        return

    magaza = magaza_bul(blok)
    if marka_spam_kontrol(magaza):
        log("BILGI", f"{magaza} spam limiti – atlandı")
        return

    sablon = sablon_olustur(blok, indirim, btn_links)
    if not sablon:
        return

    gunluk_ekle(blok, indirim, btn_links)

    kat, _, _ = kategori_bul(blok)
    fs = firsat_skoru(blok, indirim, btn_links)

    try:
        kuyruk.put_nowait((sablon, gorsel, lnk, magaza, kat, kanal_adi, indirim, fs))
        log("BILGI", f"Kuyruğa eklendi [{magaza}] %{indirim} | kuyruk={kuyruk.qsize()}")
    except asyncio.QueueFull:
        log("UYARI", f"Kuyruk dolu, mesaj atıldı [{magaza}] %{indirim}")


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    """Handler'ı client'a bağlar. main.py'den bir kez çağrılır."""

    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            if state.durduruldu:
                return

            ham = markdown_temizle(event.message.text or "")

            # Buton linkleri (tüm ürünlere paylaşılır)
            btn_links: list[str] = []
            try:
                if event.message.buttons:
                    for row in event.message.buttons:
                        for btn in row:
                            if hasattr(btn, "url") and btn.url:
                                btn_links.append(btn.url)
            except Exception:
                pass

            gorsel = (
                event.message.media
                if event.message.media and isinstance(event.message.media, MessageMediaPhoto)
                else None
            )

            kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"

            # Çok ürünlü mesajı bloklara böl, her biri ayrı işlenir
            bloklar = mesaj_bolum_ayir(ham)
            if len(bloklar) > 1:
                log("BILGI", f"Çok ürünlü mesaj: {len(bloklar)} ürün ayrıldı")

            for blok in bloklar:
                await _isle(blok, gorsel, btn_links, kanal_adi, kuyruk)

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
