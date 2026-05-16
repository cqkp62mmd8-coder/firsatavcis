"""
Telegram mesaj dinleyici: gelen mesajları filtreler, kuyruğa ekler.
"""
from telethon import events

from config.settings import KARA_LISTE, MIN_INDIRIM, MIN_KALITE
from core.parser import (
    indirim_oranini_bul, mesaj_kalite_skoru, magaza_bul,
    kategori_bul, marka_spam_kontrol, firsat_skoru_hesapla, link_bul,
)
from core.template import sablon_olustur
from core.storage import gorulmus_var_mi, gorulmus_ekle
from services.scheduler import gunun_urunune_ekle
from utils.text import markdown_temizle, benzerlik_anahtari
from utils.text import benzerlik_anahtari
from utils.logger import log
from core.parser import urun_adi_bul, fiyat_bul

from telethon.tl.types import MessageMediaPhoto


def register_handler(client, mesaj_kuyrugu):
    """Handler'ı Telethon client'a bağlar."""

    @client.on(events.NewMessage())
    async def mesaj_dinle(event):
        try:
            ham_metin = markdown_temizle(event.message.text or "")

            # Kara liste
            for yasak in KARA_LISTE:
                if yasak in ham_metin.lower():
                    return

            indirim = indirim_oranini_bul(ham_metin)
            if indirim < MIN_INDIRIM:
                return

            # Duplikat kontrolü
            mid = benzerlik_anahtari(ham_metin, urun_adi_bul, fiyat_bul)
            if gorulmus_var_mi(mid):
                return
            gorulmus_ekle(mid)

            # Buton linkleri
            buton_linkleri = []
            try:
                if event.message.buttons:
                    for row in event.message.buttons:
                        for btn in row:
                            if hasattr(btn, "url") and btn.url:
                                buton_linkleri.append(btn.url)
            except Exception:
                pass

            link = link_bul(ham_metin, buton_linkleri)
            if not link:
                return

            skor = mesaj_kalite_skoru(ham_metin, indirim, buton_linkleri)
            if skor < MIN_KALITE:
                log("BILGI", f"Düşük kalite (skor:{skor}) atlandı")
                return

            magaza = magaza_bul(ham_metin)
            if marka_spam_kontrol(magaza):
                log("BILGI", f"{magaza} spam limiti – atlandı")
                return

            sablon = sablon_olustur(ham_metin, indirim, buton_linkleri)
            if not sablon:
                return

            gorsel_medya = None
            if event.message.media and isinstance(event.message.media, MessageMediaPhoto):
                gorsel_medya = event.message.media

            gunun_urunune_ekle(ham_metin, indirim, buton_linkleri)

            kat_adi, _, _ = kategori_bul(ham_metin)
            kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"
            fs_skor = firsat_skoru_hesapla(ham_metin, indirim, buton_linkleri)

            if mesaj_kuyrugu.full():
                try:
                    mesaj_kuyrugu.get_nowait()
                    log("UYARI", "Kuyruk doldu, eski mesaj çıkarıldı")
                except Exception:
                    pass

            await mesaj_kuyrugu.put((
                sablon, gorsel_medya, link, magaza,
                kat_adi, kanal_adi, indirim, fs_skor,
            ))
            log("BILGI", f"Kuyruğa eklendi [{magaza}] %{indirim} | Kuyruk: {mesaj_kuyrugu.qsize()}")

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
