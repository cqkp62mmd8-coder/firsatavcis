"""
Kuyruk worker: kuyruktaki mesajları 3 dakika arayla kanala gönderir.
Tuple formatı: (sablon, gorsel, lnk, magaza, kat, kanal_adi, indirim, fs, extra_lnk?)
  extra_lnk → varsa 2. ürün butonu eklenir (çoklu fırsat mesajları)
"""
import asyncio
from io import BytesIO

from telethon import TelegramClient

import config
import state
from services.gorsel import logo_ekle
from utils.cache import ist_guncelle
from utils.log import log, gece_modu_aktif

_MAX_RETRY = 3


def _aktif_bekleme() -> int:
    """#12 — Spike modu: yoğun saatlerde bekleme süresini kısalt.
    - Cuma akşamı 18-23 → KUYRUK_BEKLEME / 2
    - Pazartesi sabah 09-12 → KUYRUK_BEKLEME / 2
    - Gece 02-07 → KUYRUK_BEKLEME × 2 (uyandırmamak için)
    - Diğer → KUYRUK_BEKLEME"""
    if not config.SPIKE_MODU_AKTIF:
        return config.KUYRUK_BEKLEME

    from utils.log import simdi_tr
    simdi = simdi_tr()
    gun = simdi.weekday()   # 0=pzt, 4=cuma
    saat = simdi.hour
    temel = config.KUYRUK_BEKLEME

    # Cuma akşam (4 = Cuma, 17-22)
    if gun == 4 and 17 <= saat < 23:
        return max(60, temel // 2)
    # Pazartesi sabah (0 = Pzt, 9-12)
    if gun == 0 and 9 <= saat < 13:
        return max(60, temel // 2)
    # Gece (2-7)
    if 2 <= saat < 7:
        return temel * 2
    return temel


# ── Tepki ───────────────────────────────────────────────────────

async def tepki_ekle(client: TelegramClient, mesaj) -> None:
    """Tepki ekleme devre dışı — sessiz no-op."""
    return


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
        alindi = False   # Bu döngüde kuyruk.get() çağrıldı mı?
        try:
            veri = await kuyruk.get()
            alindi = True
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
                    buf = BytesIO(logo_ekle(raw, link=lnk))
                    buf.name = "urun.png"
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
                # Ürün görseli yok → düz metin gönder (logo eklenmez)
                kw3 = dict(parse_mode="html")
                if buton:
                    kw3["buttons"] = buton
                msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw3)

            if msg:
                await tepki_ekle(client, msg)

            # Yüksek skor → sabitle (pin)
            if msg and fs_skor >= 7.0:
                try:
                    await client.pin_message(config.HEDEF_KANAL, msg.id, notify=False)
                    log("OK", f"Sabitlendi (skor {fs_skor}/10)")
                except Exception as e:
                    log("UYARI", f"Pin hatası: {e}")

            ist_guncelle(kanal_adi, magaza, kat)
            tip = "çoklu" if extra_lnk else "tekli"
            log("OK", f"Gönderildi [{magaza}] %{indirim} ({tip}) | kuyruk={kuyruk.qsize()}")

            # #11 Stok takibe kaydet
            if msg and lnk:
                try:
                    from services.stok_takip import kayit_ekle
                    kayit_ekle(msg, lnk)
                except Exception as e:
                    log("UYARI", f"Stok takip kayıt: {e}")

            kuyruk.task_done()
            await asyncio.sleep(_aktif_bekleme())

        except Exception as e:
            log("HATA", f"Worker: {type(e).__name__}: {e}")
            if alindi:
                try:
                    kuyruk.task_done()
                except ValueError:
                    pass
            await asyncio.sleep(10)
