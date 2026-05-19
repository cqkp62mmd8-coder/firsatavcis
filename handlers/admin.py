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
from utils.log import log, simdi_tr

_YARDIM = (
    "📋 <b>Admin Komutları</b>\n\n"
    "/durum — Bot durumu\n"
    "/istatistik — Detaylı istatistik\n"
    "/rapor — Gün/saat/kategori detay raporu\n"
    "/bekleyen — Kuyruk bilgisi\n"
    "/hosgeldin — Kanala hoşgeldin mesajı sabitler\n"
    "/temizle — Görülmüş önbelleği sıfırla\n"
    "/durdur — Gönderimi duraklat\n"
    "/baslat — Gönderimi devam ettir\n"
    "/yardim — Bu listeyi göster"
)


_HOSGELDIN_METNI = """👋 <b>FırsatPulsu'ya Hoş Geldin!</b>

Türkiye'nin en iyi e-ticaret fırsatlarını otomatik olarak takip eden bot kanalı.

✅ Trendyol, Hepsiburada, Amazon, MediaMarkt ve daha fazlası
✅ Sahte indirim filtresi — sadece gerçek fırsatlar
✅ Saatlik güncel paylaşım, günün en iyileri 21:00'de
✅ Sürpriz fırsatlar 12:00-20:00 arası

🔔 <b>Bildirimleri aç</b>, fırsatları kaçırma!

📊 <b>Etiketler</b>: #FırsatPulsu #Elektronik #Giyim #Kozmetik

⚠️ Bot otomatik çalışır, paylaşılan fiyatlar değişebilir.
Satın almadan önce mutlaka kontrol edin.
"""


async def _komut_isle(event, kuyruk: asyncio.Queue) -> None:
    """Gelen komutu işler. Hem bot hem user client için ortak."""
    komut = (event.message.text or "").strip().lower().split()[0]

    try:
        if komut in ("/yardim", "/help", "/start"):
            await event.reply(_YARDIM, parse_mode="html")

        elif komut == "/durum":
            ist = ist_yukle()
            bugun = simdi_tr().strftime("%Y-%m-%d")
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

        elif komut == "/rapor":
            await _rapor_olustur(event)

        elif komut == "/hosgeldin":
            await _hosgeldin_pinle(event)

        # Bilinmeyen komutlar sessizce yok sayılır

    except Exception as e:
        log("HATA", f"Admin komut: {e}")


async def _rapor_olustur(event) -> None:
    """Detaylı rapor: gün/saat/kategori/mağaza performansı."""
    from datetime import timedelta
    ist = ist_yukle()
    simdi = simdi_tr()

    # Son 7 gün
    son_7g = 0
    son_30g = 0
    for i in range(30):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        sayi = ist.get("gunluk", {}).get(gun, 0)
        if i < 7:
            son_7g += sayi
        son_30g += sayi

    # Top 5 mağaza ve kategori
    mags = ist.get("magazalar", {})
    kats = ist.get("kategoriler", {})
    kanallar = ist.get("kanallar", {})

    top_mag = sorted(mags.items(), key=lambda x: -x[1])[:5]
    top_kat = sorted(kats.items(), key=lambda x: -x[1])[:5]
    top_kan = sorted(kanallar.items(), key=lambda x: -x[1])[:5]

    from config import KATEGORI_YAZI
    bugun_str = simdi.strftime("%Y-%m-%d")
    dun_str   = (simdi - timedelta(days=1)).strftime("%Y-%m-%d")

    satirlar = [
        "📊 <b>DETAYLI RAPOR</b>",
        f"<i>Tarih: {simdi.strftime('%d %b %Y, %H:%M')}</i>",
        "",
        "📅 <b>Zaman bazında</b>",
        f"  Bugün:  {ist.get('gunluk', {}).get(bugun_str, 0)} fırsat",
        f"  Dün:    {ist.get('gunluk', {}).get(dun_str, 0)} fırsat",
        f"  7 gün:  {son_7g} fırsat",
        f"  30 gün: {son_30g} fırsat",
        f"  Toplam: {ist.get('toplam', 0)} fırsat",
        "",
    ]

    if top_mag:
        satirlar.append("🏪 <b>Top mağazalar</b>")
        for m, c in top_mag:
            satirlar.append(f"  {m}: {c}")
        satirlar.append("")

    if top_kat:
        satirlar.append("📂 <b>Top kategoriler</b>")
        for k, c in top_kat:
            yazi = KATEGORI_YAZI.get(k, k)
            satirlar.append(f"  {yazi}: {c}")
        satirlar.append("")

    if top_kan:
        satirlar.append("📡 <b>Top kaynak kanallar</b>")
        for k, c in top_kan:
            satirlar.append(f"  @{k}: {c}")

    await event.reply("\n".join(satirlar), parse_mode="html")


async def _hosgeldin_pinle(event) -> None:
    """Kanala hoşgeldin mesajını gönder ve sabitle.
    Kullanıcı/Bot client farkına bakmaksızın admin event'in geldiği client'tan yollar."""
    try:
        client = event.client
        # Bot mu user mı bilmemiz lazım — kanala bot yazamaz (admin değilse)
        # Kullanıcı client'ı kullan, çünkü o zaten kanalın sahibi
        import client as tg_client
        kanal_client = tg_client.client   # Kullanıcı client'ı kesin sahip

        msg = await kanal_client.send_message(
            config.HEDEF_KANAL,
            _HOSGELDIN_METNI,
            parse_mode="html",
            link_preview=False,
        )
        try:
            await kanal_client.pin_message(config.HEDEF_KANAL, msg.id, notify=False)
            await event.reply("✅ Hoşgeldin mesajı kanala gönderildi ve sabitlendi.")
        except Exception as e:
            await event.reply(f"⚠️ Mesaj gönderildi ama sabitlenemedi: {e}")
    except Exception as e:
        await event.reply(f"❌ Hata: {e}")


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
