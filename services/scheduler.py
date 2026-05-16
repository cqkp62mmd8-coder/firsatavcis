"""
Zamanlayıcı servisleri: günün en iyileri, sürpriz fırsat, haftalık rapor.
"""
import asyncio
import random
from datetime import datetime, timedelta

from telethon import TelegramClient

from config.settings import HEDEF_KANAL, MAGAZA_HASHTAG, KATEGORI_YAZI
from core.parser import kategori_bul, link_bul, urun_adi_bul, fiyat_bul, magaza_bul, firsat_skoru_hesapla
from core.storage import istatistik_yukle, istatistik_kaydet
from services.sender import tepki_ekle
from utils.logger import log

# ─── Günün Ürünleri ────────────────────────────────────────────
_gunun_urunleri: list[dict] = []


def gunun_urunune_ekle(metin: str, indirim: int, buton_linkleri: list) -> None:
    e, y, _, _ = fiyat_bul(metin)
    _gunun_urunleri.append({
        "metin": metin, "indirim": indirim,
        "link": link_bul(metin, buton_linkleri),
        "urun": urun_adi_bul(metin) or "Ürün",
        "magaza": magaza_bul(metin),
        "eski": e, "yeni": y,
    })
    _gunun_urunleri.sort(key=lambda x: x["indirim"], reverse=True)
    del _gunun_urunleri[20:]


def gunun_urunleri_listesi() -> list:
    return _gunun_urunleri


# ─── Günün En İyileri (21:00) ──────────────────────────────────
async def gunun_en_iyilerini_gonder(client: TelegramClient) -> None:
    if not _gunun_urunleri:
        log("BILGI", "21:00 – Ürün yok")
        return
    en_iyi = _gunun_urunleri[:3]
    log("BILGI", f"21:00 – {len(en_iyi)} ürün paylaşılıyor")
    try:
        await client.send_message(
            HEDEF_KANAL,
            "🏆 <b>GÜNÜN EN İYİ FIRSATLARI</b> 🏆\n\nBugün yakalanan en yüksek indirimli ürünler:",
            parse_mode="html",
        )
        await asyncio.sleep(3)
    except Exception as e:
        log("HATA", f"Başlık: {e}")

    for i, u in enumerate(en_iyi, 1):
        madalya = ["🥇", "🥈", "🥉"][i - 1]
        _, kat_ikon, _ = kategori_bul(u["metin"])
        mt = MAGAZA_HASHTAG.get(u["magaza"], "")
        s = [f"{madalya} <b>{i}. FIRSAT — %{u['indirim']} İNDİRİM</b>", ""]
        s.append(f"{kat_ikon} {u['urun'][:60]}")
        s.append("")
        if u["eski"] and u["yeni"]:
            s.append(f"🏷️ Normal:    <s>{u['eski']} TL</s>")
            s.append(f"💰 İndirimli: <b>{u['yeni']} TL</b>")
            s.append("")
        s.append(f"🏪 {u['magaza']}")
        s.append("")
        s.append(f"#GününFırsatı {mt} #FırsatPulsu")
        s.append(f"📢 @{HEDEF_KANAL.lstrip('@')}")
        if u.get("link"):
            s.append(f"\n🔗 <a href='{u['link']}'>Fırsata Git</a>")
        try:
            msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
            if msg:
                await tepki_ekle(client, msg)
            await asyncio.sleep(5)
        except Exception as e:
            log("HATA", f"Günün ürünü: {e}")

    _gunun_urunleri.clear()
    log("BILGI", "21:00 – Tamamlandı")


async def gunluk_zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = datetime.now()
        hedef = simdi.replace(hour=21, minute=0, second=0, microsecond=0)
        if simdi >= hedef:
            hedef += timedelta(days=1)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Günlük özet: {int(bekle // 3600)}s {int((bekle % 3600) // 60)}dk sonra")
        await asyncio.sleep(bekle)
        await gunun_en_iyilerini_gonder(client)


# ─── Sürpriz Fırsat ────────────────────────────────────────────
async def surpriz_firsat_gonder(client: TelegramClient) -> None:
    if not _gunun_urunleri:
        return
    uygun = [u for u in _gunun_urunleri if u["indirim"] >= 60] or _gunun_urunleri
    u = random.choice(uygun)
    _, kat_ikon, _ = kategori_bul(u["metin"])
    mt = MAGAZA_HASHTAG.get(u["magaza"], "")
    s = ["🎰 <b>GÜNLÜK SÜRPRİZ FIRSAT!</b>", "", "Her gün bir sürpriz fırsat — bugünkü sürpriz:", ""]
    s.append(f"{kat_ikon} <b>{u['urun'][:60]}</b>")
    s.append("")
    if u["eski"] and u["yeni"]:
        s.append(f"🏷️ Normal:    <s>{u['eski']} TL</s>")
        s.append(f"💰 İndirimli: <b>{u['yeni']} TL</b>")
        s.append("")
    s.append(f"🏪 {u['magaza']}  •  🔥 <b>%{u['indirim']} İNDİRİM</b>")
    s.append("")
    s.append(f"#SürprizFırsat #GünlükFırsat {mt} #FırsatPulsu")
    s.append(f"📢 @{HEDEF_KANAL.lstrip('@')}")
    if u.get("link"):
        s.append(f"\n🔗 <a href='{u['link']}'>Fırsata Git</a>")
    try:
        msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
        if msg:
            await tepki_ekle(client, msg)
        log("OK", f"Sürpriz fırsat: {u['urun'][:40]}")
    except Exception as e:
        log("HATA", f"Sürpriz fırsat: {e}")


async def surpriz_firsat_zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = datetime.now()
        saat = random.randint(12, 19)
        dakika = random.randint(0, 59)
        hedef = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
        if simdi >= hedef:
            hedef = (simdi + timedelta(days=1)).replace(
                hour=random.randint(12, 19), minute=random.randint(0, 59),
                second=0, microsecond=0,
            )
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Sürpriz fırsat: {hedef.strftime('%H:%M')} için bekleniyor")
        await asyncio.sleep(bekle)
        await surpriz_firsat_gonder(client)


# ─── Haftalık Rapor (Pazar 20:00) ──────────────────────────────
async def haftalik_rapor_gonder(client: TelegramClient) -> None:
    ist = istatistik_yukle()
    istatistik_kaydet()
    simdi = datetime.now()
    haftalik = sum(
        ist.get("gunluk", {}).get((simdi - timedelta(days=i)).strftime("%Y-%m-%d"), 0)
        for i in range(7)
    )
    kategoriler = ist.get("kategoriler", {})
    en_kat = max(kategoriler, key=kategoriler.get) if kategoriler else "genel"
    magazalar = ist.get("magazalar", {})
    en_mag = max(magazalar, key=magazalar.get) if magazalar else "Bilinmiyor"
    kanal = HEDEF_KANAL.lstrip("@")
    s = [
        "📊 <b>HAFTALIK FIRSAT RAPORU</b>", "",
        f"Bu hafta <b>{haftalik} fırsat</b> paylaştık!", "",
        f"🏆 En popüler kategori: <b>{KATEGORI_YAZI.get(en_kat, en_kat)}</b>",
        f"🏪 En çok paylaşılan: <b>{en_mag}</b>",
        f"📈 Toplam: <b>{ist.get('toplam', 0)} fırsat</b>", "",
        "Bildirimleri açık tutun! 🔔", "",
        "#HaftalıkRapor #FırsatPulsu",
        f"📢 @{kanal}",
    ]
    try:
        msg = await client.send_message(HEDEF_KANAL, "\n".join(s), parse_mode="html")
        if msg:
            await tepki_ekle(client, msg)
        log("OK", "Haftalık rapor gönderildi")
    except Exception as e:
        log("HATA", f"Haftalık rapor: {e}")


async def haftalik_zamanlayici(client: TelegramClient) -> None:
    while True:
        simdi = datetime.now()
        gunler_pazar = (6 - simdi.weekday()) % 7
        if gunler_pazar == 0 and simdi.hour >= 20:
            gunler_pazar = 7
        hedef = (simdi + timedelta(days=gunler_pazar)).replace(hour=20, minute=0, second=0, microsecond=0)
        bekle = (hedef - simdi).total_seconds()
        log("BILGI", f"Haftalık rapor: {int(bekle // 3600)}s sonra")
        await asyncio.sleep(bekle)
        await haftalik_rapor_gonder(client)
