"""
FırsatPulsu – Ana Giriş Noktası
"""
import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

from config.settings import (
    API_ID, API_HASH, SESSION_STRING, BOT_TOKEN,
    KAYNAK_KANALLAR, MIN_INDIRIM, MIN_KALITE, KUYRUK_BEKLEME,
)
from utils.logger import log
from core.storage import istatistik_yukle, istatistik_kaydet, gorulmus_temizle
from services.sender import kuyruk_worker, kanallari_dogrula
from services.scheduler import (
    gunluk_zamanlayici, surpriz_firsat_zamanlayici, haftalik_zamanlayici,
)
from handlers.message_handler import register_handler
from handlers.callback_handler import register_callback_handler

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# ─── Admin & Watchdog ───────────────────────────────────────────
async def admin_bildir(mesaj: str) -> None:
    admin_id = os.environ.get("ADMIN_ID", "")
    if not admin_id:
        return
    try:
        await client.send_message(int(admin_id), f"FırsatPulsu:\n{mesaj}")
    except Exception:
        pass


async def watchdog(mesaj_kuyrugu: asyncio.Queue) -> None:
    watchdog_aralik = int(os.environ.get("WATCHDOG_ARALIK", "3600"))
    while True:
        await asyncio.sleep(watchdog_aralik)
        ist = istatistik_yukle()
        from datetime import datetime
        bugun = datetime.now().strftime("%Y-%m-%d")
        await admin_bildir(
            f"Bot çalışıyor\n"
            f"Bugün: {ist.get('gunluk', {}).get(bugun, 0)}\n"
            f"Toplam: {ist.get('toplam', 0)}\n"
            f"Kuyruk: {mesaj_kuyrugu.qsize()}"
        )
        gorulmus_temizle()
        istatistik_kaydet()


# ─── Test Modu ─────────────────────────────────────────────────
async def test_gonder(mesaj_kuyrugu: asyncio.Queue) -> None:
    from core.parser import (
        indirim_oranini_bul, mesaj_kalite_skoru, magaza_bul,
        kategori_bul, firsat_skoru_hesapla,
    )
    from core.template import sablon_olustur
    from core.parser import link_bul
    from services.scheduler import gunun_urunune_ekle, gunun_en_iyilerini_gonder, surpriz_firsat_gonder
    from services.scheduler import haftalik_rapor_gonder

    testler = [
        {"metin": "Philips Tıraş Makinesi\n\nİndirimli Fiyat: 299,90 TL\nNormal Fiyat: 899,00 TL\nİndirim: -%66\nStoklar Eriyor!\n\nAmazon TR\nhttps://amazon.com.tr/test", "aciklama": "Amazon %66"},
        {"metin": "Samsung 65 inç 4K TV\n\nTrendyol ürünlerinde %75 indirim var\n\n1.499 TL yerine 374 TL\n\nhttps://trendyol.com/test", "aciklama": "Trendyol marka"},
        {"metin": "Nike Air Max Spor Ayakkabı\n\nHepsiburada 60% indirim\n\n3.200 TL - 1.280 TL\n\nhttps://hepsiburada.com/test", "aciklama": "Hepsiburada giyim"},
    ]
    log("TEST", "=== TEST BAŞLIYOR ===")
    for i, t in enumerate(testler, 1):
        metin = t["metin"]
        indirim = indirim_oranini_bul(metin)
        skor = mesaj_kalite_skoru(metin, indirim, [])
        sablon = sablon_olustur(metin, indirim, [])
        link = link_bul(metin)
        log("TEST", f"{i}. {t['aciklama']} -> %{indirim} skor:{skor}")
        if sablon and link:
            gunun_urunune_ekle(metin, indirim, [])
            await mesaj_kuyrugu.put((
                sablon, None, link,
                magaza_bul(metin), kategori_bul(metin)[0],
                "test", indirim, firsat_skoru_hesapla(metin, indirim, []),
            ))
            log("TEST", "   Kuyruğa eklendi")
        await asyncio.sleep(1)
    await asyncio.sleep(5)
    await gunun_en_iyilerini_gonder(client)
    await asyncio.sleep(3)
    await surpriz_firsat_gonder(client)
    await asyncio.sleep(3)
    await haftalik_rapor_gonder(client)
    log("TEST", "=== TÜM TESTLER TAMAMLANDI ===")


# ─── Main ───────────────────────────────────────────────────────
async def main() -> None:
    log("SISTEM", "FırsatPulsu v8 başlatılıyor...")
    log("SISTEM", f"Min indirim: %{MIN_INDIRIM} | Min kalite: {MIN_KALITE} | Kuyruk bekleme: {KUYRUK_BEKLEME}s")

    if not SESSION_STRING:
        log("KRITIK", "SESSION_STRING eksik!")
        return

    mesaj_kuyrugu: asyncio.Queue = asyncio.Queue(maxsize=50)
    bot_client = None

    while True:
        try:
            await client.start()
            log("OK", "Bağlandı!")

            if BOT_TOKEN:
                try:
                    bot_client = TelegramClient('bot_session', API_ID, API_HASH)
                    await bot_client.start(bot_token=BOT_TOKEN)
                    register_callback_handler(bot_client)
                    log('OK', 'Bot client aktif – inline butonlar çalışıyor')
                except Exception as e:
                    log('UYARI', f'Bot client: {e}')
                    bot_client = None

            # Kaynak kanalları doğrula ve handler'ı kaydet
            gecerli_kanallar = await kanallari_dogrula(client, KAYNAK_KANALLAR)
            register_handler(client, mesaj_kuyrugu)

            await admin_bildir(
                f"Bot Başladı v8\nKanal: {len(gecerli_kanallar)}\nMin indirim: %{MIN_INDIRIM}"
            )

            if os.environ.get("TEST_MODE", "0") == "1":
                await test_gonder(mesaj_kuyrugu)

            asyncio.ensure_future(kuyruk_worker(client, bot_client, mesaj_kuyrugu))
            asyncio.ensure_future(watchdog(mesaj_kuyrugu))
            asyncio.ensure_future(gunluk_zamanlayici(client))
            asyncio.ensure_future(surpriz_firsat_zamanlayici(client))
            asyncio.ensure_future(haftalik_zamanlayici(client))

            await client.run_until_disconnected()

        except Exception as e:
            log("HATA", f"Bağlantı koptu: {e}")
            log("BILGI", "30s sonra yeniden bağlanılıyor...")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
