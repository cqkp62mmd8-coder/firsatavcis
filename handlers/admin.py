"""
Admin komut handler — ADMIN_ID'den gelen özel mesajları işler.
Kullanıcı client'ına bağlanır; bot client gerekmez.

Komutlar:
  /durum       — Bot durumu ve anlık istatistik
  /istatistik  — Detaylı istatistik (mağaza/kategori)
  /bekleyen    — Kuyrukta kaç mesaj var
  /temizle     — Görülmüş önbelleği temizle (kanallar yeniden taranır)
  /durdur      — Yeni mesajları kuyruğa almayı durdur
  /baslat      — Kuyruğu tekrar aktifleştir
  /yardim      — Bu listeyi göster
"""
import asyncio
from datetime import datetime

from telethon import TelegramClient, events

import config
import state
from utils.cache import ist_yukle, gorulmus_temizle, ist_kaydet
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


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    if not config.ADMIN_ID:
        log("UYARI", "ADMIN_ID tanımlı değil — admin handler devre dışı")
        return

    admin_id = int(config.ADMIN_ID)

    @client.on(events.NewMessage(from_users=admin_id, func=lambda e: e.is_private))
    async def _admin(event):
        komut = (event.message.text or "").strip().lower().split()[0]

        try:
            if komut in ("/yardim", "/help", "/komutlar", "/start"):
                await event.reply(_YARDIM, parse_mode="html")

            elif komut == "/durum":
                ist = ist_yukle()
                bugun = datetime.now().strftime("%Y-%m-%d")
                durum_ikon = "⏸" if state.durduruldu else "✅"
                durum_yazi = "Duraklatıldı" if state.durduruldu else "Aktif"
                await event.reply(
                    f"{durum_ikon} <b>Bot Durumu: {durum_yazi}</b>\n\n"
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
                await event.reply("✅ Görülmüş önbelleği temizlendi. Kanallar yeniden taranacak.")

            elif komut == "/durdur":
                state.durduruldu = True
                await event.reply("⏸ Bot duraklatıldı.\nYeni mesajlar kuyruğa alınmayacak.")
                log("ADMIN", "Bot duraklatıldı")

            elif komut == "/baslat":
                state.durduruldu = False
                await event.reply("▶️ Bot devam ediyor.")
                log("ADMIN", "Bot devam ettirildi")

            else:
                await event.reply(_YARDIM, parse_mode="html")

        except Exception as e:
            log("HATA", f"Admin handler: {e}")
