"""
Watchdog: arka planda kanalları doğrular, görülmüş cache'i temizler.
Admin'e sadece SORUN varsa veya günde 1 kez sabah özet atar (spam yapmaz).
"""
import asyncio

from telethon import TelegramClient

import config
from utils.cache import ist_yukle, ist_kaydet, gorulmus_temizle
from utils.log import log, simdi_tr


_son_ozet_tarihi: str = ""


async def admin_bildir(client: TelegramClient, mesaj: str) -> None:
    """Admin'e bildirim. ADMIN_ID yoksa sessiz."""
    if not config.ADMIN_ID:
        return
    try:
        await client.send_message(int(config.ADMIN_ID), f"FırsatPulsu:\n{mesaj}")
    except Exception as e:
        log("UYARI", f"Admin bildirim hatası: {e}")


async def kanal_dogrula(client: TelegramClient) -> list[str]:
    """Geçersiz kanalları listeden çıkarır, geçerli listeyi döndürür."""
    gecerli = []
    log("BILGI", f"{len(config.KAYNAK_KANALLAR)} kanal doğrulanıyor…")
    for kanal in config.KAYNAK_KANALLAR:
        try:
            await client.get_entity(kanal)
            gecerli.append(kanal)
            log("OK", f"{kanal} aktif")
        except Exception as e:
            log("UYARI", f"{kanal} bulunamadı: {e}")
    log("BILGI", f"{len(gecerli)} kanal aktif")
    return gecerli


async def calistir(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    """Watchdog ana döngüsü. 1 saatte bir görevleri yapar, sorun varsa admin'e bildirir.
    Günde sadece 1 kez (09:00 sonrası) özet rapor gönderir."""
    global _son_ozet_tarihi
    log("BILGI", "Watchdog başladı (saatlik döngü)")

    while True:
        await asyncio.sleep(config.WATCHDOG_ARALIK)
        try:
            # 1. Cache temizliği
            gorulmus_temizle()
            ist_kaydet()

            # 2. Sorun var mı kontrol et
            sorunlar = []
            if kuyruk.qsize() >= kuyruk.maxsize - 5:
                sorunlar.append(f"⚠️ Kuyruk %{int(kuyruk.qsize()/kuyruk.maxsize*100)} dolu ({kuyruk.qsize()}/{kuyruk.maxsize})")

            ist = ist_yukle()
            bugun = simdi_tr().strftime("%Y-%m-%d")
            bugun_sayi = ist.get("gunluk", {}).get(bugun, 0)

            # Saat 18:00'den sonra hâlâ 0 fırsat = kanal problemi olabilir
            if simdi_tr().hour >= 18 and bugun_sayi == 0 and len(config.KAYNAK_KANALLAR) > 0:
                sorunlar.append("⚠️ Bugün hiç fırsat paylaşılmadı, kaynak kanalları kontrol et")

            if sorunlar:
                await admin_bildir(
                    client,
                    "🚨 Uyarılar:\n" + "\n".join(sorunlar) +
                    f"\n\n📊 Bugün: {bugun_sayi} | Toplam: {ist.get('toplam', 0)} | Kuyruk: {kuyruk.qsize()}"
                )

            # 3. Günlük özet (09:00–10:00 arası, günde sadece 1 kez)
            if 9 <= simdi_tr().hour < 10 and _son_ozet_tarihi != bugun:
                _son_ozet_tarihi = bugun
                kategoriler = ist.get("kategoriler", {})
                magazalar   = ist.get("magazalar", {})
                top_kat = max(kategoriler, key=kategoriler.get) if kategoriler else "-"
                top_mag = max(magazalar, key=magazalar.get) if magazalar else "-"
                await admin_bildir(
                    client,
                    f"☀️ Günaydın!\n\n"
                    f"📊 Dün: {ist.get('gunluk', {}).get(_onceki_gun(), 0)} fırsat\n"
                    f"📈 Toplam: {ist.get('toplam', 0)} fırsat\n"
                    f"🏆 Top kategori: {top_kat}\n"
                    f"🏪 Top mağaza: {top_mag}\n"
                    f"📬 Kuyrukta: {kuyruk.qsize()} mesaj"
                )

        except Exception as e:
            log("HATA", f"Watchdog: {e}")


def _onceki_gun() -> str:
    """YYYY-MM-DD olarak dün."""
    from datetime import timedelta
    return (simdi_tr() - timedelta(days=1)).strftime("%Y-%m-%d")
