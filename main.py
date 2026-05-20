"""
FırsatPulsu — Ana Giriş Noktası
Çalıştır: python main.py
"""
import asyncio
import signal
import sys

from telethon import TelegramClient

import config
import client as tg
import state
from utils import cache, db, metrik, izleme
from utils.log import log
from watchdog import admin_bildir, kanal_dogrula, calistir as watchdog_calistir
from handlers import mesaj as mesaj_handler, callback as callback_handler
from handlers import admin as admin_handler
from services.kuyruk import worker as kuyruk_worker
from services import stok_takip, health
from schedulers import gunluk, surpriz, haftalik


# ── Graceful shutdown — #3 ──────────────────────────────────────
_shutdown_event = asyncio.Event() if False else None   # main() içinde set edilecek
_kapanis_baslatildi = False


def _signal_handler():
    """SIGTERM/SIGINT geldiğinde graceful kapanış başlat."""
    global _kapanis_baslatildi
    if _kapanis_baslatildi:
        log("UYARI", "Zorla kapanış istendi — anında çıkılıyor")
        sys.exit(0)
    _kapanis_baslatildi = True
    log("SISTEM", "Kapanış sinyali alındı — graceful shutdown başlıyor")
    state.durduruldu = True   # Yeni mesaj alma
    if _shutdown_event is not None:
        _shutdown_event.set()


async def _graceful_bekle(kuyruk: asyncio.Queue, max_saniye: int = 30) -> None:
    """Kuyruğun boşalmasını bekler (max N saniye)."""
    log("SISTEM", f"Kuyruğun boşalması bekleniyor (max {max_saniye}s)…")
    son_zaman = asyncio.get_event_loop().time() + max_saniye
    while kuyruk.qsize() > 0:
        if asyncio.get_event_loop().time() > son_zaman:
            log("UYARI", f"Süre aşıldı, {kuyruk.qsize()} mesaj kayıp")
            break
        await asyncio.sleep(1)
    # Cache'i son bir kez kaydet
    try:
        from utils.cache import ist_kaydet, _telegram_kaydet
        ist_kaydet()
        await _telegram_kaydet()
        log("OK", "İstatistik son kez kaydedildi")
    except Exception as e:
        log("UYARI", f"Son kayıt hatası: {e}")
    log("SISTEM", "Graceful shutdown tamamlandı — çıkılıyor")


# ── Başlangıç doğrulaması ────────────────────────────────────────

def _config_dogrula() -> bool:
    """Tüm config değerlerini detaylı kontrol eder. Sorun varsa False döner."""
    hatalar = []

    # ZORUNLU alanlar — eksik ya da geçersiz
    if not config.API_ID or config.API_ID == 0:
        hatalar.append("API_ID boş veya 0")
    elif config.API_ID < 1000:
        hatalar.append(f"API_ID görünüşe göre geçersiz ({config.API_ID}) — my.telegram.org'dan alınan tam sayı olmalı")

    if not config.API_HASH:
        hatalar.append("API_HASH boş")
    elif len(config.API_HASH) < 30 or len(config.API_HASH) > 40:
        hatalar.append(f"API_HASH uzunluğu garip ({len(config.API_HASH)} kar) — 32 karakter olmalı")

    if not config.SESSION_STRING:
        hatalar.append("SESSION_STRING boş — kullanıcı oturumu yüklenmemiş")
    elif len(config.SESSION_STRING) < 100:
        hatalar.append(f"SESSION_STRING çok kısa ({len(config.SESSION_STRING)} kar)")

    if not config.HEDEF_KANAL:
        hatalar.append("CHANNEL_ID boş")
    elif not (config.HEDEF_KANAL.startswith("@") or config.HEDEF_KANAL.startswith("-100")):
        hatalar.append(f"CHANNEL_ID format yanlış: '{config.HEDEF_KANAL}' — '@kanalad' veya '-100...' olmalı")

    # OPSİYONEL ama varsa sıkı kontrol
    if config.ADMIN_ID:
        try:
            aid = int(config.ADMIN_ID)
            if aid < 1000:
                hatalar.append(f"ADMIN_ID görünüşe göre geçersiz ({aid})")
        except ValueError:
            hatalar.append(f"ADMIN_ID sayı değil: '{config.ADMIN_ID}'")

    if config.BOT_TOKEN and ":" not in config.BOT_TOKEN:
        hatalar.append("BOT_TOKEN format yanlış — '123456:ABC...' formatında olmalı")

    # Sayısal değerler — mantıklı aralık
    if not (1 <= config.MIN_INDIRIM <= 99):
        hatalar.append(f"MIN_INDIRIM mantıksız ({config.MIN_INDIRIM}) — 1-99 arası olmalı")
    if not (0 <= config.MIN_KALITE <= 100):
        hatalar.append(f"MIN_KALITE mantıksız ({config.MIN_KALITE}) — 0-100 arası olmalı")
    if not (5 <= config.KUYRUK_BEKLEME <= 3600):
        hatalar.append(f"KUYRUK_BEKLEME mantıksız ({config.KUYRUK_BEKLEME}s) — 5-3600 arası olmalı")

    # Kaynak kanal kontrolü
    if not config.KAYNAK_KANALLAR:
        hatalar.append("KAYNAK_KANALLAR listesi boş — dinlenecek kanal yok")

    if hatalar:
        log("KRITIK", "❌ Config hataları:")
        for h in hatalar:
            log("KRITIK", f"  • {h}")
        log("KRITIK", ".env.example dosyasına bak, eksikleri Heroku Config Vars'a ekle.")
        return False

    log("OK", "✅ Config doğrulandı")
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
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    # #3 — SIGTERM/SIGINT yakala (graceful shutdown)
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
    except NotImplementedError:
        # Windows'ta add_signal_handler yok
        log("UYARI", "Signal handler kayıt edilemedi (Windows?)")

    log("SISTEM", "═══════════════════════════════════════════")
    log("SISTEM", "FırsatPulsu v16 başlatılıyor…")
    log("SISTEM", "═══════════════════════════════════════════")

    # Versiyon entegrasyon kontrolü — eski dosya tespit eder
    try:
        from services.analiz import mesaj_bolum_ayir, link_temizle
        from services.sablon import olustur
        from utils.log import simdi_tr
        log("OK", "Modül entegrasyonu doğrulandı (v16)")
    except ImportError as e:
        log("KRITIK", f"Modül eksik veya eski: {e}")
        log("KRITIK", "Lütfen tüm dosyaları yeniden yükle!")
        sys.exit(1)

    if not _config_dogrula():
        sys.exit(1)

    log("SISTEM", (
        f"Min indirim: %{config.MIN_INDIRIM} | "
        f"Kalite: {config.MIN_KALITE} | "
        f"Bekleme: {config.KUYRUK_BEKLEME}s"
    ))

    # #3 SQLite başlat (JSON varsa migrate eder)
    try:
        db.init()
    except Exception as e:
        log("KRITIK", f"DB başlatılamadı: {e}")
        sys.exit(1)

    # ML kategori modelini başlat (yoksa varsayılan setle kur)
    try:
        from utils import ml_kategori
        ml_kategori.ilk_kurulum()
    except Exception as e:
        log("UYARI", f"ML kategori modeli yüklenemedi: {e}")

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

            # İstatistiği Telegram'dan yükle (kalıcılık)
            await cache.telegram_yukle(tg.client)

            mesaj_handler.kaydet(tg.client, kuyruk)
            admin_handler.kaydet(tg.client, kuyruk, tg.bot_client)   # Admin komutları

            # #1 catch_up — restart sırasında kaçan mesajları yakala
            try:
                log("BILGI", "catch_up: kaçan mesajlar yakalanıyor…")
                await tg.client.catch_up()
                log("OK", "catch_up tamamlandı")
            except Exception as e:
                log("UYARI", f"catch_up hatası (yok sayılıyor): {e}")

            await admin_bildir(
                tg.client,
                f"🚀 Bot Başladı v16\n"
                f"Kanal: {len(config.KAYNAK_KANALLAR)}\n"
                f"Min indirim: %{config.MIN_INDIRIM}\n"
                f"Toplam istatistik: {cache.ist_yukle().get('toplam', 0)} fırsat\n\n"
                f"Admin komutları için /yardim yaz.",
            )

            if config.TEST_MODE:
                await _test_gonder(kuyruk)

            # #10 Supervisor pattern — patlayan görevleri yeniden başlat
            import os
            _port = int(os.environ.get("PORT", "8080"))
            _gorev_fabrikalari = {
                "kuyruk_worker": lambda: kuyruk_worker(tg.client, tg.bot_client, kuyruk),
                "watchdog":      lambda: watchdog_calistir(tg.client, kuyruk),
                "gunluk":        lambda: gunluk.zamanlayici(tg.client),
                "surpriz":       lambda: surpriz.zamanlayici(tg.client),
                "haftalik":      lambda: haftalik.zamanlayici(tg.client),
                "cache_kaydet":  lambda: cache.periyodik_kaydet(600),
                "stok_takip":    lambda: stok_takip.kontrol_dongusu(tg.client),
                "gunluk_yedek":  lambda: cache.gunluk_yedek(),
                "health":        lambda: health.baslat(kuyruk, port=_port),
            }
            _gorev_yeniden_baslat_sayilari: dict[str, int] = {}

            def _supervise(ad: str):
                def _bitti(task):
                    if task.cancelled() or _kapanis_baslatildi:
                        return
                    exc = task.exception()
                    if exc is None:
                        return
                    sayim = _gorev_yeniden_baslat_sayilari.get(ad, 0) + 1
                    _gorev_yeniden_baslat_sayilari[ad] = sayim
                    log("KRITIK", f"Görev '{ad}' öldü ({type(exc).__name__}: {exc}) "
                                  f"— yeniden başlatılıyor (deneme #{sayim})")
                    metrik.kayit("gorev_oldu", veri={"ad": ad, "hata": str(exc), "sayim": sayim})

                    # #2 — Admin'e kritik uyarı (her 3 patlama bildirim)
                    if sayim % 3 == 1:
                        asyncio.create_task(izleme.kritik_uyari(
                            tg.client,
                            f"Görev '{ad}' patladı ({sayim}. kez):\n{type(exc).__name__}: {exc}"
                        ))

                    if sayim > 50:
                        log("KRITIK", f"'{ad}' 50+ kez patladı, vazgeçildi")
                        return
                    asyncio.get_event_loop().call_later(
                        min(300, 5 * sayim),
                        lambda: _baslat(ad),
                    )
                return _bitti

            def _baslat(ad: str):
                if _kapanis_baslatildi:
                    return
                t = asyncio.ensure_future(_gorev_fabrikalari[ad]())
                t.add_done_callback(_supervise(ad))

            for ad in _gorev_fabrikalari:
                _baslat(ad)
                log("BILGI", f"Arka plan görevi başlatıldı: {ad}")

            # Ana bekleyiş — disconnect ya da shutdown sinyali
            disconnect_task = asyncio.ensure_future(tg.client.run_until_disconnected())
            shutdown_task  = asyncio.ensure_future(_shutdown_event.wait())
            await asyncio.wait(
                [disconnect_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Graceful shutdown başladıysa
            if _kapanis_baslatildi:
                await _graceful_bekle(kuyruk, max_saniye=30)
                try:
                    await tg.client.disconnect()
                except Exception:
                    pass
                break

        except KeyboardInterrupt:
            log("SISTEM", "Manuel kapatma — çıkılıyor")
            break
        except Exception as e:
            log("HATA", f"Bağlantı koptu: {e}")
            log("BILGI", "30s sonra yeniden bağlanılıyor…")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
