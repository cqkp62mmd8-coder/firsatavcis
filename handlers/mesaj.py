"""
Kaynak kanallardan gelen yeni mesajları dinler,
filtreler ve işleme kuyruğuna ekler.
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
)
from services.sablon import olustur as sablon_olustur
from schedulers.gunluk import ekle as gunluk_ekle
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    """Handler'ı client'a bağlar. main.py'den bir kez çağrılır."""

    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            # Duraklatma kontrolü
            if state.durduruldu:
                return

            ham = markdown_temizle(event.message.text or "")

            # Kara liste
            if any(yasak in ham.lower() for yasak in config.KARA_LISTE):
                return

            indirim = indirim_oranini_bul(ham)
            if indirim < config.MIN_INDIRIM:
                return

            # Duplikat
            mid = benzerlik_anahtari(ham)
            if gorulmus_var_mi(mid):
                return
            gorulmus_ekle(mid)

            # Buton linkleri
            btn_links: list[str] = []
            try:
                if event.message.buttons:
                    for row in event.message.buttons:
                        for btn in row:
                            if hasattr(btn, "url") and btn.url:
                                btn_links.append(btn.url)
            except Exception:
                pass

            if not link_bul(ham, btn_links):
                return

            skor = kalite_skoru(ham, indirim, btn_links)
            if skor < config.MIN_KALITE:
                log("BILGI", f"Düşük kalite (skor={skor}) atlandı")
                return

            magaza = magaza_bul(ham)
            if marka_spam_kontrol(magaza):
                log("BILGI", f"{magaza} spam limiti – atlandı")
                return

            sablon = sablon_olustur(ham, indirim, btn_links)
            if not sablon:
                return

            gorsel = (
                event.message.media
                if event.message.media and isinstance(event.message.media, MessageMediaPhoto)
                else None
            )

            gunluk_ekle(ham, indirim, btn_links)

            kat, _, _ = kategori_bul(ham)
            kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"
            fs = firsat_skoru(ham, indirim, btn_links)
            lnk = link_bul(ham, btn_links)

            # FIX: put_nowait + QueueFull — bloklamaz, güvenli
            try:
                kuyruk.put_nowait((sablon, gorsel, lnk, magaza, kat, kanal_adi, indirim, fs))
                log("BILGI", f"Kuyruğa eklendi [{magaza}] %{indirim} | kuyruk={kuyruk.qsize()}")
            except asyncio.QueueFull:
                log("UYARI", f"Kuyruk dolu ({kuyruk.maxsize}), mesaj atıldı [{magaza}] %{indirim}")

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
