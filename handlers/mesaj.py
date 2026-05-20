"""
Kaynak kanallardan gelen yeni mesajları dinler, filtreler ve kuyruğa ekler.
- Tek ürünlü mesaj: normal akış (1 mesaj, 1 buton)
- Çok ürünlü mesaj: tek mesajda 2 ürün birleştirilir (1 mesaj, 2 buton)
"""
import asyncio
import re

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
from services import llm
from schedulers.gunluk import ekle as gunluk_ekle
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


def _kara_liste_eslesir(metin: str) -> bool:
    """Kara liste kelimesi tam kelime olarak metin içinde geçiyor mu?
    'tablet kalem' → 'kalem' yakalanmalı (boşluk sınırı)
    'kalemini' → 'kalem' yakalanmamalı (kelime uzantısı)
    'kitaplık' → 'kitap' yakalanmamalı (uzantı)"""
    if not metin:
        return False
    ml = metin.lower()
    for kelime in config.KARA_LISTE:
        # Çok kelimeli ise direkt substring (örn "ekran koruyucu")
        if " " in kelime:
            if kelime in ml:
                return True
        else:
            # Tek kelime → kelime sınırı ile ara
            if re.search(r"\b" + re.escape(kelime) + r"\b", ml):
                return True
    return False


def _blok_analiz(blok: str, btn_links: list[str]) -> dict | None:
    """Bir bloğu analiz edip dict döner; geçersizse None.
    Regex zayıf kalırsa (link var ama indirim/ürün adı bulunamamış) LLM fallback dener."""
    onizleme = blok[:50].replace("\n", " ")

    if _kara_liste_eslesir(blok):
        log("FILTRE", f"Kara liste → atlandı: '{onizleme}…'")
        return None

    indirim = indirim_oranini_bul(blok)
    lnk = link_bul(blok, btn_links)

    if not lnk:
        log("FILTRE", f"Link yok → atlandı: '{onizleme}…'")
        if btn_links:
            log("FILTRE", f"  Mevcut buton linkleri ({len(btn_links)}): {btn_links}")
        return None

    from services.analiz import urun_adi_bul
    urun = urun_adi_bul(blok)

    # ── LLM fallback ────────────────────────────────────────────
    # Link var ama indirim eksik veya ürün adı eksik → LLM'e sor
    if llm.aktif_mi() and (indirim < config.MIN_INDIRIM or not urun):
        # Tekrar dene LLM ile
        log("BILGI", f"Regex zayıf, LLM deneniyor: '{onizleme}…'")
        llm_sonuc = llm.parse_et(blok)
        if llm_sonuc:
            yeni_ind = int(llm_sonuc.get("indirim_yuzdesi") or 0)
            yeni_urun = llm_sonuc.get("urun_adi")
            if yeni_ind > indirim:
                indirim = yeni_ind
            if not urun and yeni_urun:
                urun = yeni_urun

    if indirim < config.MIN_INDIRIM:
        log("FILTRE", f"İndirim %{indirim} < {config.MIN_INDIRIM} → atlandı: '{onizleme}…'")
        return None

    if not urun:
        log("FILTRE", f"Ürün adı çıkarılamadı → atlandı: '{onizleme}…'")
        return None

    skor = kalite_skoru(blok, indirim, btn_links)
    if skor < config.MIN_KALITE:
        log("FILTRE", f"Kalite {skor} < {config.MIN_KALITE} → atlandı: '{onizleme}…'")
        return None

    magaza = magaza_bul(blok, lnk)
    kat, _, _ = kategori_bul(blok)
    fs = firsat_skoru(blok, indirim, btn_links)
    return {
        "blok": blok, "indirim": indirim, "link": lnk,
        "magaza": magaza, "kat": kat, "skor": skor, "fs": fs,
        "urun_llm": urun if not urun_adi_bul(blok) else None,   # LLM'den geldiyse sablon'a aktarılabilir
    }


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            if state.durduruldu:
                return

            # #13 — Eski mesaj filtresi: mesaj çok eskiyse atla
            # (forward edilmiş eski içerikler kanala düşebiliyor)
            try:
                from datetime import datetime, timezone, timedelta
                if event.message.date:
                    yas_sn = (datetime.now(timezone.utc) - event.message.date).total_seconds()
                    if yas_sn > config.ESKI_MESAJ_LIMIT_DK * 60:
                        log("FILTRE", f"Eski mesaj atlandı ({int(yas_sn / 60)}dk önce)")
                        return
            except Exception:
                pass

            ham = markdown_temizle(event.message.text or "")

            # Buton linklerini topla — birkaç farklı yoldan dene
            btn_links: list[str] = []
            try:
                # 1) En yaygın: event.message.buttons (Telethon high-level)
                if event.message.buttons:
                    for row in event.message.buttons:
                        for btn in row:
                            url = getattr(btn, "url", None)
                            if url:
                                btn_links.append(url)
            except Exception as e:
                log("UYARI", f"event.message.buttons hatası: {e}")

            # 2) Fallback: doğrudan reply_markup içine bak
            try:
                if not btn_links and event.message.reply_markup:
                    rm = event.message.reply_markup
                    rows = getattr(rm, "rows", None) or []
                    for row in rows:
                        for btn in getattr(row, "buttons", []) or []:
                            url = getattr(btn, "url", None)
                            if url:
                                btn_links.append(url)
            except Exception as e:
                log("UYARI", f"reply_markup parse hatası: {e}")

            # 3) Fallback: mesajdaki entities (gizli link/text_link)
            try:
                from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
                for ent in event.message.entities or []:
                    if isinstance(ent, MessageEntityTextUrl) and ent.url:
                        btn_links.append(ent.url)
                    elif isinstance(ent, MessageEntityUrl):
                        # Mesaj metninden URL'i kes
                        text = event.message.text or ""
                        url = text[ent.offset:ent.offset + ent.length]
                        if url.startswith("http"):
                            btn_links.append(url)
            except Exception as e:
                log("UYARI", f"entities parse hatası: {e}")

            # Tekrarları temizle, sırasını koru
            seen = set()
            btn_links = [x for x in btn_links if not (x in seen or seen.add(x))]

            if btn_links:
                log("BILGI", f"Mesajdan {len(btn_links)} link toplandı: {btn_links[0][:60]}…")

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
