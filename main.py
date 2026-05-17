"""
FırsatPulsu — Ana Giriş Noktası
Çalıştır: python main.py
"""
import asyncio
import sys

from telethon import TelegramClient

import config
import client as tg
from utils.log import log
from watchdog import admin_bildir, kanal_dogrula, calistir as watchdog_calistir
from handlers import mesaj as mesaj_handler, callback as callback_handler
from handlers import admin as admin_handler
from services.kuyruk import worker as kuyruk_worker
from schedulers import gunluk, surpriz, haftalik


# ── Başlangıç doğrulaması ────────────────────────────────────────

def _config_dogrula() -> bool:
    """Kritik env değişkenlerini kontrol eder; eksik varsa False döner."""
    eksik = []
    if not config.API_ID or config.API_ID == 0:
        eksik.append("API_ID")
    if not config.API_HASH:
        eksik.append("API_HASH")
    if not config.SESSION_STRING:
        eksik.append("SESSION_STRING")
    if not config.HEDEF_KANAL:
        eksik.append("CHANNEL_ID")
    if eksik:
        log("KRITIK", f"Eksik ortam değişkenleri: {', '.join(eksik)}")
        return False
    return True


# ── Test modu ───────────────────────────────────────────────────

async def _test_gonder(kuyruk: asyncio.Queue) -> None:
    from services.analiz import (
        indirim_oranini_bul, kalite_skoru, magaza_bul,
        kategori_bul, firsat_skoru, link_bul,
    )
    from services.sablon import olustur
    from schedulers.gunluk import ekle

    ornekler = [
        ("Philips Tıraş Makinesi\n\nİndirimli Fiyat: 299,90 TL\nNormal Fiyat: 899,00 TL\nİndirim: -%66\nStoklar Eriyor!\n\nAmazon TR\nhttps://amazon.com.tr/test", "Amazon %66"),
        ("Samsung 65 inç 4K TV\n\nTrendyol ürünlerinde %75 indirim var\n\n1.499 TL yerine 374 TL\n\nhttps://trendyol.com/test", "Trendyol marka"),
        ("Nike Air Max Spor Ayakkabı\n\nHepsiburada 60% indirim\n\n3.200 TL - 1.280 TL\n\nhttps://hepsiburada.com/test", "Hepsiburada giyim"),
    ]

    log("TEST", "=== TEST BAŞLIYOR ===")
    for i, (metin, aciklama) in enumerate(ornekler, 1):
        ind = indirim_oranini_bul(metin)
        skor = kalite_skoru(metin, ind, [])
        sablon = olustur(metin, ind, [])
        lnk = link_bul(metin)
        log("TEST", f"{i}. {aciklama} → %{ind} skor={skor}")
        if sablon and lnk:
            ekle(metin, ind, [])
            await kuyruk.put((
                sablon, None, lnk,
                magaza_bul(metin), kategori_bul(metin)[0],
                "test", ind, firsat_skoru(metin, ind, []),
            ))
            log("TEST", "   → kuyruğa eklendi")
        await asyncio.sleep(1)

    await asyncio.sleep(5)
    await gunluk.gonder(tg.client)
    await asyncio.sleep(3)
    await surpriz.gonder(tg.client)
    await asyncio.sleep(3)
    await haftalik.gonder(tg.client)
    log("TEST", "=== TESTLER TAMAMLANDI ===")


# ── Ana döngü ───────────────────────────────────────────────────

async def main() -> None:
    log("SISTEM", "FırsatPulsu v9 başlatılıyor…")

    if not _config_dogrula():
        sys.exit(1)

    log("SISTEM", (
        f"Min indirim: %{config.MIN_INDIRIM} | "
        f"Kalite: {config.MIN_KALITE} | "
        f"Bekleme: {config.KUYRUK_BEKLEME}s"
    ))

    kuyruk: asyncio.Queue = asyncio.Queue(maxsize=50)

    while True:
        try:
            await tg.client.start()
            log("OK", "Kullanıcı client bağlandı")

            # Bot client (inline butonlar — opsiyonel)
            if config.BOT_TOKEN:
                try:
                    tg.bot_client = TelegramClient("bot_session", config.API_ID, config.API_HASH)
                    await tg.bot_client.start(bot_token=config.BOT_TOKEN)
                    callback_handler.kaydet(tg.bot_client)
                    log("OK", "Bot client aktif – inline butonlar çalışıyor")
                except Exception as e:
                    log("UYARI", f"Bot client başlatılamadı: {e}")
                    tg.bot_client = None

            # Kanal doğrulama & handler kaydı
            config.KAYNAK_KANALLAR[:] = await kanal_dogrula(tg.client)
            mesaj_handler.kaydet(tg.client, kuyruk)
            admin_handler.kaydet(tg.client, kuyruk)   # Admin komutları

            await admin_bildir(
                tg.client,
                f"🚀 Bot Başladı v9\n"
                f"Kanal: {len(config.KAYNAK_KANALLAR)}\n"
                f"Min indirim: %{config.MIN_INDIRIM}\n\n"
                f"Admin komutları için /yardim yaz.",
            )

            if config.TEST_MODE:
                await _test_gonder(kuyruk)

            # Arka plan görevleri
            for coro in [
                kuyruk_worker(tg.client, tg.bot_client, kuyruk),
                watchdog_calistir(tg.client, kuyruk),
                gunluk.zamanlayici(tg.client),
                surpriz.zamanlayici(tg.client),
                haftalik.zamanlayici(tg.client),
            ]:
                asyncio.ensure_future(coro)

            await tg.client.run_until_disconnected()

        except KeyboardInterrupt:
            log("SISTEM", "Manuel kapatma — çıkılıyor")
            break
        except Exception as e:
            log("HATA", f"Bağlantı koptu: {e}")
            log("BILGI", "30s sonra yeniden bağlanılıyor…")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
