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
    firsat_skoru,
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
        tags.append(kat_hashtagler[0])   # İlk = en spesifik
    mt = config.MAGAZA_HASHTAG.get(magaza, "")
    if mt:
        tags.append(mt)
    tags.append("#FırsatPulsu")
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
                onceden_lnk: str | None = None) -> list[str]:
    # onceden_lnk: çoklu modda direkt link geçilirse magaza_bul daha doğru çalışır
    lnk          = onceden_lnk or link_bul(metin, btn_links)
    magaza       = magaza_bul(metin, lnk)
    urun         = urun_adi_bul(metin)
    eski_s, yeni_s, eski_v, yeni_v = fiyat_bul(metin)
    tur          = indirim_turu(metin)
    kat, ikon, _ = kategori_bul(metin)
    etiket       = _ozel_etiket(metin)
    kupon        = kupon_bul(metin)
    min_sip      = min_siparis_bul(metin)

    # Alt-kategori bilgisi (hiyerarşik) — şablon yazısı için
    try:
        from services.analiz import kategori_bul_tam
        from utils.ml_kategoriler import kategori_bilgisi
        ana_k, alt_k, _ = kategori_bul_tam(metin)
        bilgi = kategori_bilgisi(ana_k, alt_k or None)
        kat_yazi = bilgi.get("yazi", config.KATEGORI_YAZI.get(kat, "Alışveriş"))
    except Exception:
        kat_yazi = config.KATEGORI_YAZI.get(kat, "Alışveriş")

    fs           = firsat_skoru(metin, indirim, btn_links)
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

    # Stok / uyarılar
    if stok_kritik_mi(metin):
        s.append("🚨 <b>Son stoklar</b>")
    if sahte_indirim_mi(metin, indirim):
        s.append("⚠️ <i>Bu oran alışılmışın dışında, araştırarak satın al</i>")

    # Kupon / min
    if kupon:
        s.append(f"🎟️ Kupon: <code>{kupon}</code>")
    if min_sip:
        s.append(f"🛒 Min. {min_sip} alışverişte")

    return s


# ── Tek ürün şablonu ────────────────────────────────────────────

def olustur(metin: str, indirim: int, buton_linkleri: list[str] | None = None) -> str | None:
    # NOT: indirim <= 0 olan ürünleri de paylaşıyoruz (fiyat odaklı başlık).
    # Sadece negatif/yasak içerik reddedilir.
    if negatif_mi(metin):
        return None
    # Ürün adı yoksa (slogan/CTA-only mesaj) — marka kampanyası değilse paylaşma
    if not urun_adi_bul(metin) and indirim_turu(metin) != "marka":
        return None
    bl  = buton_linkleri or []
    lnk = link_bul(metin, bl)
    mag = magaza_bul(metin, lnk)
    kat, _, kat_tags = kategori_bul(metin)
    # Alt kategori hashtag varsa, daha spesifik etiket için onu kullan
    try:
        from services.analiz import kategori_bul_tam
        from utils.ml_kategoriler import kategori_bilgisi
        ana_k, alt_k, _ = kategori_bul_tam(metin)
        if alt_k:
            alt_bilgi = kategori_bilgisi(ana_k, alt_k)
            kat_tags = alt_bilgi.get("hashtag", kat_tags)
    except Exception:
        pass
    kanal   = config.HEDEF_KANAL.lstrip("@")
    hashtag = _hashtag(kat_tags, mag)

    # Trend için mağazayı kayıt
    trend_kaydet(mag)

    s = _urun_blogu(metin, indirim, bl)
    s += ["", hashtag, f"@{kanal}"]
    return "\n".join(s)


# ── İki ürün, tek mesaj şablonu ─────────────────────────────────

def olustur_coklu(
    blok1: str, indirim1: int, lnk1: str | None,
    blok2: str, indirim2: int, lnk2: str | None,
    btn_links: list[str] | None = None,
) -> str | None:
    if (indirim1 <= 0 and indirim2 <= 0) or negatif_mi(blok1) or negatif_mi(blok2):
        return None

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
