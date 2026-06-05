"""
Telegram HTML şablonu — modern, minimal, etki odaklı tasarım.

Değişiklikler v11:
  • Çift skor (yıldız spam) kaldırıldı, tek temiz başlık
  • Tasarruf tutarı vurgulanıyor (>=50 TL ise)
  • Fiyatlar küsuratsız (1.499,00 → 1.499)
  • VIP rozeti (skor 8+ veya indirim 70+)
  • Marka kampanyasında marka adı/kampanya başlığı görünür
  • Çoklu şablonda mağaza link'ten doğru tespit ediliyor
  • Negatif ifade tespit edilirse şablon None döner
  • Hashtag sayısı azaltıldı (max 3)
  • Trend rozeti (#D — son 1 saatte aynı marka çok geliyorsa)
"""
import re
import time
from collections import deque

import config
from services.analiz import (
    magaza_bul, urun_adi_bul, fiyat_bul, link_bul,
    stok_kritik_mi, indirim_turu, kategori_bul,
    kupon_bul, min_siparis_bul, sahte_indirim_mi,
    firsat_skoru, _urun_adi_makul,
)
from services.zenginlestir import guvenilirlik_etiketi
from utils.log import simdi_tr


# ── Negatif ifade tespit (#I) ───────────────────────────────────
_NEGATIF_KALIP = re.compile(
    r"yanl\u0131\u015f\s*payla\u015f|iptal\s*edildi|fiyat\s*hatas\u0131|"
    r"d\u00fczeltildi|geri\s*\u00e7ekildi|geri\s*\u00e7ekilmi\u015f|"
    r"yanl\u0131\u015f\s*fiyat|hat\u0131rlatma:\s*iptal",
    re.I,
)


def negatif_mi(metin: str) -> bool:
    """Yanlış paylaşım / iptal mesajı mı?"""
    return bool(_NEGATIF_KALIP.search(metin or ""))


# ── Trend tespit (#D) ───────────────────────────────────────────
# Son 60 dakikadaki mağaza adlarını tutar
_son_magazalar: deque = deque(maxlen=50)

# Bu mağazalar "marka" değil, "site" — trend rozeti gösterme
_SITELER = {
    "Amazon TR", "Trendyol", "Hepsiburada", "MediaMarkt", "Teknosa",
    "N11", "Gratis", "Boyner", "Çiçeksepeti", "AliExpress", "Temu",
    "E-Ticaret",
}


def trend_kaydet(magaza: str) -> None:
    _son_magazalar.append((magaza, time.time()))


def trend_var_mi(magaza: str) -> bool:
    """Son 1 saatte aynı MARKADAN 3+ ürün varsa trend say.
    Site adları (Amazon, Trendyol vs.) trend olmaz — onlar zaten her zaman görünür."""
    if not magaza or magaza in _SITELER:
        return False
    simdi_ts = time.time()
    sayi = sum(1 for m, t in _son_magazalar if m == magaza and simdi_ts - t < 3600)
    return sayi >= 3


# ── Fiyat formatlama ────────────────────────────────────────────

def _fiyat_format(fiyat_str: str) -> str:
    """'1.499,00' → '1.499', '299,90' → '299,90', '50,00' → '50'."""
    if not fiyat_str:
        return fiyat_str
    s = fiyat_str.strip()
    # ,00 küsuratını sil
    s = re.sub(r",00\b", "", s)
    return s


def _tasarruf_hesapla(eski_v: float, yeni_v: float) -> int:
    """İki fiyattan tasarruf TL'sini hesapla."""
    if eski_v > yeni_v > 0:
        return int(round(eski_v - yeni_v))
    return 0


def _tasarruf_format(tasarruf: int) -> str:
    """1234 → '1.234'"""
    return f"{tasarruf:,}".replace(",", ".")


# ── Başlık ──────────────────────────────────────────────────────

def _baslik(indirim: int, tur: str, fs: float, tasarruf: int) -> str:
    """Tek satır, kontrastlı başlık.
    VIP rozet: skor 8+ veya indirim 70+
    İndirim 0 (oran belirtilmemiş ürün): fiyat odaklı başlık."""
    # VIP modu
    vip = fs >= 8.0 or indirim >= 70

    if tur == "marka":
        if vip:
            return f"💎 <b>ELİT MARKA KAMPANYASI — %{indirim}'ye varan</b>"
        return f"🏷️ <b>MARKA KAMPANYASI — %{indirim}'ye varan</b>"

    # İndirim oranı yok (0) — fiyat/fırsat odaklı başlık, "%0 İNDİRİM" YAZMA
    if indirim <= 0:
        if vip:
            return "💎 <b>ELİT FIRSAT</b>"
        return "🔥 <b>FIRSAT ÜRÜNÜ</b>"

    # Ürün — sadece %
    if vip:
        return f"💎 <b>ELİT FIRSAT — %{indirim} İNDİRİM</b>"
    if indirim >= 50:
        return f"🎯 <b>%{indirim} İNDİRİM</b>"
    if indirim >= 30:
        return f"💰 <b>%{indirim} İNDİRİM</b>"
    return f"💰 <b>%{indirim} İNDİRİM</b>"


# ── Hashtag ─────────────────────────────────────────────────────

def _hashtag(kat_hashtagler: list[str], magaza: str) -> str:
    """En fazla 3 hashtag: kategori ana etiketi + mağaza + FırsatPulsu."""
    tags: list[str] = []
    if kat_hashtagler:
        ilk = (kat_hashtagler[0] or "").strip()
        if ilk and ilk != "#":
            tags.append(ilk)   # İlk = en spesifik (boş değilse)
    mt = config.MAGAZA_HASHTAG.get(magaza, "")
    if mt:
        tags.append(mt)
    tags.append("#kacirmabak")
    return " ".join(tags)


# ── Özel etiket ─────────────────────────────────────────────────

def _ozel_etiket(metin: str) -> str | None:
    ml = (metin or "").lower()
    if any(k in ml for k in ["flash", "anlık fırsat", "saatlik fırsat"]):
        return "⚡ Flash Sale"
    if any(k in ml for k in ["son gün", "bugün bitiyor", "son 24"]):
        return "⏰ Son gün"
    if any(k in ml for k in ["ücretsiz kargo"]):
        return "📦 Ücretsiz kargo"
    return None


# ── Ürün bloğu (yeni minimalist) ────────────────────────────────

def _urun_blogu(metin: str, indirim: int, btn_links: list[str], numara: int | None = None,
                onceden_lnk: str | None = None, gemini: dict | None = None) -> list[str]:
    # onceden_lnk: çoklu modda direkt link geçilirse magaza_bul daha doğru çalışır
    # gemini: Gemini analiz sonucu — varsa ürün adı + akıllı tanıtım cümlesi kullanılır
    lnk          = onceden_lnk or link_bul(metin, btn_links)
    magaza       = magaza_bul(metin, lnk)
    # Ürün adı: Gemini'nin temiz çıkardığı ad öncelikli
    # v23.0 — TEK MERKEZİ KAPI'dan geçir
    # v23.8 — Gemini kopuk parça verebilir, saf-Python ile KARŞILAŞTIR
    from services.urun_kapisi import gecerli_urun_adi as _kapi, en_iyi_urun_adi as _eniyi0, guzellestir as _guzel0
    if gemini and gemini.get("urun_adi"):
        _gb = _kapi(gemini["urun_adi"], metin)
        _pb = _kapi(urun_adi_bul(metin), metin)
        urun = _eniyi0(_gb, _pb, metin) or _pb or urun_adi_bul(metin)
    else:
        urun = urun_adi_bul(metin)
    # v23.9 — Uzun teknik adı okunabilir hale getir
    if urun:
        urun = _guzel0(urun)
    eski_s, yeni_s, eski_v, yeni_v = fiyat_bul(metin)
    # v23.16 — TUTARLILIK: İki fiyat belliyse indirim oranını OTOMATİK hesapla.
    if (not indirim or indirim <= 0) and eski_v and yeni_v and eski_v > yeni_v > 0:
        _hes = int(round((eski_v - yeni_v) / eski_v * 100))
        if _hes >= 1:
            indirim = _hes
    tur          = indirim_turu(metin)
    kat, ikon, _ = kategori_bul(metin)
    # Kategori tahmini için TEMİZ ürün adını kullan — tam metindeki gürültü
    # (#İşbirliği, Karşılaştır, fiyatlar, "Stokta var") kategoriyi şaşırtıyor.
    # Ürün adı varsa kategori SADECE ondan belirlensin (çok daha isabetli).
    from services.analiz import urun_adi_bul as _uab
    # v23.8 — Gemini kopuk parça verebilir, saf-Python ile karşılaştır
    try:
        from services.urun_kapisi import en_iyi_urun_adi as _eniyi2
        _g_ad = (gemini or {}).get("urun_adi")
        _p_ad = _uab(metin)
        _temiz_ad = _eniyi2(_g_ad, _p_ad, metin) or _p_ad or metin
    except Exception:
        _temiz_ad = (gemini or {}).get("urun_adi") or _uab(metin) or metin
    # Temiz ad ile kategoriyi yeniden belirle (gürültüsüz → isabetli)
    _kat2, _ikon2, _ = kategori_bul(_temiz_ad)
    if _kat2 != "genel":
        kat, ikon = _kat2, _ikon2
    etiket       = _ozel_etiket(metin)
    kupon        = kupon_bul(metin)
    min_sip      = min_siparis_bul(metin)
    # Gemini akıllı tanıtım cümlesi (varsa)
    tanitim      = (gemini or {}).get("tanitim", "")

    # Alt-kategori bilgisi (hiyerarşik) — şablon yazısı için
    # Gemini varsa onun kategori/alt_kategorisi ÖNCELİKLİ (daha doğru)
    # Alt kategoriye özel ikon (minimal-şık görsel ayrım)
    _ALT_IKON = {
        "ses": "🎧", "telefon": "📱", "saat": "⌚", "tv": "📺",
        "kamera": "📷", "bilgisayar": "💻", "beyaz_esya": "🔌",
        "ayakkabi": "👟", "canta": "👜", "parfum": "🌸", "makyaj": "💄",
        "oyuncak": "🧸", "lego": "🧱", "konsol": "🎮", "lastik": "🛞",
        "vitamin": "💊", "bez": "🍼", "kahve": "☕",
    }
    try:
        from services.analiz import kategori_bul_tam
        from utils.ml_kategoriler import kategori_bilgisi
        g_kat = (gemini or {}).get("kategori", "")
        g_alt = (gemini or {}).get("alt_kategori", "")
        # v23.2 — ÇAPRAZ DOĞRULAMA: Gemini'nin kategorisi saf-Python ile
        # çelişiyorsa Gemini'ye güvenme. "Otogizoshi" (kitap) → Gemini "oto"
        # heceesine bakıp "otomotiv" diyordu; saf-Python ise "genel" diyor.
        # Gemini bir kategori iddia ediyor ama metinde o kategorinin izi yoksa
        # (saf-Python "genel" diyorsa) → Gemini muhtemelen uydurmuş, reddet.
        py_ana, py_alt, py_guven = kategori_bul_tam(_temiz_ad)
        _esik = config.KATEGORI_GUVEN_ESIK / 100.0
        gemini_guvenli = True   # Varsayılan: Gemini'ye güven (genelde haklı)
        if g_kat and g_kat != "genel":
            if py_ana == g_kat and py_guven >= _esik:
                gemini_guvenli = True   # ikisi hemfikir → kesin
            elif py_ana != "genel" and py_guven >= _esik and py_ana != g_kat:
                # Saf-Python YÜKSEK güvenle FARKLI kategori diyor → Gemini şüpheli
                gemini_guvenli = False
            else:
                # Saf-Python emin değil. Gemini'yi kabul et AMA "hece tuzağı"
                # kontrolü yap: Gemini'nin kategorisinin ipucu kelimesi ürün
                # adında TAM KELİME olarak yok ama ALT-DİZGİ olarak varsa
                # (örn "oto" → "Otogizoshi") → bu uydurma, reddet.
                try:
                    from services.urun_kapisi import _KATEGORI_IPUCU, _kelimeler
                    ipuclari = _KATEGORI_IPUCU.get(g_kat, set())
                    ad_low = (_temiz_ad or "").replace("İ","i").replace("I","ı").lower()
                    kelime_set = set(_kelimeler(_temiz_ad))
                    tam_kelime_var = bool(ipuclari & kelime_set)
                    # Alt-dizgi tuzağı: kısa bir ipucu (oto, araç) ürün adının
                    # İÇİNDE geçiyor ama tam kelime değil
                    alt_dizgi_tuzak = False
                    for ip in ipuclari:
                        if len(ip) <= 4 and ip in ad_low and ip not in kelime_set:
                            alt_dizgi_tuzak = True
                            break
                    if alt_dizgi_tuzak and not tam_kelime_var:
                        gemini_guvenli = False   # "Otogizoshi"→oto tuzağı
                    else:
                        gemini_guvenli = True    # AirPods gibi gerçek ürün → güven
                except Exception:
                    gemini_guvenli = True
        if gemini_guvenli:
            bilgi = kategori_bilgisi(g_kat, g_alt or None)
            kat = g_kat
            if bilgi.get("ikon"):
                ikon = bilgi["ikon"]
            if g_alt in _ALT_IKON:
                ikon = _ALT_IKON[g_alt]
        else:
            # v23.2 — Gemini reddedildi. Saf-Python'a düş AMA sadece YÜKSEK
            # güvenliyse. "Otogizoshi" giyim 0.15 → güvenilmez, "genel" kalsın.
            if py_ana != "genel" and py_guven >= _esik:
                bilgi = kategori_bilgisi(py_ana, py_alt or None)
                kat = py_ana
            else:
                bilgi = kategori_bilgisi("genel", None)
        kat_yazi = bilgi.get("yazi", config.KATEGORI_YAZI.get(kat, "Alışveriş"))
    except Exception:
        kat_yazi = config.KATEGORI_YAZI.get(kat, "Alışveriş")

    fs           = firsat_skoru(metin, indirim, btn_links)
    # Gemini "mükemmel fırsat" (kalite 5) dediyse fırsat skorunu yükselt →
    # başlıkta 💎 ELİT rozeti tetiklenir (minimal-şık vurgu, ekstra satır yok)
    g_kalite     = (gemini or {}).get("kalite", 0)
    if g_kalite >= 5:
        fs = max(fs + 3.0, 8.0)   # kalite 5 → garanti ELİT rozet
    elif g_kalite == 4:
        fs += 1.5
    tasarruf     = _tasarruf_hesapla(eski_v, yeni_v)

    eski_s = _fiyat_format(eski_s) if eski_s else None
    yeni_s = _fiyat_format(yeni_s) if yeni_s else None

    pref = f"{numara}️⃣  " if numara else ""
    s: list[str] = []

    if tur == "marka":
        s.append(f"{pref}{_baslik(indirim, tur, fs, tasarruf)}")
        s.append("")
        # Ürün adı varsa onu, yoksa kampanyayı tanımlayan başlık
        if urun:
            s.append(f"<b>{urun}</b>")
        elif kat != "genel":
            s.append(f"<b>{magaza} • {kat_yazi} ürünleri</b>")
        else:
            s.append(f"<b>{magaza} kampanyası</b>")
        s.append("")
        s.append(f"{ikon} {kat_yazi}  •  🏪 {magaza}")
    else:
        s.append(f"{pref}{_baslik(indirim, tur, fs, tasarruf)}")
        s.append("")
        if urun:
            s.append(f"<b>{urun}</b>")
        elif kat != "genel":
            s.append(f"<b>{kat_yazi} fırsatı</b>")
        else:
            s.append(f"<b>İndirimli ürün</b>")
        # Gemini akıllı tanıtım cümlesi (varsa) — ürün adının altında, şık
        # v23.2 — DOĞRULA: kategoriyle çelişen uydurma açıklamaları at
        # ("Otogizoshi" kitabı için "aracınız için pratik çözüm" gibi)
        if tanitim:
            try:
                from services.urun_kapisi import tanitim_gecerli
                _t = tanitim_gecerli(tanitim, urun or "", kat)
            except Exception:
                _t = tanitim
            if _t:
                s.append(f"<i>{_t}</i>")
        s.append("")
        # Fiyat: temiz, çift satır
        if eski_s and yeni_s:
            s.append(f"🟢 <b>{yeni_s} TL</b>   <s>{eski_s} TL</s>")
        elif yeni_s:
            s.append(f"🟢 <b>{yeni_s} TL</b>")
        s.append(f"{ikon} {kat_yazi}  •  🏪 {magaza}")

    # Trend rozeti
    if trend_var_mi(magaza):
        s.append("🔥 <i>Bu marka bugün çok hareketli</i>")

    # Etiketler (varsa)
    if etiket:
        s.append(etiket)

    # Güvenilirlik
    guven = guvenilirlik_etiketi(lnk)
    if guven:
        s.append(guven)

    # v22.10 — Sistem 4+5+7: Fiyat geçmişi & stok rozetleri
    try:
        if lnk:
            from utils import fiyat_takip
            from services.analiz import urun_kimligi
            kim = urun_kimligi(lnk)
            if kim and yeni_v:
                analiz = fiyat_takip.fiyat_analiz(kim, yeni_v)
                if analiz["en_dusuk_mu"] and analiz["kayit_sayisi"] >= 2:
                    s.append("💎 <b>Son 30 günün en düşük fiyatı!</b>")
                elif analiz["sahte_indirim_mi"]:
                    s.append("⚠️ <i>Fiyat geçmişi sabit — indirim oranını araştır</i>")
                elif (analiz.get("gecmis_max") and analiz["kayit_sayisi"] >= 2
                      and analiz["gecmis_max"] > yeni_v):
                    # v23.9 — Geçmişe göre ne kadar ucuzladı? (güven veren bağlam)
                    fark = analiz["gecmis_max"] - yeni_v
                    yuzde = int(fark / analiz["gecmis_max"] * 100)
                    if yuzde >= 5:
                        _gm = analiz["gecmis_max"]
                        eski_str = f"{_gm:,.0f}".replace(",", ".")
                        s.append(f"📉 <i>Geçen ay {eski_str} TL'ydi (%{yuzde} ucuzladı)</i>")
                # Stok geri-gelme
                durum = fiyat_takip.stok_kontrol(kim)
                if durum == "yeniden_stokta":
                    s.append("🔄 <i>Yeniden stokta!</i>")
                # v23.19 — "Şimdi al / bekle" zekâsı (fiyat geçmişi konumu)
                # "en düşük" rozeti YOKSA göster (çift mesaj olmasın)
                if not (analiz["en_dusuk_mu"] and analiz["kayit_sayisi"] >= 2):
                    try:
                        tavsiye = fiyat_takip.al_bekle_tavsiyesi(kim, yeni_v)
                        if tavsiye:
                            s.append(tavsiye)
                    except Exception:
                        pass
    except Exception:
        pass

    # Stok / uyarılar
    if stok_kritik_mi(metin):
        s.append("🚨 <b>Son stoklar</b>")
    # Fiyat uyarısı: Gemini'nin akıllı değerlendirmesi öncelikli, yoksa saf-Python
    g_fiyat_uyari = (gemini or {}).get("fiyat_uyari", "")
    if g_fiyat_uyari:
        s.append(f"⚠️ <i>{g_fiyat_uyari}</i>")
    elif sahte_indirim_mi(metin, indirim):
        s.append("⚠️ <i>Bu oran alışılmışın dışında, araştırarak satın al</i>")

    # Kupon / min
    if kupon:
        s.append(f"🎟️ Kupon: <code>{kupon}</code>")
    if min_sip:
        s.append(f"🛒 Min. {min_sip} alışverişte")

    return s


# ── Tek ürün şablonu ────────────────────────────────────────────

def _marka_kampanya_gecerli(metin: str) -> bool:
    """v22.6 — Gerçek marka kampanyası mı, yoksa çöp mü?
    Geçerli: 'Nike ürünlerinde %40', 'LCW markasında %30 indirim'
    Çöp:     'Amazon TR', 'elektronik ürünlerde' (mağaza/jenerik kategori)
    """
    if not metin:
        return False
    import re as _re
    ml = metin.replace("İ", "i").replace("I", "ı").lower()
    _MAGAZALAR = ("amazon", "trendyol", "hepsiburada", "n11", "mediamarkt",
                  "teknosa", "vatan", "gittigidiyor", "morhipo", "boyner",
                  "carrefour", "migros", "a101", "bim", "şok")
    _JENERIK = ("elektronik", "giyim", "kozmetik", "mobilya", "spor",
                "kitap", "oyuncak", "beyaz eşya", "ev ürünleri")
    m = _re.search(r"(\w+)\s*(?:markasında|markasinda|ürünlerinde|urunlerinde|serisinde)", ml)
    if m:
        marka = m.group(1).strip()
        if marka in _MAGAZALAR or marka in _JENERIK:
            return False
        if len(marka) >= 2 and _re.search(r"[a-zçğıöşü]", marka):
            return True
    return False


def olustur(metin: str, indirim: int, buton_linkleri: list[str] | None = None,
            gemini: dict | None = None) -> str | None:
    # NOT: indirim <= 0 olan ürünleri de paylaşıyoruz (fiyat odaklı başlık).
    # gemini: Gemini analiz sonucu — varsa akıllı ürün adı + tanıtım kullanılır.
    if negatif_mi(metin):
        return None
    # Ürün adı: Gemini varsa onu kullan (boş slogan kontrolü için)
    # v23.0 — TEK MERKEZİ KAPI'dan geçir (Amazon vb çöp burada elenir)
    # v23.8 — Gemini ile saf-Python KARŞILAŞTIR: Gemini bazen uzun ürün adının
    # ortasından kopuk parça veriyor ("Apple iPad ... Gümüş Rengi" yerine
    # "Gün Süren Pil Ömrü Gümüş Rengi Satıcı Amazon Depo"). Mesaj başıyla
    # örtüşen ad doğrudur.
    from services.urun_kapisi import gecerli_urun_adi as _kapi2, en_iyi_urun_adi as _eniyi, guzellestir as _guzel
    _g_urun = (gemini or {}).get("urun_adi")
    if _g_urun:
        _g_aday = _kapi2(_g_urun, metin)
        _p_aday = _kapi2(urun_adi_bul(metin), metin)
        _urun = _eniyi(_g_aday, _p_aday, metin) or _p_aday or urun_adi_bul(metin)
    else:
        _urun = urun_adi_bul(metin)
    # v23.9 — Uzun teknik adı okunabilir hale getir
    if _urun:
        _urun = _guzel(_urun)
    _tur_on = indirim_turu(metin)
    # v22.6 — Marka kampanyası DESTEKLENİYOR (kullanıcı istedi) ama güvenli:
    #   • Ürün adı varsa → normal ürün paylaşımı
    #   • Ürün adı yok AMA gerçek marka kampanyası ise → marka şablonu
    #   • Ürün adı yok VE marka kampanyası da değilse → çöp, paylaşma
    if not _urun and _tur_on != "marka":
        return None
    if not _urun and _tur_on == "marka":
        if not _marka_kampanya_gecerli(metin):
            return None
    bl  = buton_linkleri or []
    lnk = link_bul(metin, bl)
    mag = magaza_bul(metin, lnk)
    # Hashtag/kategori için TEMİZ ürün adı kullan (gürültü kategoriyi şaşırtmasın)
    # v23.8 — Gemini kopuk parça verebilir, saf-Python ile karşılaştır
    try:
        from services.urun_kapisi import en_iyi_urun_adi as _eniyi3
        _temiz = _eniyi3((gemini or {}).get("urun_adi"), urun_adi_bul(metin), metin) \
                 or urun_adi_bul(metin) or metin
    except Exception:
        _temiz = (gemini or {}).get("urun_adi") or urun_adi_bul(metin) or metin
    kat, _, kat_tags = kategori_bul(_temiz)
    if kat == "genel":
        kat, _, kat_tags = kategori_bul(metin)   # ad işe yaramazsa tam metne dön
    # Gemini kategori verdiyse onu kullan (daha doğru) — ikon + hashtag için
    g_kat = (gemini or {}).get("kategori", "")
    g_alt = (gemini or {}).get("alt_kategori", "")
    try:
        from utils.ml_kategoriler import kategori_bilgisi
        from services.analiz import kategori_bul_tam
        # v23.2 — ÇAPRAZ DOĞRULAMA (hashtag): _urun_blogu ile aynı yumuşak mantık.
        # Gemini'ye güven, sadece hece-tuzağında ("oto"→Otogizoshi) reddet.
        py_ana, py_alt, py_guven = kategori_bul_tam(_temiz)
        _esik = config.KATEGORI_GUVEN_ESIK / 100.0
        g_guvenli = True
        if g_kat and g_kat != "genel":
            if py_ana != "genel" and py_guven >= _esik and py_ana != g_kat:
                g_guvenli = False
            else:
                try:
                    from services.urun_kapisi import _KATEGORI_IPUCU, _kelimeler
                    ipuclari = _KATEGORI_IPUCU.get(g_kat, set())
                    ad_low = (_temiz or "").replace("İ","i").replace("I","ı").lower()
                    kelime_set = set(_kelimeler(_temiz))
                    tam_kelime_var = bool(ipuclari & kelime_set)
                    alt_dizgi_tuzak = any(
                        len(ip) <= 4 and ip in ad_low and ip not in kelime_set
                        for ip in ipuclari)
                    g_guvenli = not (alt_dizgi_tuzak and not tam_kelime_var)
                except Exception:
                    g_guvenli = True
        if g_kat and g_kat != "genel" and g_guvenli:
            bilgi = kategori_bilgisi(g_kat, g_alt) if g_alt else kategori_bilgisi(g_kat, "")
            if bilgi and bilgi.get("hashtag"):
                kat_tags = bilgi["hashtag"]
                kat = g_kat
        else:
            if py_ana != "genel" and py_guven >= _esik:
                alt_bilgi = kategori_bilgisi(py_ana, py_alt) if py_alt else kategori_bilgisi(py_ana, "")
                if alt_bilgi.get("hashtag"):
                    kat_tags = alt_bilgi["hashtag"]
                    kat = py_ana
    except Exception:
        pass
    kanal   = config.HEDEF_KANAL.lstrip("@")
    hashtag = _hashtag(kat_tags, mag)

    # Trend için mağazayı kayıt
    trend_kaydet(mag)

    s = _urun_blogu(metin, indirim, bl, gemini=gemini)
    s += ["", hashtag, f"@{kanal}"]
    cikti = "\n".join(s)

    # ── KALİTE KAPISI: bozuk/eksik şablonu paylaşma (merkezi savunma) ──
    if not _sablon_kalite_gecer(cikti, _urun, lnk, indirim_turu(metin)):
        return None

    # v22.9 — Sistem 2: Kalite puanı kapısı. Düşük puanlı paylaşımları ele.
    try:
        import config as _cfg
        if getattr(_cfg, "KALITE_PUAN_ESIK", 0) > 0:
            from utils import kalite
            from services.analiz import kategori_bul_tam, fiyat_bul
            ana_k, _, guven = kategori_bul_tam(_urun or metin)
            eski_s, yeni_s, eski_v, yeni_v = fiyat_bul(metin)
            gecer = kalite.degerlendir(
                _urun, ana_k, guven, indirim, eski_v, yeni_v,
                gorsel_var=True,   # şablon aşamasında varsayılan
                link=lnk, esik=_cfg.KALITE_PUAN_ESIK,
            )
            if not gecer:
                return None
    except Exception:
        pass   # kalite modülü hatası paylaşımı engellememellİ

    return cikti


def _sablon_kalite_gecer(cikti: str, urun: str | None, link: str | None,
                         tur: str) -> bool:
    """Üretilen şablon paylaşılmaya uygun mu? Son savunma katmanı.
    Bozuk/eksik çıktıları yakalar — canlıda 'kötü paylaşım' olmasın."""
    if not cikti or len(cikti) < 30:
        return False
    # Link yoksa (marka kampanyası hariç) paylaşma — kullanıcı tıklayacak yer yok
    if not link and tur != "marka":
        return False
    # Ürün adı yer tutucu/çöp mü? ("İndirimli ürün", mağaza adı tek başına)
    dusuk_kalite_adlar = ("indirimli ürün", "ürün fırsatı", "kampanya")
    if urun and urun.strip().lower() in dusuk_kalite_adlar:
        # Bu jenerik adlar sadece marka kampanyasında kabul (gerçek ürün değil)
        if tur != "marka":
            return False
    # v23.1 — Ürün adı doğrulaması TEK merkezi kapıda (urun_kapisi).
    # Eskiden buradaki _COP_BASLIK listesi kapıyla tekrar ediyordu.
    if urun:
        try:
            from services.urun_kapisi import gecerli_mi
            if not gecerli_mi(urun):
                return False
        except Exception:
            pass

    # Fiyat satırı varsa ama "0 TL" / boş fiyat → bozuk
    if "🟢 <b> TL" in cikti or "🟢 <b>0 TL" in cikti:
        return False
    return True


# ── İki ürün, tek mesaj şablonu ─────────────────────────────────

def olustur_coklu(
    blok1: str, indirim1: int, lnk1: str | None,
    blok2: str, indirim2: int, lnk2: str | None,
    btn_links: list[str] | None = None,
) -> str | None:
    if (indirim1 <= 0 and indirim2 <= 0) or negatif_mi(blok1) or negatif_mi(blok2):
        return None

    # v22.6 — Güvenlik: İki bloğun ürün adı AYNI ise, bunlar aslında tek üründür
    # (yanlışlıkla 2 kopya). Tek ürün şablonuyla paylaş — "aynı isim 2 kez" olmasın.
    _ad1 = urun_adi_bul(blok1)
    _ad2 = urun_adi_bul(blok2)
    if _ad1 and _ad2 and _ad1.strip().lower() == _ad2.strip().lower():
        if indirim1 >= indirim2:
            return olustur(blok1, indirim1, [lnk1] if lnk1 else btn_links)
        return olustur(blok2, indirim2, [lnk2] if lnk2 else btn_links)

    bl    = btn_links or []
    # Mağaza tespitinde link öncelikli — bu fix #5
    mag1  = magaza_bul(blok1, lnk1)
    mag2  = magaza_bul(blok2, lnk2)
    ana_blok = blok1 if indirim1 >= indirim2 else blok2
    ana_mag  = mag1  if indirim1 >= indirim2 else mag2
    _, _, kat_tags = kategori_bul(ana_blok)
    kanal   = config.HEDEF_KANAL.lstrip("@")
    hashtag = _hashtag(kat_tags, ana_mag)

    # Trend için her iki mağaza
    trend_kaydet(mag1)
    trend_kaydet(mag2)

    s: list[str] = ["🎯 <b>2 ÜRÜN — TEK MESAJ</b>", ""]
    s += _urun_blogu(blok1, indirim1, bl, numara=1, onceden_lnk=lnk1)
    s += ["", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", ""]
    s += _urun_blogu(blok2, indirim2, bl, numara=2, onceden_lnk=lnk2)
    s += ["", hashtag, f"@{kanal}"]
    return "\n".join(s)
