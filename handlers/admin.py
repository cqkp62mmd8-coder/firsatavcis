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
    "\n<b>ML Komutları:</b>\n"
    "/mlistatistik — ML model durumu\n"
    "/egit &lt;ana:alt&gt; &lt;metin&gt; — Eğitim örneği ekle\n"
    "/tahmin &lt;metin&gt; — Kategori tahmin et (top-3)\n"
    "/altkat — Tüm kategori hiyerarşisini listele\n"
    "/kfold — 5-fold cross validation (doğruluk testi)\n"
    "/aktiog — Belirsiz tahminleri listele\n"
    "/ogret &lt;sira&gt; &lt;ana:alt&gt; — Belirsizi manuel etiketle\n"
    "/yenidenegit — Modeli sıfırdan yeniden eğit\n"
    "\n<b>Yapay Zeka & Analiz (v18):</b>\n"
    "/markalar — Otomatik öğrenilmiş markalar\n"
    "/trend — Son 24h/7g trend raporu\n"
    "/segment — Kullanıcı tıklama analizi\n"
    "/anomali — Anomali tespit istatistikleri\n"
    "/fiyat — Fiyat zekası kategori profilleri\n"
    "/gemini — Yapay zeka (Gemini) durumu\n"
    "/topluluk — Topluluk oyları & en çok oylananlar\n"
    "/scrape &lt;url&gt; — Ürün sayfası bilgi çıkar\n"
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
            # Yapay zeka durumu
            ai_satir = ""
            try:
                from utils import gemini
                g = gemini.istatistik()
                if g["aktif"]:
                    if g.get("dinlenmede"):
                        ai_satir = "\n🤖 Yapay Zeka: 🟡 yedekte (kota/hata)"
                    else:
                        ai_satir = f"\n🤖 Yapay Zeka: 🟢 Gemini aktif ({g['basari']} analiz)"
                else:
                    ai_satir = "\n🤖 Yapay Zeka: ⚪ saf-Python (Gemini anahtarı yok)"
            except Exception:
                pass
            await event.reply(
                f"{ikon} <b>Bot Durumu: {durum}</b>\n\n"
                f"📅 Bugün: {ist.get('gunluk', {}).get(bugun, 0)} fırsat\n"
                f"📈 Toplam: {ist.get('toplam', 0)} fırsat\n"
                f"📬 Kuyruk: {kuyruk.qsize()} / {kuyruk.maxsize} mesaj"
                f"{ai_satir}",
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

        elif komut == "/altkat":
            await _ml_altkat_listele(event)

        elif komut == "/kfold":
            await _ml_kfold(event)

        elif komut == "/aktiog":
            await _ml_aktif_ogrenme_listele(event)

        elif komut == "/ogret":
            await _ml_ogret(event, mesaj_metin)

        elif komut == "/yenidenegit":
            await _ml_yeniden_egit(event)

        # ── v18 yeni komutlar ──
        elif komut == "/markalar":
            await _markalar_listele(event)

        elif komut == "/trend":
            await _trend_raporu(event)

        elif komut == "/segment":
            await _segment_raporu(event)

        elif komut == "/scrape":
            await _scrape_test(event, mesaj_metin)

        elif komut == "/anomali":
            await _anomali_raporu(event)

        elif komut == "/fiyat":
            await _fiyat_raporu(event)

        elif komut == "/gemini":
            await _gemini_raporu(event)

        elif komut == "/topluluk":
            await _topluluk_raporu(event)

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
        kaynak = ist.get("kaynak_dagilim", {})
        satirlar = [
            f"🤖 <b>ML Kategori Modeli v{ist.get('version', '?')}</b>",
            "",
            f"📚 Toplam örnek: <b>{ist['toplam_ornek']}</b>",
            f"🧠 Vocabulary: <b>{ist['vocab_boyut']}</b> token",
            f"📂 Ana kategori: <b>{ist.get('ana_kategori_sayi', '?')}</b>"
            + (f", alt-grup: <b>{ist.get('alt_grup_sayi', '?')}</b>" if 'alt_grup_sayi' in ist else ""),
            f"📊 Toplam kategori: <b>{ist['kategori_sayi']}</b>",
            "",
            "<b>Eğitim verisi kaynağı:</b>",
            f"  • Varsayılan: <b>{kaynak.get('varsayilan', 0)}</b>",
            f"  • Manuel (/egit): <b>{kaynak.get('manuel', 0)}</b>",
            f"  • Otomatik (kendi kendine öğrenme): <b>{kaynak.get('auto', 0)}</b>",
        ]
        if ist.get("belirsiz_bekleyen"):
            satirlar.append(f"\n⚠️ Belirsiz tahmin bekleyen: <b>{ist['belirsiz_bekleyen']}</b>")
            satirlar.append("   <i>/aktiog ile görüntüle</i>")
        satirlar.append("")
        satirlar.append("<b>En çok örnekli 10 kategori:</b>")
        for kat, sayi in sorted(ist["kategori_sayilari"].items(), key=lambda x: -x[1])[:10]:
            satirlar.append(f"  {kat:25} {sayi}")
        satirlar.append("")
        satirlar.append("<i>Komutlar: /tahmin, /egit, /kfold, /altkat, /trend, /marka, /anomali</i>")
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
        await event.reply("⚠️ Eksik parametre. <code>/egit elektronik:telefon Galaxy S24</code>", parse_mode="html")
        return

    kategori, metin = parcalar[0].lower(), parcalar[1]

    # Kategori formatını kontrol et: 'ana' veya 'ana:alt'
    from utils.ml_kategoriler import KATEGORI_AGAC, ana_kategori_listesi
    if ":" in kategori:
        ana, alt = kategori.split(":", 1)
    else:
        ana, alt = kategori, None

    if ana not in KATEGORI_AGAC:
        await event.reply(
            f"⚠️ Geçersiz ana kategori: <code>{ana}</code>\n"
            f"Geçerli: {', '.join(ana_kategori_listesi())}",
            parse_mode="html",
        )
        return
    if alt and alt not in KATEGORI_AGAC[ana].get("alt", {}):
        from utils.ml_kategoriler import alt_kategori_listesi
        await event.reply(
            f"⚠️ Geçersiz alt kategori: <code>{alt}</code>\n"
            f"<code>{ana}</code> altında: {', '.join(alt_kategori_listesi(ana)) or '(alt yok)'}",
            parse_mode="html",
        )
        return

    try:
        from utils import ml_kategori
        ml_kategori.egit_toplu([(metin, kategori)], kaynak="manuel")
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
    """Top-3 kategori tahmini ile detaylı analiz.
    Kullanım: /tahmin Bosch akülü süpürge"""
    if not mesaj_metin:
        await event.reply("Kullanım: <code>/tahmin &lt;ürün metni&gt;</code>", parse_mode="html")
        return

    try:
        from utils import ml_kategori
        top3 = ml_kategori.tahmin_topk(mesaj_metin, k=3)
        if not top3:
            await event.reply("⚠️ Model boş veya tahmin yapılamadı")
            return

        en_iyi, en_iyi_guven = top3[0]

        satirlar = [f"📦 <b>Metin:</b> {mesaj_metin[:200]}", ""]
        satirlar.append("🤖 <b>Top-3 tahmin:</b>")
        for i, (kat, guven) in enumerate(top3, 1):
            cubuk = "█" * int(guven * 20)
            satirlar.append(f"  {i}. <code>{kat}</code> %{int(guven*100)}")
            satirlar.append(f"     {cubuk}")
        satirlar.append("")
        satirlar.append(f"<i>Yanlışsa: /egit &lt;doğru_kategori&gt; {mesaj_metin[:50]}</i>")

        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Tahmin hatası: {e}")


async def _ml_altkat_listele(event) -> None:
    """Tüm ana ve alt kategorileri ağaç formatında listele."""
    try:
        from utils.ml_kategoriler import KATEGORI_AGAC
        satirlar = ["🌳 <b>Kategori Hiyerarşisi</b>", ""]
        for ana, data in KATEGORI_AGAC.items():
            ikon = data.get("ikon", "•")
            yazi = data.get("yazi", ana)
            satirlar.append(f"{ikon} <b>{ana}</b> — {yazi}")
            for alt, alt_data in data.get("alt", {}).items():
                alt_yazi = alt_data.get("yazi", alt)
                satirlar.append(f"   └ <code>{ana}:{alt}</code> — {alt_yazi}")
            satirlar.append("")
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Liste hatası: {e}")


async def _ml_kfold(event) -> None:
    """5-fold cross validation çalıştır, doğruluk raporu çıkar."""
    await event.reply("⏳ K-fold doğruluk testi başladı, biraz bekleyin (1-2 dk)…")
    try:
        from utils import ml_kategori
        loop = asyncio.get_running_loop()
        # CPU-yoğun iş — thread'de çalıştır
        rapor = await loop.run_in_executor(None, ml_kategori.k_fold_dogruluk, 5)
        if "hata" in rapor:
            await event.reply(f"❌ {rapor['hata']}")
            return

        satirlar = [
            "📊 <b>5-Fold Cross Validation Sonucu</b>",
            "",
            f"🎯 <b>Genel doğruluk:</b> %{int(rapor['dogruluk']*100)} "
            f"({rapor['toplam_dogru']}/{rapor['toplam_ornek']})",
            "",
            "<b>Kategori başına F1:</b>",
        ]
        # F1 skoruna göre sırala
        kat_sirali = sorted(rapor["kategori"].items(), key=lambda x: -x[1]["f1"])
        for kat, m in kat_sirali[:25]:
            satirlar.append(
                f"  <code>{kat[:30]:30}</code> "
                f"F1=<b>{m['f1']}</b> "
                f"(P={m['precision']}, R={m['recall']}, n={m['ornek']})"
            )
        if len(kat_sirali) > 25:
            satirlar.append(f"  <i>… ve {len(kat_sirali)-25} kategori daha</i>")

        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ K-fold hatası: {e}")


async def _ml_aktif_ogrenme_listele(event) -> None:
    """Belirsiz tahmin kuyruğunu listele."""
    try:
        from utils import ml_kategori
        liste = ml_kategori.belirsiz_listele()
        if not liste:
            await event.reply("✨ Belirsiz tahmin yok. Modelin emin olmadığı ürün bulunmuyor.")
            return
        satirlar = [
            f"🎯 <b>Belirsiz Tahminler ({len(liste)})</b>",
            "",
            "<i>Her birini /ogret &lt;sıra&gt; &lt;ana:alt&gt; ile etiketle</i>",
            "",
        ]
        for i, ornek in enumerate(liste[:20], 1):
            metin = ornek["metin"][:60]
            guven = int(ornek["guven"] * 100)
            satirlar.append(f"<b>{i}.</b> [%{guven}] <code>{ornek['tahmin']}</code>")
            satirlar.append(f"     {metin}")
        if len(liste) > 20:
            satirlar.append(f"\n<i>… ve {len(liste)-20} tane daha</i>")
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Liste hatası: {e}")


async def _ml_ogret(event, mesaj_metin: str) -> None:
    """Belirsiz kuyruktaki bir örneği etiketle ve modele kazandır.
    Kullanım: /ogret 3 elektronik:telefon"""
    if not mesaj_metin:
        await event.reply(
            "Kullanım: <code>/ogret &lt;sıra&gt; &lt;ana:alt&gt;</code>\n"
            "Önce <code>/aktiog</code> ile listeyi gör.",
            parse_mode="html",
        )
        return
    parcalar = mesaj_metin.strip().split(maxsplit=1)
    if len(parcalar) < 2:
        await event.reply("⚠️ Eksik parametre.")
        return
    try:
        sira = int(parcalar[0])
    except ValueError:
        await event.reply("⚠️ Sıra numarası geçersiz.")
        return

    kategori = parcalar[1].strip().lower()
    try:
        from utils import ml_kategori
        from utils.ml_kategoriler import KATEGORI_AGAC

        # Kategori doğrula
        ana = kategori.split(":", 1)[0]
        alt = kategori.split(":", 1)[1] if ":" in kategori else ""
        if ana not in KATEGORI_AGAC:
            await event.reply(
                f"⚠️ Geçersiz ana kategori: <code>{ana}</code>\n"
                f"Geçerli olanlar: <code>/altkat</code>",
                parse_mode="html",
            )
            return
        if alt and alt not in KATEGORI_AGAC[ana].get("alt", {}):
            await event.reply(
                f"⚠️ Geçersiz alt kategori: <code>{alt}</code>\n"
                f"'{ana}' altındaki seçenekleri görmek için <code>/altkat</code>",
                parse_mode="html",
            )
            return

        loop = asyncio.get_running_loop()
        basari, msg = await loop.run_in_executor(
            None, ml_kategori.belirsiz_eslestir_ve_egit, sira, ana, alt
        )
        if basari:
            await event.reply(f"✅ {msg}", parse_mode=None)
        else:
            await event.reply(f"⚠️ {msg}")
    except Exception as e:
        await event.reply(f"❌ Öğret hatası: {e}")


async def _ml_yeniden_egit(event) -> None:
    """Modeli baştan eğit (mevcut tüm eğitim verisiyle)."""
    try:
        from utils import ml_kategori
        loop = asyncio.get_running_loop()
        sayi = await loop.run_in_executor(None, ml_kategori.yeniden_egit)
        await event.reply(f"✅ Model yeniden eğitildi: {sayi} örnek")
    except Exception as e:
        await event.reply(f"❌ Eğitim hatası: {e}")


async def _markalar_listele(event) -> None:
    """Otomatik öğrenilmiş markaları + bekleyen adayları listele."""
    try:
        from utils import marka_ogrenme
        ist = marka_ogrenme.istatistik()
        markalar = marka_ogrenme.marka_listesi()
        adaylar = marka_ogrenme.aday_listesi(limit=15)

        satirlar = [
            "🏷️ <b>Marka Öğrenme Sistemi</b>",
            "",
            f"📊 Toplam kayıt: <b>{ist['toplam_kayit']}</b>",
            f"✅ Öğrenilmiş marka: <b>{ist['ogrenilen_marka']}</b>",
            f"⏳ Bekleyen aday: <b>{ist['marka_adayi']}</b>",
            "",
        ]
        if markalar:
            satirlar.append("<b>Öğrenilmiş markalar (top 20):</b>")
            for m in sorted(markalar, key=lambda x: -x["sayim"])[:20]:
                satirlar.append(f"  • <b>{m['marka']}</b> → {m['kategori']} ({m['sayim']} örnek)")
        else:
            satirlar.append("<i>Henüz hiç marka öğrenilmedi — daha çok mesaj akışına ihtiyaç var.</i>")

        if adaylar:
            satirlar.append("")
            satirlar.append("<b>Marka adayı (yakında öğrenilecek):</b>")
            for a in adaylar[:10]:
                kat_str = ", ".join(f"{k}:{v}" for k, v in a["kategoriler"].items())
                satirlar.append(f"  • {a['aday']} (top: {a['toplam']}, {kat_str})")

        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Marka listesi hatası: {e}")


async def _trend_raporu(event) -> None:
    """Son 24h/7g trend raporu."""
    try:
        from utils import trend
        son_24 = trend.son_n_saat(24)
        son_168 = trend.son_n_saat(168)   # 7 gün
        yukselen = trend.yukselen_kategoriler(24)

        satirlar = [
            "📈 <b>Trend Raporu</b>",
            "",
            f"🕐 Son 24 saat: <b>{son_24['toplam']}</b> paylaşım",
            f"📅 Son 7 gün: <b>{son_168['toplam']}</b> paylaşım",
            "",
            "<b>Son 24h - En Popüler Kategoriler:</b>",
        ]
        if son_24["kategoriler"]:
            for kat, sayi in son_24["kategoriler"][:8]:
                satirlar.append(f"  • {kat:25} <b>{sayi}</b>")
        else:
            satirlar.append("  <i>(henüz veri yok)</i>")

        satirlar.append("\n<b>Son 7 gün - Genel Eğilim:</b>")
        if son_168["kategoriler"]:
            for kat, sayi in son_168["kategoriler"][:8]:
                satirlar.append(f"  • {kat:25} <b>{sayi}</b>")
        else:
            satirlar.append("  <i>(henüz veri yok)</i>")

        if yukselen:
            satirlar.append("\n🔥 <b>Yükselen Kategoriler (son 24h):</b>")
            for kat, oran in yukselen[:5]:
                satirlar.append(f"  • <b>{kat}</b> → <b>{oran}x</b> artış")

        if son_24["magazalar"]:
            satirlar.append("\n<b>En Aktif Mağazalar (24h):</b>")
            for m, sayi, ort_ind in son_24["magazalar"][:8]:
                satirlar.append(f"  • {m:25} <b>{sayi}</b> paylaşım (ort %{ort_ind} ind.)")

        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Trend raporu hatası: {e}")


async def _segment_raporu(event) -> None:
    """Kullanıcı segmentasyon — tıklama analizi."""
    try:
        from utils import segment
        ist = segment.istatistik()
        populer_kat = segment.populer_kategoriler(gun=7)[:10]
        populer_mag = segment.populer_magazalar(gun=7)[:10]
        supheli = segment.supheli_magazalar(gun=30)
        saatler = segment.saatlik_aktivite(gun=7)

        satirlar = [
            "👥 <b>Kullanıcı Segmentasyon</b>",
            "",
            f"📊 Toplam tıklama: <b>{ist.get('toplam_tikla', 0)}</b>",
            f"🔥 İyi oy: <b>{ist.get('iyi_oy', 0)}</b>",
            f"❌ Sahte oy: <b>{ist.get('sahte_oy', 0)}</b>",
            f"👤 Benzersiz kullanıcı: <b>{ist.get('benzersiz_kullanici', 0)}</b>",
            "",
        ]

        if populer_kat:
            satirlar.append("<b>En Popüler Kategoriler (7gün):</b>")
            for k in populer_kat:
                satirlar.append(
                    f"  • {k['kategori']:20} 🔥{k['iyi_oy']} ❌{k['sahte_oy']}"
                )

        if populer_mag:
            satirlar.append("\n<b>En Popüler Mağazalar (7gün):</b>")
            for m in populer_mag:
                satirlar.append(
                    f"  • {m['magaza']:25} 🔥{m['iyi_oy']} ❌{m['sahte_oy']}"
                )

        if supheli:
            satirlar.append("\n⚠️ <b>Şüpheli Mağazalar (sahte &gt; iyi):</b>")
            for m in supheli:
                satirlar.append(f"  • {m['magaza']}: ❌{m['sahte_oy']} vs 🔥{m['iyi_oy']}")

        # En aktif 3 saat
        if any(saatler):
            en_aktif = sorted(enumerate(saatler), key=lambda x: -x[1])[:3]
            satirlar.append("\n⏰ <b>En Aktif Saatler (7gün):</b>")
            for saat, sayi in en_aktif:
                if sayi > 0:
                    satirlar.append(f"  • {saat:02d}:00 — <b>{sayi}</b> tıklama")

        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Segment raporu hatası: {e}")


async def _scrape_test(event, url: str) -> None:
    """Bir URL'yi scraping ile test et."""
    url = (url or "").strip()
    if not url or not url.startswith(("http://", "https://")):
        await event.reply("Kullanım: /scrape https://www.trendyol.com/...")
        return
    try:
        from services import scraping
        if not scraping.destekleniyor_mu(url):
            await event.reply(
                f"❌ Bu domain desteklenmiyor.\n"
                f"<i>Desteklenenler:</i> Trendyol, Hepsiburada, Amazon TR, "
                f"N11, Teknosa, Gratis, Boyner, MediaMarkt, Vatan, Morhipo, Watsons",
                parse_mode="html"
            )
            return
        loop = asyncio.get_running_loop()
        bilgi = await loop.run_in_executor(None, scraping.urun_bilgisi, url)
        if not bilgi:
            await event.reply("❌ Sayfa açılamadı veya meta veri yok.")
            return
        satirlar = [
            "🌐 <b>Web Scrape Sonucu</b>",
            "",
            f"<b>Mağaza:</b> {bilgi.get('magaza', '-')}",
            f"<b>Ürün adı:</b> {bilgi.get('ad') or '<i>bulunamadı</i>'}",
            f"<b>Fiyat:</b> {bilgi.get('fiyat') or '<i>bulunamadı</i>'} TL",
            f"<b>Stok:</b> {bilgi.get('stok') or '<i>belirsiz</i>'}",
            f"<b>Görsel:</b> {'✓ var' if bilgi.get('gorsel') else '<i>yok</i>'}",
        ]
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Scrape hatası: {e}")


async def _anomali_raporu(event) -> None:
    """Anomali tespit istatistikleri."""
    try:
        from utils import anomali
        ist = anomali.istatistik()
        satirlar = ["🚨 <b>Anomali Tespit Sistemi</b>", ""]
        satirlar.append("<b>Öğrenilmiş normaller</b> (z-score temeli):")
        for ad, s in ist.items():
            satirlar.append(f"  • {ad}: n={s['n']}, ort={s['ort']}, std={s['std']}")
        satirlar.append("")
        satirlar.append("<i>Bu eşiklerden 4+ sapma → mesaj atılır</i>")
        satirlar.append("<i>Hard kurallar: %95+ indirim, &lt;10 TL fiyat, %30+ emoji</i>")
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Anomali rapor hatası: {e}")


async def _topluluk_raporu(event) -> None:
    """Topluluk etkileşim raporu — en çok oylanan fırsatlar."""
    try:
        from utils import segment
        ozet = segment.oy_ozeti(7)
        en_cok = segment.en_cok_oylanan(7, 5)
        satirlar = [
            "\U0001F465 <b>Topluluk Etkileşimi</b> (son 7 gün)",
            "",
            f"\U0001F525 Toplam kaçmaz oyu: <b>{ozet['iyi']}</b>",
            f"\u274C Toplam uyarı: <b>{ozet['sahte']}</b>",
            f"\U0001F4CA Toplam oy: <b>{ozet['toplam']}</b>",
        ]
        if en_cok:
            satirlar.append("")
            satirlar.append("<b>En çok oylanan fırsatlar:</b>")
            for i, m in enumerate(en_cok, 1):
                satirlar.append(
                    f"  {i}. Mesaj #{m['mesaj_id']}: "
                    f"\U0001F525{m['iyi']} \u274C{m['sahte']} (net +{m['net']})"
                )
        else:
            satirlar.append("")
            satirlar.append("<i>Henüz oy yok — fırsatlar oylandıkça görünür.</i>")

        # Beğenilen kategoriler (kategori bazlı topluluk ilgisi)
        try:
            kats = segment.begenilen_kategoriler(30, 5)
            if kats:
                satirlar.append("")
                satirlar.append("<b>En beğenilen kategoriler (30 gün):</b>")
                for k in kats:
                    satirlar.append(f"  • {k['kategori']}: \U0001F525{k['iyi']} \u274C{k['sahte']}")
        except Exception:
            pass
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"\u274C Topluluk raporu hatası: {e}")


async def _gemini_raporu(event) -> None:
    """Gemini yapay zeka durum raporu."""
    try:
        from utils import gemini
        ist = gemini.istatistik()
        durum = "🟢 AKTİF" if ist["aktif"] else "🔴 DEVRE DIŞI (anahtar yok)"
        if ist.get("dinlenmede"):
            durum = "🟡 GEÇİCİ DİNLENMEDE (kota/hata — yedekte)"
        satirlar = [
            "🤖 <b>Gemini Yapay Zeka</b>",
            "",
            f"Durum: <b>{durum}</b>",
            f"Model: <code>{ist['model']}</code>",
            "",
            f"📤 Toplam istek: {ist['istek']}",
            f"✅ Başarılı: {ist['basari']}",
            f"⚠️ Hata: {ist['hata']}",
            f"💾 Cache: {ist['cache_boyut']} mesaj",
            "",
            "<i>Gemini aktifken mesajları gerçekten anlar (kalıp/örnek yok). "
            "Kota dolsa/hata olsa bot otomatik saf-Python yedeğe döner.</i>",
        ]
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Gemini rapor hatası: {e}")


async def _fiyat_raporu(event) -> None:
    """Fiyat zekası raporu — kategori bazlı fiyat profilleri."""
    try:
        from utils import fiyat_zekasi
        ist = fiyat_zekasi.istatistik()
        profiller = fiyat_zekasi.tum_profiller()
        satirlar = [
            "💰 <b>Fiyat Zekası</b>",
            "",
            f"📊 İzlenen kategori: <b>{ist['kategori_sayisi']}</b>",
            f"🔢 Toplam gözlem: <b>{ist['toplam_gozlem']}</b>",
            "",
            "<b>Kategori fiyat profilleri:</b>",
        ]
        # En çok örneği olan 12 kategori
        profiller = [p for p in profiller if p.get("ornek", 0) >= 5]
        profiller.sort(key=lambda x: -x.get("ornek", 0))
        for p in profiller[:12]:
            satirlar.append(
                f"  • {p['kategori']:24} ort {p['ortalama']:.0f} TL "
                f"(medyan {p['medyan']:.0f}, n={p['ornek']})"
            )
        if not profiller:
            satirlar.append("  <i>(henüz yeterli veri yok — paylaşım yapıldıkça öğrenir)</i>")
        satirlar.append("")
        satirlar.append("<i>Her fırsat o kategorinin tipik fiyatına göre değerlendirilir.</i>")
        await event.reply("\n".join(satirlar), parse_mode="html")
    except Exception as e:
        await event.reply(f"❌ Fiyat raporu hatası: {e}")


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
