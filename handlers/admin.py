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
    "/tani — Yüklü modüllerin versiyon teşhisi\n"
    "/bekleyen — Kuyruk bilgisi\n"
    "/hosgeldin — Kanala hoşgeldin mesajı sabitler\n"
    "/temizle — Görülmüş önbelleği sıfırla\n"
    "/durdur — Gönderimi duraklat\n"
    "/baslat — Gönderimi devam ettir\n"
    "<b>ML Komutları:</b>\n"
    "/mlistatistik — ML model durumu\n"
    "/egit &lt;kategori&gt; &lt;metin&gt; — Yeni eğitim örneği\n"
    "/tahmin &lt;metin&gt; — Bir metin için kategori tahmin et\n"
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
    full_text = (event.message.text or "").strip()
    parcalar = full_text.split(maxsplit=1)
    komut = parcalar[0].lower() if parcalar else ""
    mesaj_metin = parcalar[1] if len(parcalar) > 1 else ""

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

        elif komut == "/tani":
            await _tani_raporu(event)

        elif komut == "/mlistatistik":
            await _ml_istatistik(event)

        elif komut == "/egit":
            await _ml_egit(event, mesaj_metin)

        elif komut == "/tahmin":
            await _ml_tahmin(event, mesaj_metin)

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


async def _tani_raporu(event) -> None:
    """Yüklü modüllerin v12 fonksiyonlarını kontrol eder.
    Eski dosya tespit eder."""
    import importlib

    beklenenler = {
        "services.analiz": [
            "mesaj_bolum_ayir", "link_temizle", "_MARKA_KAMPANYA_KALIP",
            "magaza_bul", "urun_adi_bul",
        ],
        "services.sablon": [
            "negatif_mi", "trend_kaydet", "olustur_coklu",
            "_tasarruf_hesapla", "_fiyat_format", "_baslik",
        ],
        "services.zenginlestir": ["guvenilirlik_etiketi"],
        "services.stok_takip":   ["kayit_ekle", "kontrol_dongusu"],
        "services.gorsel":       ["logo_ekle"],
        "utils.log":             ["simdi_tr", "TR_TZ"],
        "utils.cache":           ["telegram_yukle", "periyodik_kaydet"],
        "utils.ml_kategori":     ["tahmin", "egit_tek", "ilk_kurulum"],
        "handlers.mesaj":        ["_blok_analiz"],
    }

    satirlar = ["🔍 <b>Modül Teşhisi</b>", ""]
    toplam_eksik = 0
    for mod_ad, fonksiyonlar in beklenenler.items():
        try:
            m = importlib.import_module(mod_ad)
            eksik = [f for f in fonksiyonlar if not hasattr(m, f)]
            if eksik:
                satirlar.append(f"❌ <code>{mod_ad}</code>")
                satirlar.append(f"   eksik: {', '.join(eksik)}")
                toplam_eksik += len(eksik)
            else:
                satirlar.append(f"✅ <code>{mod_ad}</code>")
        except ImportError as e:
            satirlar.append(f"❌ <code>{mod_ad}</code> import edilemiyor: {e}")
            toplam_eksik += 5

    if toplam_eksik == 0:
        satirlar.insert(2, "<b>✅ Tüm modüller v12 — temiz</b>\n")
    else:
        satirlar.insert(2, f"<b>⚠️ {toplam_eksik} eksik bulundu — dosyalar eski!</b>")
        satirlar.append("")
        satirlar.append("Çözüm: firsatpulsu_v16.zip'i yeniden yükle, tüm dosyaların üzerine yaz.")

    await event.reply("\n".join(satirlar), parse_mode="html")


async def _ml_istatistik(event) -> None:
    """ML model durumu raporla."""
    try:
        from utils import ml_kategori
        ist = ml_kategori.istatistik()
        satirlar = [
            "🤖 <b>ML Kategori Modeli</b>",
            "",
            f"📚 Toplam örnek: <b>{ist['toplam_ornek']}</b>",
            f"🧠 Vocabulary: <b>{ist['vocab_boyut']}</b> token",
            f"📂 Kategori sayısı: <b>{ist['kategori_sayi']}</b>",
            "",
            "<b>Kategori başına örnek:</b>",
        ]
        for kat, sayi in sorted(ist["kategori_sayilari"].items(), key=lambda x: -x[1]):
            satirlar.append(f"  {kat:12} {sayi}")
        satirlar.append("")
        satirlar.append("<i>Komutlar:</i>")
        satirlar.append("  /egit &lt;kategori&gt; &lt;metin&gt;")
        satirlar.append("  /tahmin &lt;metin&gt;")
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ ML modülü hatası: {e}")


async def _ml_egit(event, mesaj_metin: str) -> None:
    """Tek bir eğitim örneği ekle.
    Kullanım: /egit elektronik Bosch akülü süpürge"""
    if not mesaj_metin:
        await event.reply(
            "Kullanım: <code>/egit &lt;kategori&gt; &lt;metin&gt;</code>\n\n"
            "Kategoriler: elektronik, giyim, kozmetik, ev, market, "
            "spor, oyun, bebek, saglik, otomotiv",
            parse_mode="html",
        )
        return

    parcalar = mesaj_metin.strip().split(maxsplit=1)
    if len(parcalar) < 2:
        await event.reply("⚠️ Eksik parametre. <code>/egit elektronik metin</code>", parse_mode="html")
        return

    kategori, metin = parcalar[0].lower(), parcalar[1]
    if kategori not in config.KATEGORILER:
        await event.reply(
            f"⚠️ Geçersiz kategori: <code>{kategori}</code>\n"
            f"Geçerli: {', '.join(config.KATEGORILER.keys())}",
            parse_mode="html",
        )
        return

    try:
        from utils import ml_kategori
        ml_kategori.egit_toplu([(metin, kategori)])
        # Tahmin et, doğrulukla göster
        kat, guven = ml_kategori.tahmin(metin)
        await event.reply(
            f"✅ Eğitildi: <code>{kategori}</code>\n"
            f"📦 Metin: {metin}\n"
            f"🤖 Şimdiki tahmin: <code>{kat}</code> ({int(guven*100)}%)",
            parse_mode="html",
        )
    except Exception as e:
        await event.reply(f"❌ Eğitim hatası: {e}")


async def _ml_tahmin(event, mesaj_metin: str) -> None:
    """Bir metin için ML tahminini göster.
    Kullanım: /tahmin Bosch akülü süpürge"""
    if not mesaj_metin:
        await event.reply("Kullanım: <code>/tahmin &lt;ürün metni&gt;</code>", parse_mode="html")
        return

    try:
        from utils import ml_kategori
        kat, guven = ml_kategori.tahmin(mesaj_metin)
        # Keyword karşılaştırması için kategori_bul'u da çalıştır
        from services.analiz import kategori_bul
        hibrit_kat, _, _ = kategori_bul(mesaj_metin)

        await event.reply(
            f"📦 <b>Metin:</b> {mesaj_metin[:200]}\n\n"
            f"🤖 <b>ML tahmini:</b> <code>{kat}</code> (%{int(guven*100)})\n"
            f"🎯 <b>Hibrit sonuç:</b> <code>{hibrit_kat}</code>\n\n"
            f"<i>Yanlışsa: /egit &lt;doğru_kategori&gt; {mesaj_metin[:50]}</i>",
            parse_mode="html",
        )
    except Exception as e:
        await event.reply(f"❌ Tahmin hatası: {e}")


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
