"""
Kaynak kanallardan gelen yeni mesajları dinler, filtreler ve kuyruğa ekler.
- Tek ürünlü mesaj: normal akış (1 mesaj, 1 buton)
- Çok ürünlü mesaj: tek mesajda 2 ürün birleştirilir (1 mesaj, 2 buton)
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
from services.sablon import olustur as sablon_olustur, olustur_coklu
from schedulers.gunluk import ekle as gunluk_ekle
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


def _blok_analiz(blok: str, btn_links: list[str]) -> dict | None:
    """Bir bloğu analiz edip dict döner; geçersizse None."""
    if any(yasak in blok.lower() for yasak in config.KARA_LISTE):
        return None
    indirim = indirim_oranini_bul(blok)
    if indirim < config.MIN_INDIRIM:
        return None
    lnk = link_bul(blok, btn_links)
    if not lnk:
        return None
    skor = kalite_skoru(blok, indirim, btn_links)
    if skor < config.MIN_KALITE:
        return None
    magaza = magaza_bul(blok, lnk)
    kat, _, _ = kategori_bul(blok)
    fs = firsat_skoru(blok, indirim, btn_links)
    return {
        "blok": blok, "indirim": indirim, "link": lnk,
        "magaza": magaza, "kat": kat, "skor": skor, "fs": fs,
    }


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            if state.durduruldu:
                return

            ham = markdown_temizle(event.message.text or "")

            # Buton linklerini topla
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

            bloklar = mesaj_bolum_ayir(ham)
            # Her bloğu analiz et, geçenleri topla
            adaylar = []
            for b in bloklar:
                sonuc = _blok_analiz(b, btn_links)
                if sonuc:
                    adaylar.append(sonuc)

            if not adaylar:
                return

            # Tüm mesaj için tek duplikat anahtar — aynı mesaj 2 kez gelmesin
            mid = benzerlik_anahtari(adaylar[0]["blok"])
            if gorulmus_var_mi(mid):
                return
            gorulmus_ekle(mid)

            # Tek ürün
            if len(adaylar) == 1:
                a = adaylar[0]
                if marka_spam_kontrol(a["magaza"]):
                    log("BILGI", f"{a['magaza']} spam limiti – atlandı")
                    return
                sablon = sablon_olustur(a["blok"], a["indirim"], btn_links)
                if not sablon:
                    return
                gunluk_ekle(a["blok"], a["indirim"], btn_links)
                try:
                    kuyruk.put_nowait((
                        sablon, gorsel, [a["link"]],
                        a["magaza"], a["kat"], kanal_adi,
                        a["indirim"], a["fs"],
                    ))
                    log("BILGI", f"Kuyruğa eklendi [{a['magaza']}] %{a['indirim']} | kuyruk={kuyruk.qsize()}")
                except asyncio.QueueFull:
                    log("UYARI", f"Kuyruk dolu, mesaj atıldı [{a['magaza']}]")
                return

            # Çoklu ürün — en kaliteli 2'sini al, tek mesaj/2 buton
            adaylar.sort(key=lambda x: x["fs"], reverse=True)
            a1, a2 = adaylar[0], adaylar[1]

            # Aynı linkler tek ürünmüş gibi → sadece birini al
            if a1["link"] == a2["link"] and a1["indirim"] == a2["indirim"]:
                if marka_spam_kontrol(a1["magaza"]):
                    return
                sablon = sablon_olustur(a1["blok"], a1["indirim"], btn_links)
                if not sablon:
                    return
                gunluk_ekle(a1["blok"], a1["indirim"], btn_links)
                try:
                    kuyruk.put_nowait((
                        sablon, gorsel, [a1["link"]],
                        a1["magaza"], a1["kat"], kanal_adi,
                        a1["indirim"], a1["fs"],
                    ))
                    log("BILGI", f"Kuyruğa eklendi (tek) [{a1['magaza']}] %{a1['indirim']}")
                except asyncio.QueueFull:
                    log("UYARI", "Kuyruk dolu")
                return

            if marka_spam_kontrol(a1["magaza"]):
                return

            sablon = olustur_coklu(
                a1["blok"], a1["indirim"], a1["link"],
                a2["blok"], a2["indirim"], a2["link"],
                btn_links=btn_links,
            )
            if not sablon:
                return

            gunluk_ekle(a1["blok"], a1["indirim"], btn_links)
            gunluk_ekle(a2["blok"], a2["indirim"], btn_links)

            try:
                kuyruk.put_nowait((
                    sablon, gorsel,
                    [a1["link"], a2["link"]],   # 2 link → 2 buton
                    a1["magaza"], a1["kat"], kanal_adi,
                    max(a1["indirim"], a2["indirim"]),
                    max(a1["fs"], a2["fs"]),
                ))
                log("BILGI", f"Çoklu kuyruğa eklendi [{a1['magaza']}+{a2['magaza']}] %{a1['indirim']}+%{a2['indirim']}")
            except asyncio.QueueFull:
                log("UYARI", "Kuyruk dolu, çoklu mesaj atıldı")

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
