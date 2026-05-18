"""
Kaynak kanallardan gelen yeni mesajları dinler, filtreler ve işleme kuyruğuna ekler.
2 ürünlü mesajları tek mesaj + 2 inline buton olarak kuyruğa ekler.
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
    mesaj_bolum_ayir, urun_adi_bul,
)
from services.sablon import olustur as sablon_olustur
from schedulers.gunluk import ekle as gunluk_ekle
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


def _blok_analiz(blok: str, btn_links: list[str]) -> dict | None:
    """Tek bloğu analiz eder. Filtreden geçemezse None döner."""
    if any(yasak in blok.lower() for yasak in config.KARA_LISTE):
        return None

    indirim = indirim_oranini_bul(blok)
    if indirim < config.MIN_INDIRIM:
        return None

    mid = benzerlik_anahtari(blok)
    if gorulmus_var_mi(mid):
        return None

    lnk = link_bul(blok, btn_links)
    if not lnk:
        return None

    skor = kalite_skoru(blok, indirim, btn_links)
    if skor < config.MIN_KALITE:
        log("BILGI", f"Düşük kalite (skor={skor}) atlandı")
        return None

    magaza = magaza_bul(blok)
    if marka_spam_kontrol(magaza):
        log("BILGI", f"{magaza} spam limiti – atlandı")
        return None

    sablon = sablon_olustur(blok, indirim, btn_links)
    if not sablon:
        return None

    gorulmus_ekle(mid)
    gunluk_ekle(blok, indirim, btn_links)

    kat, _, _ = kategori_bul(blok)
    fs = firsat_skoru(blok, indirim, btn_links)
    urun = urun_adi_bul(blok) or magaza

    return {
        "sablon": sablon,
        "lnk": lnk,
        "magaza": magaza,
        "kat": kat,
        "indirim": indirim,
        "fs": fs,
        "urun": urun,
    }


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:

    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            if state.durduruldu:
                return

            ham = markdown_temizle(event.message.text or "")

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

            if len(bloklar) == 2:
                # ── İki ürün: tek mesaj + 2 inline buton ────────
                a1 = _blok_analiz(bloklar[0], btn_links)
                a2 = _blok_analiz(bloklar[1], btn_links)

                if a1 and a2:
                    # Birleşik şablon
                    ayrac = "\n\n" + "─" * 20 + "\n\n"
                    birlesik = a1["sablon"] + ayrac + a2["sablon"]
                    # lnk: [(url, urun_adi), ...] → kuyruk.py 2 buton oluşturur
                    lnk_cift = [(a1["lnk"], a1["urun"][:22]), (a2["lnk"], a2["urun"][:22])]
                    indirim_max = max(a1["indirim"], a2["indirim"])
                    fs_max = max(a1["fs"], a2["fs"])
                    try:
                        kuyruk.put_nowait((
                            birlesik, gorsel, lnk_cift,
                            a1["magaza"], a1["kat"], kanal_adi, indirim_max, fs_max,
                        ))
                        log("BILGI", f"2 ürün tek mesaj [{a1['magaza']}+{a2['magaza']}] | kuyruk={kuyruk.qsize()}")
                    except asyncio.QueueFull:
                        log("UYARI", "Kuyruk dolu, 2-ürün mesaj atıldı")
                elif a1:
                    # Sadece 1. ürün geçti
                    try:
                        kuyruk.put_nowait((
                            a1["sablon"], gorsel, a1["lnk"],
                            a1["magaza"], a1["kat"], kanal_adi, a1["indirim"], a1["fs"],
                        ))
                        log("BILGI", f"Kuyruğa eklendi [{a1['magaza']}] %{a1['indirim']}")
                    except asyncio.QueueFull:
                        log("UYARI", "Kuyruk dolu, mesaj atıldı")
                elif a2:
                    try:
                        kuyruk.put_nowait((
                            a2["sablon"], gorsel, a2["lnk"],
                            a2["magaza"], a2["kat"], kanal_adi, a2["indirim"], a2["fs"],
                        ))
                        log("BILGI", f"Kuyruğa eklendi [{a2['magaza']}] %{a2['indirim']}")
                    except asyncio.QueueFull:
                        log("UYARI", "Kuyruk dolu, mesaj atıldı")

            else:
                # ── Tek ürün ─────────────────────────────────────
                a = _blok_analiz(bloklar[0], btn_links)
                if not a:
                    return
                try:
                    kuyruk.put_nowait((
                        a["sablon"], gorsel, a["lnk"],
                        a["magaza"], a["kat"], kanal_adi, a["indirim"], a["fs"],
                    ))
                    log("BILGI", f"Kuyruğa eklendi [{a['magaza']}] %{a['indirim']} | kuyruk={kuyruk.qsize()}")
                except asyncio.QueueFull:
                    log("UYARI", f"Kuyruk dolu, mesaj atıldı [{a['magaza']}]")

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
