"""
Kaynak kanallardan gelen yeni mesajları dinler, filtreler ve kuyruğa ekler.
- Tek ürünlü mesaj: normal akış (1 mesaj, 1 buton)
- Çok ürünlü mesaj: tek mesajda 2 ürün birleştirilir (1 mesaj, 2 buton)
"""
import asyncio
import re

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto

import config
import state
from services.analiz import (
    markdown_temizle, benzerlik_anahtari,
    indirim_oranini_bul, kalite_skoru, magaza_bul,
    kategori_bul, marka_spam_kontrol, firsat_skoru, link_bul,
    mesaj_bolum_ayir,
)
from services.sablon import olustur as sablon_olustur, olustur_coklu
from schedulers.gunluk import ekle as _gunluk_ekle_ham


def gunluk_ekle(metin, indirim, linkler, gemini_kalite=0):
    """Geriye dönük uyumlu sarmalayıcı: schedulers.gunluk.ekle eski sürümse
    (4. parametreyi kabul etmiyorsa) 3 argümanla çağırır — karışık deploy'da çökmez."""
    try:
        _gunluk_ekle_ham(metin, indirim, linkler, gemini_kalite)
    except TypeError:
        try:
            _gunluk_ekle_ham(metin, indirim, linkler)
        except Exception:
            pass
from utils.cache import gorulmus_var_mi, gorulmus_ekle
from utils.log import log


def _kara_liste_eslesir(metin: str) -> bool:
    """Kara liste kelimesi tam kelime olarak metin içinde geçiyor mu?
    'tablet kalem' → 'kalem' yakalanmalı (boşluk sınırı)
    'kalemini' → 'kalem' yakalanmamalı (kelime uzantısı)
    'kitaplık' → 'kitap' yakalanmamalı (uzantı)"""
    if not metin:
        return False
    ml = metin.lower()
    for kelime in config.KARA_LISTE:
        # Çok kelimeli ise direkt substring (örn "ekran koruyucu")
        if " " in kelime:
            if kelime in ml:
                return True
        else:
            # Tek kelime → kelime sınırı ile ara
            if re.search(r"\b" + re.escape(kelime) + r"\b", ml):
                return True
    return False


def _kupon_adaylar_olustur(kupon_urunler: list[dict], btn_links: list[str],
                           ham: str) -> list[dict]:
    """v23.15 — Kupon ayrıştırıcının çıktısını _blok_analiz formatında
    aday dict'lerine çevir. Her kupon ürünü ayrı bir paylaşım adayı olur.

    Fiyat zaten ayrıştırıcıdan kesin geliyor (kupon kodundan değil), o yüzden
    fiyat çıkarıcıyı atlayıp doğrudan ürün+fiyat+kod kullanıyoruz.
    """
    from services.analiz import kategori_bul
    from services.urun_kapisi import gecerli_urun_adi, guzellestir
    adaylar = []
    for i, u in enumerate(kupon_urunler):
        ad = gecerli_urun_adi(u.get("urun"), ham)
        if not ad:
            continue
        ad = guzellestir(ad)
        fiyat = u.get("fiyat")
        eski = u.get("eski_fiyat")
        # İndirim yüzdesi (eski varsa)
        indirim = 0
        if eski and fiyat and eski > fiyat:
            indirim = int((eski - fiyat) / eski * 100)
        kat, _, _ = kategori_bul(ad)
        # Fiyatları TR formatında string'e çevir (23899.0 → "23.899")
        def _fmt(v):
            if not v:
                return None
            return f"{v:,.0f}".replace(",", ".")
        fiyat_str = _fmt(fiyat)
        eski_str = _fmt(eski)
        # Sahte gemini sonucu (ürün adı + kategori + kupon)
        sahte_gemini = {
            "urun_adi": ad, "kategori": kat, "reklam": False,
            "tanitim": "", "fiyat_uyari": "", "kalite": 3,
            "fiyat": fiyat, "eski_fiyat": eski or 0,
            "kupon_kodu": u.get("kod"),
        }
        blok_metin = f"{ad}\n{fiyat_str} TL"
        if eski_str:
            blok_metin += f" {eski_str} TL"
        if u.get("kod"):
            blok_metin += f"\n🎟️ Kupon: {u['kod']}"
        adaylar.append({
            "blok": blok_metin,
            "indirim": indirim,
            # v23.34 — Her ürüne KENDİ linkini ver (sıralı: 🔥→link0, 🔻→link1).
            # Eskiden TÜM ürünler btn_links[0] alıyordu → aynı link → aşağıdaki
            # duplicate filtresi 2. ve sonraki ürünleri "aynı link" diye
            # düşürüyordu, çoklu kupon ürünü kayboluyordu. Ürün sayısı link
            # sayısını aşarsa fazlalar son linke düşer (dedup eler, güvenli).
            "link": (btn_links[min(i, len(btn_links) - 1)] if btn_links else ""),
            "magaza": "E-Ticaret",
            "kat": kat,
            "skor": 50,
            "fs": 5,
            "gemini": sahte_gemini,
            "urun": ad,
            "kupon_kodu": u.get("kod"),
            "_kupon_fiyat": fiyat,
            "_kupon_eski": eski,
        })
    return adaylar


def _blok_analiz(blok: str, btn_links: list[str], gemini_sonuc: dict | None = None,
                 orijinal_mesaj: str = "") -> dict | None:
    """Bir bloğu analiz edip dict döner; geçersizse None.

    gemini_sonuc verilmişse (Gemini ile gerçek anlama), ürün/reklam/kategori
    kararlarında ÖNCELİKLE o kullanılır. Yoksa saf-Python yedek sistem.

    orijinal_mesaj: Blok bölme bozulmuşsa (ürün adı ayrı bloğa düşmüşse),
    ürün adını buradan kurtarmak için kullanılır (v23.3 güvenlik ağı).
    """
    onizleme = blok[:50].replace("\n", " ")

    if _kara_liste_eslesir(blok):
        log("FILTRE", f"Kara liste → atlandı: '{onizleme}…'")
        return None

    # ── Dil filtresi: yabancı dilli mesajları filtrele ──
    try:
        from utils import dil
        tr_skor = dil.turkce_skoru(blok)
        if tr_skor < 0.30:   # net yabancı
            log("FILTRE", f"Yabancı dil (TR skor={tr_skor:.2f}) → atlandı: '{onizleme}…'")
            return None
    except Exception as _e:
        try:
            from utils import karakutu
            karakutu.sessiz_hata("mesaj.dil_tanima", _e)
        except Exception:
            pass   # dil tanıma başarısız → devam et

    indirim = indirim_oranini_bul(blok)
    lnk = link_bul(blok, btn_links)

    if not lnk:
        log("FILTRE", f"Link yok → atlandı: '{onizleme}…'")
        try:
            from utils import saglik; saglik.kaydet("link_yok")
        except Exception: pass
        if btn_links:
            log("FILTRE", f"  Mevcut buton linkleri ({len(btn_links)}): {btn_links}")
        return None

    # ── v23.32 — KİTAP FİLTRESİ ──────────────────────────────────
    # Amazon'da kitaplar ASIN olarak ISBN kullanır (rakamla başlayan 10 hane
    # veya 9 hane + X); diğer ürünlerin ASIN'i "B" ile başlar. Kitaplar
    # çoğunlukla indirimde olsa da kanalı tek tipleştirdiği için paylaşılmaz.
    if getattr(config, "KITAP_FILTRELE", True) and _kitap_linki_mi(lnk, btn_links):
        log("FILTRE", f"Kitap → atlandı: '{onizleme}…'")
        return None

    from services.analiz import fiyat_bul, urun_adi_bul, _urun_adi_makul
    _eski_fiyat, _yeni_fiyat, _, _ = fiyat_bul(blok)

    # ── ÜRÜN ADI: Gemini varsa onun anlayışı, yoksa saf-Python ──
    # v23.0 — TEK MERKEZİ KAPI: Gemini'nin ürün adı da kapıdan geçer.
    # Hangi kaynaktan gelirse gelsin "Amazon" gibi çöp burada elenir.
    from services.urun_kapisi import gecerli_urun_adi, en_iyi_urun_adi
    if gemini_sonuc and gemini_sonuc.get("urun_adi"):
        # v23.8 — Gemini bazen uzun ürün adının ORTASINDAN kopuk parça veriyor
        # ("Apple iPad ... Gümüş Rengi" → "Gün Süren Pil Ömrü Gümüş Rengi").
        # Gemini ile saf-Python'u karşılaştır: mesaj başıyla örtüşen doğrudur.
        g_aday = gecerli_urun_adi(gemini_sonuc["urun_adi"], blok)
        p_aday = gecerli_urun_adi(urun_adi_bul(blok), blok)
        secilen = en_iyi_urun_adi(g_aday, p_aday, blok)
        urun = secilen or p_aday or urun_adi_bul(blok)
    else:
        urun = urun_adi_bul(blok)

    # ── REKLAM KARARI: Gemini varsa onun anlayışı (gerçek anlama), yoksa yedek ──
    # v23.25 — ÖNCE Gemini'den BAĞIMSIZ kesin reklam kontrolü. Açık işaretler
    # (#sponsorlu, "Hemen Başvur", "yatırım fırsatı") varsa Gemini "ürün" dese
    # bile engelle. Tek katmana güvenmek riskli: canlıda sponsorlu emlak
    # reklamı sahte ürün adıyla (slogan) Gemini'yi geçip paylaşılmıştı.
    try:
        from utils import reklam as _reklam_on
        _kesin, _kesin_sebep = _reklam_on.reklam_mi(
            blok, link=lnk, urun_adi="", fiyat_var=bool(_yeni_fiyat))
        # Sadece "kesin reklam işareti" ile düşür (yapısal karar değil — o
        # aşağıda Gemini yoksa devreye girer). Böylece Gemini'nin ürün kararı
        # korunur AMA açık reklam etiketleri her durumda engellenir.
        if _kesin and _kesin_sebep.startswith("kesin reklam işareti"):
            log("FILTRE", f"Reklam (kesin işaret) → atlandı: '{onizleme}…' ({_kesin_sebep})")
            try:
                from utils import urun_taniyici
                urun_taniyici.ogren_negatif(blok[:200])
            except Exception:
                pass
            return None
    except Exception:
        pass

    if gemini_sonuc is not None:
        if gemini_sonuc.get("reklam"):
            log("FILTRE", f"Reklam (Gemini) → atlandı: '{onizleme}…'")
            try:
                from utils import saglik; saglik.kaydet("reklam")
            except Exception: pass
            # Gemini'nin kararını yedek sisteme öğret (kota dolunca işe yarar)
            try:
                from utils import urun_taniyici
                urun_taniyici.ogren_negatif(blok[:200])
            except Exception:
                pass
            return None
        # Gemini "ürün" dedi → reklam filtresini atla, devam et
        # Gemini'nin onayladığı ürün adını yedek sisteme pozitif öğret
        if gemini_sonuc.get("urun_adi"):
            try:
                from utils import urun_taniyici
                urun_taniyici.ogren_pozitif(gemini_sonuc["urun_adi"])
            except Exception:
                pass
    else:
        # Yedek: saf-Python reklam tespiti
        try:
            from utils import reklam
            rek, rek_sebep = reklam.reklam_mi(
                blok, link=lnk, urun_adi=urun or "",
                fiyat_var=bool(_yeni_fiyat),
            )
            if rek:
                log("FILTRE", f"Reklam/duyuru → atlandı: '{onizleme}…' ({rek_sebep})")
                try:
                    from utils import urun_taniyici
                    urun_taniyici.ogren_negatif(blok[:200])
                except Exception:
                    pass
                return None
        except Exception:
            pass

    # ── Geçerlilik: somut ürün sinyali olmalı ──
    # Fiyat VEYA indirim VEYA (ürün adı + mağaza linki) → geçer
    if not _yeni_fiyat and indirim < config.MIN_INDIRIM and not urun:
        log("FILTRE", f"Ürün sinyali yetersiz → atlandı: '{onizleme}…'")
        return None

    if not urun:
        # v23.3 — GÜVENLİK AĞI: Blok bölme bozulmuş olabilir (ürün adı ayrı
        # bloğa düşmüş). Bu blokta fiyat/indirim VAR ama ürün adı YOKsa,
        # orijinal mesajdan ürün adını kurtarmayı dene. Böylece "ürün adı
        # üstte, fiyat altta" formatında bölme hatası olsa bile ürün kaybolmaz.
        if orijinal_mesaj and (_yeni_fiyat or indirim >= config.MIN_INDIRIM):
            try:
                kurtarilan = urun_adi_bul(orijinal_mesaj)
                if kurtarilan:
                    urun = kurtarilan
                    log("KURTARMA", f"Ürün adı orijinalden kurtarıldı: '{urun[:40]}'")
            except Exception as _e:
                try:
                    from utils import karakutu
                    karakutu.sessiz_hata("mesaj.urun_kurtarma", _e)
                except Exception:
                    pass
        if not urun:
            log("FILTRE", f"Ürün adı çıkarılamadı → atlandı: '{onizleme}…'")
            try:
                from utils import saglik; saglik.kaydet("urun_adi_yok")
            except Exception: pass
            return None

    skor = kalite_skoru(blok, indirim, btn_links)
    if skor < config.MIN_KALITE:
        log("FILTRE", f"Kalite {skor} < {config.MIN_KALITE} → atlandı: '{onizleme}…'")
        return None

    # ── Sahte indirim tespiti (heuristik) ──
    try:
        from utils import sahte_indirim
        magaza_n = magaza_bul(blok, lnk)
        sahte, sebep = sahte_indirim.sahte_mi(_eski_fiyat, _yeni_fiyat, indirim, magaza_n)
        if sahte:
            log("FILTRE", f"Sahte indirim → atlandı: '{onizleme}…' ({sebep})")
            return None
    except Exception:
        pass

    # ── Anomali tespiti (z-score tabanlı) ──
    try:
        from utils import anomali
        link_sayi = len(btn_links) + (1 if lnk else 0)
        anormalmi, sebep_an = anomali.kontrol_et(
            blok,
            fiyat=_yeni_fiyat if _yeni_fiyat else None,
            indirim=indirim,
            link_sayi=link_sayi,
        )
        if anormalmi:
            log("FILTRE", f"Anomali → atlandı: '{onizleme}…' ({sebep_an})")
            return None
    except Exception:
        pass

    magaza = magaza_bul(blok, lnk)
    # Kategori: Gemini varsa onun anlayışı, yoksa saf-Python
    if gemini_sonuc and gemini_sonuc.get("kategori") and gemini_sonuc["kategori"] != "genel":
        kat = gemini_sonuc["kategori"]
        # Alt kategori varsa "ana:alt" formatında birleştir
        alt = gemini_sonuc.get("alt_kategori", "")
        if alt:
            kat = f"{kat}:{alt}"
    else:
        kat, _, _ = kategori_bul(blok)
    fs = firsat_skoru(blok, indirim, btn_links)
    # Gemini kalite değerlendirmesi (1-5) → fırsat skorunu zenginleştir
    if gemini_sonuc and gemini_sonuc.get("kalite", 0) >= 4:
        fs += 1.5   # Gemini "mükemmel fırsat" dediyse öne çıkar
    elif gemini_sonuc and gemini_sonuc.get("kalite", 0) == 3:
        fs += 0.5

    # ════════════════════════════════════════════════════════════
    # KENDI KENDİNE ÖĞRENME (v18) — Claude bağımsız
    # ════════════════════════════════════════════════════════════
    #
    # Self-Supervised Learning:
    #   • Yüksek güvenli tahminler → eğitim verisine eklenir (pseudo-label)
    #   • Belirsiz tahminler → mesaj 'genel' kategori ile gönderilir
    #   • Marka otomatik öğrenme → bilinmeyen sık token "marka adayı"
    try:
        if urun and skor >= 50 and indirim >= 25 and len(urun) >= 10:
            from utils import ml_kategori
            from services.analiz import kategori_bul_tam
            ana_k, alt_k, guven = kategori_bul_tam(blok)

            # ÖNCE HAFIZAYA SOR: bu ürün/marka daha önce öğrenildi mi?
            # Öğrenildiyse, modelin tahminini override et (kalıcı öğrenme).
            try:
                from utils import urun_hafiza
                hatirlanan = urun_hafiza.hatirla(urun, lnk)
                if hatirlanan:
                    if ":" in hatirlanan:
                        ana_k, alt_k = hatirlanan.split(":", 1)
                    else:
                        ana_k, alt_k = hatirlanan, None
                    guven = max(guven, 0.85)   # hafıza güçlü sinyal
                    kat = ana_k                 # şablon kategorisini güncelle
            except Exception:
                pass

            # ÖNEMLİ: Model KENDİ tahminini kendine öğretmemeli (echo chamber /
            # kısır döngü — yanlışı pekiştirir). Bunun yerine, marka→kategori
            # TUTARLILIĞINDAN öğreniyoruz: aynı marka defalarca aynı kategoride
            # görülürse bu güçlü bir DIŞ sinyaldir (modelin kendi onayı değil).
            tam_kat = f"{ana_k}:{alt_k}" if alt_k else ana_k

            # A) Marka→kategori gözlemi kaydet (tutarlılık öğrenmesi).
            #    marka_ogrenme yeterli tutarlı gözlem birikince kalıcı öğrenir.
            if ana_k != "genel" and guven >= 0.6:
                try:
                    from utils import marka_ogrenme
                    # Sadece GÖZLEM kaydet — marka_ogrenme tutarlılık eşiğini
                    # kendisi uygular (örn. 3+ kez aynı kategori → öğren).
                    marka_ogrenme.kaydet(urun, ana_k)
                except Exception:
                    pass

            # B) Belirsiz tahminleri etiketleme kuyruğuna al (admin sonra düzeltir)
            if guven < 0.55:
                ml_kategori.belirsiz_kaydet(urun, ana_k, guven)
                kat = "genel"   # belirsizse 'genel' ile gönder (yanlış kategoriden iyi)

            # C) ÜRÜN HAFIZASI: bu ürünü/markayı kalıcı hatırla.
            #    Aynı ürün tekrar geldiğinde sıfırdan tahmin etmek yerine
            #    öğrenilen kategoriyi kullan (günde 1000 mesajın çoğu tekrar).
            try:
                from utils import urun_hafiza
                urun_hafiza.kaydet(urun, lnk, tam_kat if ana_k != "genel" else None)
            except Exception:
                pass

    except Exception as e:
        from utils.log import log as _l
        _l("UYARI", f"Kendi kendine öğrenme hatası: {e}")

    # ════════════════════════════════════════════════════════════
    # FİYAT ZEKASI (v19) — kategori bazlı fiyat dağılımı öğren
    # ════════════════════════════════════════════════════════════
    try:
        if _yeni_fiyat and kat != "genel":
            from utils import fiyat_zekasi
            from services.analiz import kategori_bul_tam
            ana_fk, alt_fk, _ = kategori_bul_tam(blok)
            fk = f"{ana_fk}:{alt_fk}" if alt_fk else ana_fk
            fiyat_zekasi.kaydet(fk, _yeni_fiyat)
            # Fırsat değeri varsa skoru zenginleştir
            deger = fiyat_zekasi.firsat_degeri(fk, _yeni_fiyat)
            if deger:
                fs = fs + deger["bonus"] / 10.0   # bonus 0-15 → fs +0-1.5
    except Exception:
        pass

    return {
        "blok": blok, "indirim": indirim, "link": lnk,
        "magaza": magaza, "kat": kat, "skor": skor, "fs": fs,
        "gemini": gemini_sonuc, "urun": urun,
    }


def _coklu_link_satir_ayir(blok: str, linkler: list, orijinal_mesaj: str) -> list | None:
    """v23.31 — Tek blokta N farklı ürün linki varken bloğu ürün SEGMENTLERİNE ayır.

    Fiyat içeren satırı SINIR kabul eder: bir ürün = ad satır(lar)ı + onu kapatan
    fiyat satırı. Böylece "Ürün Adı\\n💰199 TL" gibi ÇOK SATIRLI biçimleri de
    yakalar (eski sürüm adı+fiyatı AYNI satırda arıyordu, n11/Amazon toplu fırsat
    mesajlarında ad ve fiyat ayrı satırlarda olduğu için başarısız oluyordu).

    SADECE fiyat-çapalı segment sayısı link sayısına TAM eşitse ve her segment
    geçerli ürün üretirse sonuç döndürür (her ürün → kendi linki, sırayla).
    Aksi halde None → çağıran güvenli davranışı (yalnız ilk ürün) korur.
    Yanlış isimli/linkli gönderi üretmemek için bu sıkı koşul korunur.
    """
    if not blok or not linkler or len(linkler) < 2:
        return None
    from services.analiz import fiyat_bul
    from services.urun_kapisi import gecerli_urun_adi

    # v23.31 — Baştaki BAŞLIK/slogan satırlarını at ("🔥 Günün Fırsatları 🔥").
    # Bunlar ilk ürün segmentine karışıp ürün adı olarak seçilebiliyordu.
    # Fiyatı olmayan + geçerli ürün adı olmayan + link içermeyen ÖNCÜ satırları
    # ilk gerçek içeriğe kadar temizle.
    _satirlar = blok.split("\n")
    while _satirlar:
        ilk = _satirlar[0].strip()
        if not ilk:
            _satirlar.pop(0); continue
        _, _ys, _, _ = fiyat_bul(ilk)
        if _ys is None and gecerli_urun_adi(ilk, ilk) is None and "http" not in ilk.lower():
            _satirlar.pop(0)  # başlık/slogan/emoji satırı → at
        else:
            break
    blok = "\n".join(_satirlar)

    # Satırları, fiyat içeren satırı SINIR kabul ederek ürün segmentlerine grupla
    segmentler: list[str] = []
    mevcut: list[str] = []
    for ham_satir in blok.split("\n"):
        s = ham_satir.strip()
        if not s:
            continue
        mevcut.append(s)
        _, ys, _, _ = fiyat_bul(s)
        if ys:  # fiyat satırı → mevcut segmenti kapat (ad satırları + fiyat)
            segmentler.append("\n".join(mevcut))
            mevcut = []
    # Sondaki fiyatsız artık satırlar bir ürün oluşturmaz → yok say

    # Güvenlik: segment sayısı link sayısıyla TAM eşleşmeli (sıralı eşleme güvenli)
    if len(segmentler) != len(linkler):
        log("BILGI", f"Çoklu link: segment-link eşleşmedi "
                      f"({len(segmentler)} segment / {len(linkler)} link) → güvenli mod")
        return None

    # Her segmenti KENDİ linkiyle analiz et (tüm kalite/reklam/kategori mantığı)
    adaylar = []
    for seg, lnk in zip(segmentler, linkler):
        try:
            a = _blok_analiz(seg, [lnk], gemini_sonuc=None, orijinal_mesaj=orijinal_mesaj)
        except Exception:
            a = None
        if a and a.get("urun"):
            a["link"] = lnk
            adaylar.append(a)

    # Hepsi geçerli ürün üretmeli; biri bile düşerse güvenli davran
    if len(adaylar) != len(linkler):
        log("BILGI", f"Çoklu link: {len(adaylar)}/{len(linkler)} segment geçerli "
                      "ürün verdi → güvenli mod")
        return None
    return adaylar


def _urun_olmayan_link_mi(url: str) -> bool:
    """v23.35 — WhatsApp/Telegram/sosyal medya paylaş-katıl butonları ürün
    linki DEĞİLDİR. Bu linkler ürün sayısını şişirip çoklu-ürün ayrımını
    bozuyordu (örn tek ürünlü mesaj + WhatsApp paylaş butonu → '1 segment /
    4 link' uyuşmazlığı). Ürün linkleri (amazon, trendyol, n11, hb vb) korunur.
    """
    if not url:
        return True
    u = url.lower()
    _urun_disi = (
        "whatsapp.com", "wa.me", "chat.whatsapp", "api.whatsapp",
        "t.me/", "telegram.me", "telegram.dog", "telegram.org",
        "instagram.com", "facebook.com", "fb.com", "fb.me",
        "twitter.com", "x.com/", "youtube.com", "youtu.be", "tiktok.com",
    )
    return any(d in u for d in _urun_disi)


def _kitap_linki_mi(link: str, btn_links: list | None = None) -> bool:
    """v23.32 — Amazon kitap linki mi? Kitaplar ASIN olarak ISBN-10 kullanır:
    10 rakam VEYA 9 rakam + X (örn 9750854586, 080485277X). Diğer ürünlerin
    ASIN'i 'B' ile başlar (örn B0F3JPLZ53). Yalnızca Amazon için geçerli;
    güvenilir ve yanlış pozitif vermez.
    """
    import re as _re
    adaylar = list(btn_links or [])
    if link:
        adaylar.append(link)
    for u in adaylar:
        if not u or "amazon." not in u.lower():
            continue
        m = _re.search(r"/(?:dp|gp/product|d)/(\d{9}[\dXx])(?:[/?]|$)", u)
        if m:
            return True
    return False


def kaydet(client: TelegramClient, kuyruk: asyncio.Queue) -> None:
    @client.on(events.NewMessage(chats=config.KAYNAK_KANALLAR))
    async def _dinle(event):
        try:
            if state.durduruldu:
                return

            # #13 — Eski mesaj filtresi: mesaj çok eskiyse atla
            # (forward edilmiş eski içerikler kanala düşebiliyor)
            try:
                from datetime import datetime, timezone, timedelta
                if event.message.date:
                    yas_sn = (datetime.now(timezone.utc) - event.message.date).total_seconds()
                    if yas_sn > config.ESKI_MESAJ_LIMIT_DK * 60:
                        log("FILTRE", f"Eski mesaj atlandı ({int(yas_sn / 60)}dk önce)")
                        return
            except Exception:
                pass

            ham = markdown_temizle(event.message.text or "")

            # ── v23.25 — ENGELLENMİŞ GÖNDERİCİ KONTROLÜ ──────────────
            # @magfi gibi belirli botların mesajları tamamen yok sayılır.
            # Üç yoldan kontrol: gönderen kullanıcı adı, forward kaynağı,
            # ve metin/link içeriği (örn 'magfi.link').
            try:
                _engelliler = getattr(config, "ENGELLI_GONDERENLER", [])
                if _engelliler:
                    _adaylar = []
                    # Gönderen kullanıcı adı
                    try:
                        _snd = await event.get_sender()
                        if _snd is not None and getattr(_snd, "username", None):
                            _adaylar.append(_snd.username.lower())
                    except Exception:
                        pass
                    # Forward kaynağı (forward edilmiş mesaj)
                    try:
                        _fwd = getattr(event.message, "forward", None)
                        if _fwd is not None:
                            _fc = getattr(_fwd, "chat", None) or getattr(_fwd, "sender", None)
                            if _fc is not None and getattr(_fc, "username", None):
                                _adaylar.append(_fc.username.lower())
                    except Exception:
                        pass
                    # Kullanıcı adı eşleşmesi
                    if any(e in _adaylar for e in _engelliler):
                        log("FILTRE", f"Engelli gönderici → atlandı ({_adaylar})")
                        return
                    # Metin/link içeriği eşleşmesi (örn 'magfi' linki)
                    _dusuk = ham.lower()
                    if any(e in _dusuk for e in _engelliler):
                        log("FILTRE", "Engelli gönderici içeriği → atlandı")
                        return
            except Exception:
                pass

            # Buton linklerini topla — birkaç farklı yoldan dene
            btn_links: list[str] = []
            try:
                # 1) En yaygın: event.message.buttons (Telethon high-level)
                if event.message.buttons:
                    for row in event.message.buttons:
                        for btn in row:
                            url = getattr(btn, "url", None)
                            if url:
                                btn_links.append(url)
            except Exception as e:
                log("UYARI", f"event.message.buttons hatası: {e}")

            # 2) Fallback: doğrudan reply_markup içine bak
            try:
                if not btn_links and event.message.reply_markup:
                    rm = event.message.reply_markup
                    rows = getattr(rm, "rows", None) or []
                    for row in rows:
                        for btn in getattr(row, "buttons", []) or []:
                            url = getattr(btn, "url", None)
                            if url:
                                btn_links.append(url)
            except Exception as e:
                log("UYARI", f"reply_markup parse hatası: {e}")

            # 3) Fallback: mesajdaki entities (gizli link/text_link)
            try:
                from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
                for ent in event.message.entities or []:
                    if isinstance(ent, MessageEntityTextUrl) and ent.url:
                        btn_links.append(ent.url)
                    elif isinstance(ent, MessageEntityUrl):
                        # Mesaj metninden URL'i kes
                        text = event.message.text or ""
                        url = text[ent.offset:ent.offset + ent.length]
                        if url.startswith("http"):
                            btn_links.append(url)
            except Exception as e:
                log("UYARI", f"entities parse hatası: {e}")

            # Tekrarları temizle (exact string), sırasını koru
            seen = set()
            btn_links = [x for x in btn_links if not (x in seen or seen.add(x))]

            # v23.35 — Ürün OLMAYAN linkleri (WhatsApp/Telegram/sosyal paylaş-katıl
            # butonları) ele. Bunlar ürün sayısını şişirip çoklu-ürün ayrımını
            # bozuyordu (canlıda 33 WhatsApp linki "X segment / Y link" uyuşmazlığı
            # yaratmıştı). Ürün linkleri (amazon/trendyol/n11/hb...) korunur.
            btn_links = [x for x in btn_links if not _urun_olmayan_link_mi(x)]

            # ÜRÜN bazında grupla — aynı ürünün affiliate/ref farklı linkleri
            # tek ürün sayılır; gerçekten farklı ürünler ayrı tutulur.
            from services.analiz import urun_kimligine_gore_grupla
            urun_linkleri = urun_kimligine_gore_grupla(btn_links)

            if btn_links:
                log("BILGI", f"Mesajdan {len(btn_links)} link toplandı, "
                             f"{len(urun_linkleri)} benzersiz ürün: {btn_links[0][:60]}…")

            gorsel = (
                event.message.media
                if event.message.media and isinstance(event.message.media, MessageMediaPhoto)
                else None
            )
            # Görseli HEMEN indir — kuyrukta 180sn bekleyince file_reference süresi dolar.
            # `bytes` olarak gönderdiğimizde, expired reference sorunu olmaz.
            gorsel_bytes: bytes | None = None
            if gorsel is not None:
                try:
                    gorsel_bytes = await client.download_media(event.message, bytes)
                    if gorsel_bytes and len(gorsel_bytes) < 1_000:
                        gorsel_bytes = None   # çok küçük, kullanma
                except Exception as e:
                    log("UYARI", f"Görsel indirilemedi (kaynakta): {e}")
                    gorsel_bytes = None
            kanal_adi = getattr(getattr(event, "chat", None), "username", None) or "bilinmiyor"

            # v23.15 — KUPON MESAJI ÖZEL İŞLEME: "Kodu İle X TL" formatındaki
            # çok-ürünlü kupon mesajlarını ayrı çöz (fiyat çıkarıcı bunlarda
            # şaşırıyordu: "500"u HAZIRAN500 kodundan fiyat sanıyordu).
            adaylar = []
            try:
                from services import kupon_ayristirici
                if kupon_ayristirici.kupon_mesaji_mi(ham):
                    kupon_urunler = kupon_ayristirici.ayristir(ham)
                    if kupon_urunler:
                        adaylar = _kupon_adaylar_olustur(kupon_urunler, btn_links, ham)
                        log("KUPON", f"{len(adaylar)} kupon ürünü ayrıştırıldı")
            except Exception as _e:
                try:
                    from utils import karakutu
                    karakutu.sessiz_hata("mesaj.kupon_ayristir", _e)
                except Exception:
                    pass

            # Kupon ayrıştırma sonuç vermediyse → normal blok işleme
            if adaylar:
                bloklar = []  # kupon yolu kullanıldı, normal işlemeyi atla
            else:
                bloklar = mesaj_bolum_ayir(ham)
            # Akıllı eşleştirme: blok sayısı ile ürün linki sayısı eşitse birebir,
            # DEĞİLSE ama yeterli ürün linki varsa yine sıralı eşle (fazla/alakasız
            # buton link sayısını bozsa bile her bloğa kendi linkini ver).
            blok_link_eslesir = len(bloklar) >= 2 and len(urun_linkleri) >= len(bloklar)

            # Gemini ile gerçek anlama (varsa) — thread'de çağır, event loop bloklanmasın
            async def _gemini_analiz(metin):
                try:
                    from utils import gemini
                    if not gemini.kullanilabilir():
                        return None
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, gemini.analiz_et, metin)
                except Exception:
                    return None

            for idx, b in enumerate(bloklar):
                g_sonuc = await _gemini_analiz(b)
                linkler = [urun_linkleri[idx]] if blok_link_eslesir else btn_links
                sonuc = _blok_analiz(b, linkler, gemini_sonuc=g_sonuc,
                                     orijinal_mesaj=ham)
                if sonuc:
                    adaylar.append(sonuc)

            # v22.6 — BUG FIX: Tek metin bloğu + birden fazla link, AYNI ürünün
            # farklı linkleridir (ana link + ilgili/kısa link). Eskiden blok
            # kopyalanıp 2 "ürün" yapılıyordu → ikisi de AYNI isimle çıkıyordu.
            if len(adaylar) == 1 and len(urun_linkleri) >= 2:
                from services.analiz import urun_kimligi
                kimlikler = {}
                for ul in urun_linkleri[:5]:
                    k = urun_kimligi(ul)
                    if k and k not in kimlikler:
                        kimlikler[k] = ul
                if len(kimlikler) >= 2:
                    # v23.27 — Tek blok + N farklı ürün linki. ÖNCE bloğu
                    # satır-bazlı ayırmayı dene: her satır geçerli ürün adı +
                    # fiyat içeriyorsa VE adet link sayısıyla EŞLEŞİYORSA, her
                    # ürünü kendi linkiyle ayrı paylaş. Eşleşme net değilse
                    # güvenli davran (yanlış isimli gönderi üretme) → sadece ilk.
                    coklu = _coklu_link_satir_ayir(
                        adaylar[0]["blok"], list(kimlikler.values()), ham)
                    if coklu and len(coklu) >= 2:
                        adaylar = coklu
                        log("BILGI", f"Tek blok + {len(kimlikler)} ürün linki → "
                                      f"{len(coklu)} ürün satır-bazlı ayrıldı, hepsi paylaşılıyor")
                    else:
                        # Güvenli: sadece ilk ürünü paylaş (yanlış isim üretme)
                        adaylar[0]["link"] = list(kimlikler.values())[0]
                        log("BILGI", f"Tek blok + {len(kimlikler)} farklı ürün linki → "
                                      "isim ayrımı yapılamadığı için sadece ilki paylaşılıyor")
                else:
                    adaylar[0]["link"] = urun_linkleri[0]

            if not adaylar:
                return

            # Tüm mesaj için tek duplikat anahtar — aynı mesaj 2 kez gelmesin
            mid = benzerlik_anahtari(adaylar[0]["blok"])
            if gorulmus_var_mi(mid):
                return
            gorulmus_ekle(mid)

            # ── Çoklu ürün (2-5) ──
            adaylar.sort(key=lambda x: x["fs"], reverse=True)

            # Aynı linke sahip adayları tekille (gerçekten aynı ürün)
            benzersiz = []
            gorulen_link = set()
            for a in adaylar:
                if a["link"] in gorulen_link:
                    continue
                gorulen_link.add(a["link"])
                benzersiz.append(a)
            adaylar = benzersiz

            # Tek ürüne düştüyse tekli gönderim
            if len(adaylar) == 1:
                a = adaylar[0]
                if marka_spam_kontrol(a["magaza"]):
                    log("BILGI", f"{a['magaza']} spam limiti – atlandı")
                    return
                sablon = sablon_olustur(a["blok"], a["indirim"], [a["link"]],
                                        gemini=a.get("gemini"),
                                        kurtarilan_urun=a.get("urun"))
                if not sablon:
                    return
                # v22: Duplicate kontrol — son N gün içinde aynı ürün paylaşıldıysa atla
                try:
                    from utils import duplicate
                    onceki = duplicate.daha_once_paylasildi_mi([a["link"]])
                    if onceki:
                        log("BILGI", f"Duplicate atlandı: '{(onceki.get('urun') or '')[:40]}' "
                                      f"{onceki['kac_saat']}h önce paylaşıldı")
                        return
                except Exception:
                    pass
                gunluk_ekle(a["blok"], a["indirim"], [a["link"]], (a.get("gemini") or {}).get("kalite", 0))
                try:
                    kuyruk.put_nowait((
                        sablon, gorsel_bytes, [a["link"]],
                        a["magaza"], a["kat"], kanal_adi,
                        a["indirim"], a["fs"],
                    ))
                    log("BILGI", f"Kuyruğa eklendi (tek) [{a['magaza']}] %{a['indirim']}")
                except asyncio.QueueFull:
                    log("UYARI", "Kuyruk dolu")
                return

            # En kaliteli 2 ürün → tek mesaj, 2 buton
            a1, a2 = adaylar[0], adaylar[1]
            if marka_spam_kontrol(a1["magaza"]):
                return

            sablon = olustur_coklu(
                a1["blok"], a1["indirim"], a1["link"],
                a2["blok"], a2["indirim"], a2["link"],
                btn_links=[a1["link"], a2["link"]],
            )
            if not sablon:
                return

            gunluk_ekle(a1["blok"], a1["indirim"], [a1["link"]], (a1.get("gemini") or {}).get("kalite", 0))
            gunluk_ekle(a2["blok"], a2["indirim"], [a2["link"]], (a2.get("gemini") or {}).get("kalite", 0))

            # v22: Çoklu üründe de duplicate kontrolü — her iki link de yeni olmalı
            try:
                from utils import duplicate
                onceki = duplicate.daha_once_paylasildi_mi([a1["link"], a2["link"]])
                if onceki:
                    log("BILGI", f"Çoklu duplicate atlandı: bir ürün "
                                  f"{onceki['kac_saat']}h önce paylaşıldı")
                    return
            except Exception:
                pass

            try:
                kuyruk.put_nowait((
                    sablon, gorsel_bytes,
                    [a1["link"], a2["link"]],   # 2 link → 2 buton
                    a1["magaza"], a1["kat"], kanal_adi,
                    max(a1["indirim"], a2["indirim"]),
                    max(a1["fs"], a2["fs"]),
                ))
                log("BILGI", f"Çoklu kuyruğa eklendi [{a1['magaza']}+{a2['magaza']}] %{a1['indirim']}+%{a2['indirim']}")
            except asyncio.QueueFull:
                log("UYARI", "Kuyruk dolu, çoklu mesaj atıldı")

        except Exception as e:
            log("HATA", f"{type(e).__name__}: {e}")
