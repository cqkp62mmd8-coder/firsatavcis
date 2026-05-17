"""
Admin komut handler — bota gelen mesajları işler (bot_client üzerinden).
BOT_TOKEN yoksa kullanıcı client'ına fallback yapar (/ ile başlayan mesajlar).

Komutlar:
  /durum       — Bot durumu ve anlık istatistik
  /istatistik  — Detaylı istatistik (mağaza/kategori)
  /bekleyen    — Kuyrukta kaç mesaj var
  /temizle     — Görülmüş önbelleği temizle
  /durdur      — Yeni mesajları kuyruğa almayı durdur
  /baslat      — Kuyruğu tekrar aktifleştir
  /yardim      — Bu listeyi göster
"""
import asyncio
from datetime import datetime

from telethon import TelegramClient, events

import config
import state
from utils.cache import ist_yukle, gorulmus_temizle
from utils.log import log

_YARDIM = (
    "📋 <b>Admin Komutları</b>\n\n"
    "/durum — Bot durumu\n"
    "/istatistik — Detaylı istatistik\n"
    "/bekleyen — Kuyruk bilgisi\n"
    "/temizle — Görülmüş önbelleği sıfırla\n"
    "/durdur — Gönderimi duraklat\n"
    "/baslat — Gönderimi devam ettir\n"
    "/yardim — Bu listeyi göster"
)


async def _komut_isle(event, kuyruk: asyncio.Queue) -> None:
    """Gelen komutu işler. Hem bot hem user client için ortak."""
    komut = (event.message.text or "").strip().lower().split()[0]

    try:
        if komut in ("/yardim", "/help", "/start"):
            await event.reply(_YARDIM, parse_mode="html")

        elif komut == "/durum":
            ist = ist_yukle()
            bugun = datetime.now().strftime("%Y-%m-%d")
            ikon = "⏸" if state.durduruldu else "✅"
            durum = "Duraklatıldı" if state.durduruldu else "Aktif"
            await event.reply(
                f"{ikon} <b>Bot Durumu: {durum}</b>\n\n"
                f"📅 Bugün: {ist.get('gunluk', {}).get(bugun, 0)} fırsat\n"
                f"📈 Toplam: {ist.get('toplam', 0)} fırsat\n"
                f"📬 Kuyruk: {kuyruk.qsize()} / {kuyruk.maxsize} mesaj",
                parse_mode="html",
            )

        elif komut == "/istatistik":
            ist = ist_yukle()
            kats = ist.get("kategoriler", {})
            mags = ist.get("magazalar", {})
            en_kat = max(kats, key=kats.get) if kats else "-"
            en_mag = max(mags, key=mags.get) if mags else "-"
            mag_str = "\n".join(
                f"  {m}: {c}"
                for m, c in sorted(mags.items(), key=lambda x: -x[1])[:6]
            )
            await event.reply(
                f"📊 <b>İstatistikler</b>\n\n"
                f"Toplam: {ist.get('toplam', 0)} fırsat\n"
                f"🏆 En iyi kategori: {en_kat}\n"
                f"🏪 En iyi mağaza: {en_mag}\n\n"
                f"<b>Top Mağazalar:</b>\n{mag_str}",
                parse_mode="html",
            )

        elif komut == "/bekleyen":
            await event.reply(
                f"📬 Kuyrukta <b>{kuyruk.qsize()}</b> mesaj bekliyor "
                f"(max: {kuyruk.maxsize})",
                parse_mode="html",
            )

        elif komut == "/temizle":
            gorulmus_temizle()
            await event.reply("✅ Görülmüş önbelleği temizlendi.")

        elif komut == "/durdur":
            state.durduruldu = True
            await event.reply("⏸ Bot duraklatıldı. Yeni mesajlar kuyruğa alınmayacak.")
            log("ADMIN", "Bot duraklatıldı")

        elif komut == "/baslat":
            state.durduruldu = False
            await event.reply("▶️ Bot devam ediyor.")
            log("ADMIN", "Bot devam ettirildi")

        # Bilinmeyen komutlar sessizce yok sayılır

    except Exception as e:
        log("HATA", f"Admin komut: {e}")


def kaydet(
    client: TelegramClient,
    kuyruk: asyncio.Queue,
    bot_client: TelegramClient | None = None,
) -> None:
    if not config.ADMIN_ID:
        log("UYARI", "ADMIN_ID tanımlı değil — admin handler devre dışı")
        return

    admin_id = int(config.ADMIN_ID)

    if bot_client:
        # ── Bot client: bota gelen mesajlarda çalışır ──────────────
        @bot_client.on(events.NewMessage(func=lambda e: e.is_private))
        async def _bot_admin(event):
            # Sadece admin'den gelen mesajlar
            sender = await event.get_sender()
            if not sender or sender.id != admin_id:
                return
            if not (event.message.text or "").startswith("/"):
                return
            await _komut_isle(event, kuyruk)

        log("OK", "Admin handler: bot üzerinden aktif — bota /yardim yaz")

    else:
        # ── Fallback: kullanıcı client'ı, sadece / komutları ───────
        @client.on(events.NewMessage(
            from_users=admin_id,
            func=lambda e: e.is_private and (e.message.text or "").startswith("/"),
        ))
        async def _user_admin(event):
            await _komut_isle(event, kuyruk)

        log("UYARI", "Admin handler: BOT_TOKEN yok, kullanıcı client fallback aktif")
