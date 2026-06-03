"""
Kuyruk worker: kuyruktaki mesajları KUYRUK_BEKLEME saniye arayla kanala gönderir.

#4 — FloodWaitError yakalama + adaptif bekleme
#10 — Supervisor pattern (worker patlasa otomatik yeniden başlar)
"""
import asyncio
from io import BytesIO

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

import config
import state
from services.gorsel import logo_ekle
from utils.cache import ist_guncelle
from utils import metrik
from utils.log import log, gece_modu_aktif

_MAX_RETRY = 3

# #4 — FloodWait sonrası adaptif bekleme süresi çarpanı
# Her FloodWait alındığında bir sonraki gönderim daha yavaş olur
_floodwait_carpani: float = 1.0
_son_floodwait_zaman: float = 0.0

# Son paylaşılan ürün — admin /yanlis komutuyla kategori düzeltmesi için
_son_paylasilan: dict | None = None


def son_paylasilani_al() -> dict | None:
    """Son paylaşılan ürünün bilgisini döndürür (admin düzeltmesi için)."""
    return _son_paylasilan


# ── Kuyruk Kalıcılığı (G): restart'ta bekleyen görevler kaybolmasın ──

import os as _os
import json as _json

_KUYRUK_DOSYA = _os.path.join(config.DATA_DIR, "kuyruk_kalan.json")


def kuyruk_kaydet(kuyruk) -> int:
    """Bekleyen kuyruk öğelerini diske yaz. Bot kapanırken çağrılır.
    Görsel byte'ları atılır (çok büyük) — restart'ta tekrar indirilir.
    Döner: kaydedilen öğe sayısı."""
    if kuyruk is None:
        return 0
    kalanlar = []
    try:
        while not kuyruk.empty():
            try:
                ogeler = kuyruk.get_nowait()
            except Exception:
                break
            # Tuple yapısı: (sablon, gorsel_bytes, linkler, magaza, kat, kanal, indirim, fs)
            try:
                sablon, _gorsel, linkler, magaza, kat, kanal, indirim, fs = ogeler
                kalanlar.append({
                    "sablon":  sablon,
                    "linkler": list(linkler) if linkler else [],
                    "magaza":  magaza,
                    "kat":     kat,
                    "kanal":   kanal,
                    "indirim": int(indirim) if indirim else 0,
                    "fs":      float(fs) if fs else 0.0,
                })
            except Exception:
                pass
            try:
                kuyruk.task_done()
            except Exception:
                pass
        if kalanlar:
            _os.makedirs(_os.path.dirname(_KUYRUK_DOSYA) or ".", exist_ok=True)
            gecici = _KUYRUK_DOSYA + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                _json.dump({"ts": int(__import__("time").time()),
                            "ogeler": kalanlar}, f, ensure_ascii=False)
            _os.replace(gecici, _KUYRUK_DOSYA)
            log("OK", f"Kuyruk kalıcılığı: {len(kalanlar)} bekleyen öğe diske kaydedildi")
    except Exception as e:
        log("UYARI", f"Kuyruk kaydet: {e}")
    return len(kalanlar)


def kuyruk_yukle(kuyruk) -> int:
    """Önceki kapanışta kaydedilen görevleri kuyruğa geri yükle.
    Bot başlangıcında çağrılır. Görsel byte'sız yüklenir (worker fallback'i
    görsel olmadan metin gönderir). Döner: yüklenen öğe sayısı."""
    if not _os.path.exists(_KUYRUK_DOSYA):
        return 0
    try:
        with open(_KUYRUK_DOSYA, encoding="utf-8") as f:
            veri = _json.load(f)
        ogeler = veri.get("ogeler", [])
        kac_saat_once = (int(__import__("time").time()) - veri.get("ts", 0)) / 3600
        # 12 saatten eski görevleri yükleme (bayatlamış fırsat)
        if kac_saat_once > 12:
            log("BILGI", f"Kuyruk kalıcılığı: {len(ogeler)} öğe çok eski "
                          f"({kac_saat_once:.1f}h) — atlandı")
            try: _os.remove(_KUYRUK_DOSYA)
            except Exception: pass
            return 0
        yuklendi = 0
        for o in ogeler:
            try:
                kuyruk.put_nowait((
                    o["sablon"], None,   # gorsel_bytes None → worker metin olarak gönderir
                    o.get("linkler", []),
                    o.get("magaza", ""),
                    o.get("kat", "genel"),
                    o.get("kanal", ""),
                    o.get("indirim", 0),
                    o.get("fs", 0.0),
                ))
                yuklendi += 1
            except Exception:
                break   # kuyruk doldu
        if yuklendi:
            log("OK", f"Kuyruk kalıcılığı: {yuklendi} bekleyen öğe geri yüklendi")
        try: _os.remove(_KUYRUK_DOSYA)
        except Exception: pass
        return yuklendi
    except Exception as e:
        log("UYARI", f"Kuyruk yükle: {e}")
        return 0


def _aktif_bekleme() -> int:
    """#12 — Spike modu: yoğun saatlerde bekleme süresini kısalt.
    - Cuma akşamı 18-23 → KUYRUK_BEKLEME / 2
    - Pazartesi sabah 09-12 → KUYRUK_BEKLEME / 2
    - Gece 02-07 → KUYRUK_BEKLEME × 2 (uyandırmamak için)
    - Diğer → KUYRUK_BEKLEME"""
    if not config.SPIKE_MODU_AKTIF:
        return config.KUYRUK_BEKLEME

    from utils.log import simdi_tr
    simdi = simdi_tr()
    gun = simdi.weekday()   # 0=pzt, 4=cuma
    saat = simdi.hour
    temel = config.KUYRUK_BEKLEME

    # Cuma akşam (4 = Cuma, 17-22)
    if gun == 4 and 17 <= saat < 23:
        return max(60, temel // 2)
    # Pazartesi sabah (0 = Pzt, 9-12)
    if gun == 0 and 9 <= saat < 13:
        return max(60, temel // 2)
    # Gece (2-7)
    if 2 <= saat < 7:
        return temel * 2
    return temel


# ── Tepki ───────────────────────────────────────────────────────

async def tepki_ekle(client: TelegramClient, mesaj) -> None:
    """Tepki ekleme devre dışı — sessiz no-op."""
    return


# ── Buton fabrikası ─────────────────────────────────────────────

def _buton_olustur(link: str, bot_client_var: bool, extra_lnk: str | None = None):
    from telethon.tl.types import (
        KeyboardButtonUrl, KeyboardButtonCallback,
        KeyboardButtonRow, ReplyInlineMarkup,
    )
    satirlar = []

    if extra_lnk:
        # Çoklu ürün: her ürüne ayrı buton, yan yana
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text="1️⃣ Ürün 1", url=link),
            KeyboardButtonUrl(text="2️⃣ Ürün 2", url=extra_lnk),
        ]))
    else:
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text="🔗 Fırsata Git", url=link),
        ]))

    if bot_client_var:
        satirlar.append(KeyboardButtonRow(buttons=[
            KeyboardButtonCallback(text="🔥 Kaçmaz Fırsat", data=b"vote_good"),
            KeyboardButtonCallback(text="❌ Sahte İndirim", data=b"vote_fake"),
        ]))

    return ReplyInlineMarkup(rows=satirlar)


# ── Retry ───────────────────────────────────────────────────────

async def _gonder_retry(gonderi_client, hedef, metin, **kw):
    """#4 — Exponential backoff + FloodWait özel yakalama."""
    global _floodwait_carpani, _son_floodwait_zaman
    import time as _time

    son_hata = None
    for attempt in range(_MAX_RETRY):
        try:
            return await gonderi_client.send_message(hedef, metin, **kw)
        except FloodWaitError as e:
            log("UYARI", f"FloodWait {e.seconds}s — Telegram limit")
            metrik.kayit("floodwait", veri={"sn": e.seconds, "attempt": attempt})
            _son_floodwait_zaman = _time.time()
            _floodwait_carpani = min(_floodwait_carpani * 1.5, 4.0)
            log("BILGI", f"Bekleme çarpanı → {_floodwait_carpani:.1f}x")
            await asyncio.sleep(e.seconds + 2)
            son_hata = e
        except RPCError as e:
            son_hata = e
            log("UYARI", f"RPC hata ({attempt+1}/{_MAX_RETRY}): {e}")
            if attempt < _MAX_RETRY - 1:
                await asyncio.sleep(5 * (2 ** attempt))
        except Exception as e:
            son_hata = e
            if attempt < _MAX_RETRY - 1:
                bekle = 5 * (2 ** attempt)
                log("UYARI", f"Gönderim hatası ({attempt+1}/{_MAX_RETRY}): {e} — {bekle}s")
                await asyncio.sleep(bekle)
    raise son_hata


def _bekleme_carpani_aktif() -> float:
    """Son FloodWait'ten sonra zamanla normal çarpana dön."""
    global _floodwait_carpani
    import time as _time
    if _floodwait_carpani > 1.0:
        gecen = _time.time() - _son_floodwait_zaman
        if gecen > 3600:
            _floodwait_carpani = max(1.0, _floodwait_carpani * 0.7)
    return _floodwait_carpani


# ── Worker ──────────────────────────────────────────────────────

async def worker(
    client: TelegramClient,
    bot_client: TelegramClient | None,
    kuyruk: asyncio.Queue,
) -> None:
    log("BILGI", "Kuyruk worker başladı")
    while True:
        alindi = False   # Bu döngüde kuyruk.get() çağrıldı mı?
        try:
            veri = await kuyruk.get()
            alindi = True
            sablon, gorsel_medya, lnk_giris, magaza, kat, kanal_adi, indirim = veri[:7]
            fs_skor = veri[7] if len(veri) > 7 else 0.0

            # Link tek string ya da liste olabilir → normalize
            if isinstance(lnk_giris, (list, tuple)):
                linkler = [l for l in lnk_giris if l]
            elif lnk_giris:
                linkler = [lnk_giris]
            else:
                linkler = []
            lnk       = linkler[0] if linkler else None
            extra_lnk = linkler[1] if len(linkler) > 1 else None

            while state.durduruldu:
                log("BILGI", "Gece modu / duraklama — worker bekliyor…")
                await asyncio.sleep(15)

            sessiz = gece_modu_aktif()
            buton  = _buton_olustur(lnk, bool(bot_client), extra_lnk) if lnk else None

            # Bot yoksa ya da link yoksa, link metne göm
            if lnk and not buton:
                metin = sablon + f"\n\n🔗 <a href='{lnk}'>Fırsata Git</a>"
            else:
                metin = sablon

            msg = None
            gonderi_client = bot_client if (bot_client and lnk) else client

            if gorsel_medya:
                try:
                    # gorsel_medya artık bytes — mesaj alınırken indirildi (file_reference
                    # süresi dolması önleniyor). Eski uyumluluk için MessageMediaPhoto
                    # gelirse fallback olarak indirme deneyelim.
                    if isinstance(gorsel_medya, (bytes, bytearray)):
                        raw = bytes(gorsel_medya)
                    else:
                        raw = await client.download_media(gorsel_medya, bytes)
                    if not raw or len(raw) < 1_000:
                        raise ValueError("Görsel çok küçük")

                    # ── Görsel kalite kontrolü (v18) ──
                    # Boyut/oran/varyans yetersiz görseller metinle gönderilir.
                    # CPU-yoğun Pillow işlemleri thread'de — event loop bloklanmaz.
                    from services.gorsel import gorsel_kaliteli_mi
                    import asyncio as _aio
                    _loop = _aio.get_running_loop()
                    kaliteli, sebep = await _loop.run_in_executor(
                        None, gorsel_kaliteli_mi, raw)
                    if not kaliteli:
                        log("UYARI", f"Görsel kalite yetersiz: {sebep} — metinle gönderiliyor")
                        raise ValueError(f"görsel kalitesiz: {sebep}")

                    islenmis = await _loop.run_in_executor(
                        None, lambda: logo_ekle(raw, link=lnk))
                    buf = BytesIO(islenmis)
                    buf.name = "urun.png"
                    kw = dict(file=buf, parse_mode="html", silent=sessiz)
                    if buton:
                        kw["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw)
                except Exception as e:
                    log("UYARI", f"Görsel gönderilemedi, metinle devam: {e}")
                    kw2 = dict(parse_mode="html")
                    if buton:
                        kw2["buttons"] = buton
                    msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw2)
            else:
                # Ürün görseli yok → düz metin gönder (logo eklenmez)
                kw3 = dict(parse_mode="html")
                if buton:
                    kw3["buttons"] = buton
                msg = await _gonder_retry(gonderi_client, config.HEDEF_KANAL, metin, **kw3)

            if msg:
                await tepki_ekle(client, msg)

                # Son paylaşılan ürünü sakla — admin /yanlis ile düzeltebilsin
                try:
                    import re as _re
                    # Şablondan ürün adını çıkar (<b>...</b> ilk kalın satır)
                    m_ad = _re.search(r"<b>([^<]{4,})</b>", sablon)
                    ad = m_ad.group(1).strip() if m_ad else None
                    # Başlık/fiyat satırlarını atla (ürün adı genelde 2. <b>)
                    bloklar = _re.findall(r"<b>([^<]+)</b>", sablon)
                    for b in bloklar:
                        if not any(x in b for x in ("İNDİRİM", "FIRSAT", "ELİT", "TL")):
                            ad = b.strip()
                            break
                    global _son_paylasilan
                    _son_paylasilan = {"urun": ad, "link": lnk, "kategori": kat,
                                       "mesaj_id": msg.id}
                    # v22: Duplicate engelleme için bu paylaşımı kalıcı işaretle
                    try:
                        from utils import duplicate
                        # v23.6 BUG FIX: 'link' tanımsızdı (NameError) → kayıt hiç
                        # çalışmıyordu, panel "son 24 saat: 0" gösteriyordu.
                        # Doğru değişken: linkler (mevcut liste) + lnk.
                        tum_linkler = list(linkler) if isinstance(linkler, list) else []
                        if lnk and lnk not in tum_linkler:
                            tum_linkler = tum_linkler + [lnk]
                        duplicate.kaydet(tum_linkler, ad, kat, magaza, msg.id)
                    except Exception:
                        pass
                    # v22: Self-healing izleme — model bozulmasını yakala
                    # v22.1: HER PAYLAŞIMDA anlık kontrol — döngü beklemesin
                    try:
                        from utils import self_heal
                        self_heal.kayit_ekle(kat)
                        # Anlık onarım denemesi (bozuk değilse hiçbir şey yapmaz)
                        sonuc = self_heal.otomatik_onar()
                        if sonuc and sonuc.get("onarildi"):
                            tetik = sonuc.get("tetik") or {}
                            log("KRITIK", f"Self-heal anlık tetik: "
                                          f"'{tetik.get('kategori')}' "
                                          f"{tetik.get('tekrar')} kez tekrar etmişti")
                    except Exception:
                        pass
                    # v22.7 — Sistem 6: Kaliteli üründen kelime öğren (sözlük büyüsün)
                    try:
                        from utils import sozluk
                        if ad:
                            sozluk.ogren(ad)
                    except Exception:
                        pass
                    # v22.7 — Sistem 7: Kara kutuya paylaşımı kaydet
                    try:
                        from utils import karakutu
                        karakutu.kaydet("paylasim", f"{ad or '?'} [{kat}] {magaza}")
                    except Exception:
                        pass
                    # v22.10 — Sistem 6: Kullanıcı isteklerini kontrol et, eşleşen
                    # abonelere bot client ile bildirim gönder
                    try:
                        from utils import istek, izleme
                        if ad and izleme._bot_client_ref is not None:
                            eslesme = istek.eslesenleri_bul(ad, sablon)
                            for kullanici_id, arama in eslesme[:20]:
                                try:
                                    await izleme._bot_client_ref.send_message(
                                        kullanici_id,
                                        f"🔔 Aradığın <b>{arama}</b> için fırsat geldi!\n\n"
                                        f"📌 {ad}\n👉 @{config.HEDEF_KANAL.lstrip('@')}",
                                        parse_mode="html")
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    # v22.11 — Sistem 10: Paylaşım saatini kaydet (zamanlama öğrensin)
                    try:
                        from utils import zamanlama
                        zamanlama.paylasim_kaydet()
                    except Exception:
                        pass
                    # v22.10 — Sistem 4+5: Fiyat geçmişi + stok geri-gelme takibi
                    try:
                        from utils import fiyat_takip
                        from services.analiz import urun_kimligi
                        import re as _re_f
                        ilk_lnk = None
                        if isinstance(lnk, str):
                            ilk_lnk = lnk
                        elif isinstance(linkler, list) and linkler:
                            ilk_lnk = linkler[0]
                        if ilk_lnk:
                            kim = urun_kimligi(ilk_lnk)
                            if kim:
                                # Şablondan yeni fiyatı çıkar (💰 <b>X TL</b>)
                                fm = _re_f.search(r"💰[^<]*<b>([\d.,]+)\s*TL", sablon)
                                if fm:
                                    try:
                                        yf = float(fm.group(1).replace(".", "").replace(",", "."))
                                        if yf > 0:
                                            fiyat_takip.fiyat_kaydet(kim, yf)
                                    except ValueError:
                                        pass
                                fiyat_takip.stok_kontrol(kim)
                    except Exception:
                        pass
                    # v22: Akıllı özet için mesaj_id'yi günlüğe iliştir
                    try:
                        from schedulers import gunluk as _gun
                        ilk_link = (link[0] if isinstance(link, list) and link else link) or lnk
                        if ilk_link:
                            _gun.mesaj_id_ilistir(ilk_link, msg.id)
                    except Exception:
                        pass
                except Exception:
                    pass

                # ── v18: Mesaj meta'yı segmentasyon için kaydet ──
                try:
                    from utils import segment
                    segment.mesaj_kaydet(
                        mesaj_id=msg.id,
                        kategori=kat,
                        magaza=magaza,
                        indirim=indirim,
                    )
                except Exception as e:
                    log("UYARI", f"Segment meta kaydı: {e}")

            # Yüksek skor → sabitle (pin)
            if msg and fs_skor >= 7.0:
                try:
                    await client.pin_message(config.HEDEF_KANAL, msg.id, notify=False)
                    log("OK", f"Sabitlendi (skor {fs_skor}/10)")
                except Exception as e:
                    log("UYARI", f"Pin hatası: {e}")

            ist_guncelle(kanal_adi, magaza, kat)
            tip = "çoklu" if extra_lnk else "tekli"
            log("OK", f"Gönderildi [{magaza}] %{indirim} ({tip}) | kuyruk={kuyruk.qsize()}")

            # #6 Health endpoint için heartbeat
            try:
                from services import health
                health.son_mesaj_kaydet()
                from utils import saglik
                saglik.kaydet("paylasildi")
            except Exception:
                pass

            # #14 — Telemetri kaydı
            metrik.kayit("paylasildi",
                magaza=magaza, kategori=kat, kaynak=kanal_adi,
                indirim=indirim, skor=fs_skor,
                veri={"tip": tip})

            # v18 — Trend ve mağaza geçmişi (kendi kendine yetinen ML için)
            try:
                from utils import trend, sahte_indirim
                ana_k = kat.split(":")[0] if ":" in kat else kat
                alt_k = kat.split(":", 1)[1] if ":" in kat else ""
                trend.kaydet(ana_k, alt_k, magaza, indirim)
                sahte_indirim.gecmise_ekle(magaza, indirim)
            except Exception:
                pass

            # #11 Stok takibe kaydet
            if msg and lnk:
                try:
                    from services.stok_takip import kayit_ekle
                    kayit_ekle(msg, lnk)
                except Exception as e:
                    log("UYARI", f"Stok takip kayıt: {e}")

            kuyruk.task_done()
            # #4 — FloodWait sonrası adaptif bekleme
            bekle_sn = int(_aktif_bekleme() * _bekleme_carpani_aktif())
            await asyncio.sleep(bekle_sn)

        except Exception as e:
            log("HATA", f"Worker: {type(e).__name__}: {e}")
            if alindi:
                try:
                    kuyruk.task_done()
                except ValueError:
                    pass
            await asyncio.sleep(10)
