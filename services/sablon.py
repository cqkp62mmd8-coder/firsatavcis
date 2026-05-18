"""
Telegram HTML şablonu: ham mesajı kanalda paylaşılacak metne dönüştürür.
olustur()       → tek ürün
olustur_coklu() → 2 ürün tek mesajda
"""
from datetime import datetime

import config
from services.analiz import (
    magaza_bul, urun_adi_bul, fiyat_bul, link_bul,
    stok_kritik_mi, indirim_turu, kategori_bul,
    kupon_bul, min_siparis_bul, sahte_indirim_mi,
    firsat_skoru, firsat_yildiz, indirim_yildiz,
)


# ── Yardımcılar ─────────────────────────────────────────────────

def _ozel_etiket(metin: str, indirim: int) -> str | None:
    ml = metin.lower()
    if any(k in ml for k in ["flash", "anlık", "saatlik"]): return "⚡ FLASH SALE"
    if any(k in ml for k in ["hediye", "ücretsiz kargo"]):  return "🎁 HEDİYE KAMPANYA"
    if any(k in ml for k in ["son gün", "bugün bitiyor"]):  return "⏰ SON GÜN"
    if indirim >= 70:                                         return "🏆 SÜPER FIRSAT"
    return None


def _baslik(indirim: int, tur: str) -> str:
    if tur == "marka":
        return f"🏷️ <b>MARKA İNDİRİMİ — %{indirim}</b>"
    if indirim >= 70: return f"🔥 <b>YANGIN FİYAT — %{indirim} İNDİRİM</b>"
    if indirim >= 50: return f"🔥 <b>BÜYÜK İNDİRİM — %{indirim}</b>"
    if indirim >= 30: return f"💰 <b>FIRSAT — %{indirim} İNDİRİM</b>"
    return f"💰 <b>%{indirim} İNDİRİM</b>"


def _hashtag(kat_hashtagler: list[str], magaza: str) -> str:
    tags = list(kat_hashtagler)
    mt = config.MAGAZA_HASHTAG.get(magaza, "")
    if mt and mt not in tags:
        tags.append(mt)
    tags.append("#FırsatPulsu")
    return " ".join(tags)


def _urun_blogu(metin: str, indirim: int, btn_links: list[str], numara: int | None = None) -> list[str]:
    """Tek ürün için satır listesi döndürür. numara=None ise tek ürün, 1/2 ise çoklu."""
    lnk          = link_bul(metin, btn_links)
    magaza       = magaza_bul(metin, lnk)
    urun         = urun_adi_bul(metin)
    eski_s, yeni_s, _, _ = fiyat_bul(metin)
    tur          = indirim_turu(metin)
    kat, ikon, _ = kategori_bul(metin)
    etiket       = _ozel_etiket(metin, indirim)
    kupon        = kupon_bul(metin)
    min_sip      = min_siparis_bul(metin)
    m_emoji      = config.MAGAZA_EMOJI.get(magaza, "🛒")
    kat_yazi     = config.KATEGORI_YAZI.get(kat, "Alışveriş")
    zaman        = simdi_tr().strftime("%H:%M")
    fs           = firsat_skoru(metin, indirim, btn_links)
    fs_y         = firsat_yildiz(fs)
    yildiz       = indirim_yildiz(indirim)
    baslik       = _baslik(indirim, tur)

    pref = f"{numara}. " if numara else ""
    s: list[str] = []

    if tur == "marka":
        s += [f"{pref}{baslik}", ""]
        s.append(f"{m_emoji} <b>{magaza}</b>  •  {ikon} {kat_yazi}")
        s += ["", f"Seçili ürünlerde <b>%{indirim}'ye varan</b> indirim"]
        if etiket: s.append(etiket)
        if kupon:   s.append(f"🎟️ Kupon: <code>{kupon}</code>")
        if min_sip: s.append(f"🛒 Min. {min_sip} alışverişte geçerli")
        s.append(f"⏰ Sınırlı süre!  •  🕐 {zaman}")
    else:
        s.append(f"{pref}{baslik}  {yildiz}")
        s.append(f"📊 Fırsat Skoru: <b>{fs}/10</b>  {fs_y}")
        if etiket: s.append(etiket)
        s.append("")
        if urun: s.append(f"📌 <b>{urun}</b>")
        s.append(f"{ikon} {kat_yazi}")
        s.append("")
        if eski_s and yeni_s:
            s.append(f"🏷️ Normal Fiyat:    <s>{eski_s} TL</s>")
            s.append(f"💰 İndirimli Fiyat: <b>{yeni_s} TL</b>")
        elif yeni_s:
            s.append(f"💰 Fiyat: <b>{yeni_s} TL</b>")
        s.append("")
        s.append(f"{m_emoji} <b>{magaza}</b>  •  🕐 {zaman}")
        if stok_kritik_mi(metin): s.append("⚠️ <b>Son stoklar!</b>")
        if sahte_indirim_mi(metin, indirim):
            s.append("⚠️ <i>Bu indirim oranı alışılmışın dışında, satın almadan araştırın.</i>")
        if kupon:   s.append(f"🎟️ Kupon: <code>{kupon}</code>")
        if min_sip: s.append(f"🛒 Min. {min_sip} alımda geçerli")

    return s


# ── Tek ürün şablonu ────────────────────────────────────────────

def olustur(metin: str, indirim: int, buton_linkleri: list[str] | None = None) -> str | None:
    if indirim <= 0:
        return None
    bl  = buton_linkleri or []
    lnk = link_bul(metin, bl)
    mag = magaza_bul(metin, lnk)
    kat, _, kat_tags = kategori_bul(metin)
    kanal   = config.HEDEF_KANAL.lstrip("@")
    hashtag = _hashtag(kat_tags, mag)

    s = _urun_blogu(metin, indirim, bl)
    s += ["", "──────────────────────", hashtag, f"📢 @{kanal}"]
    return "\n".join(s)


# ── İki ürün, tek mesaj şablonu ─────────────────────────────────

def olustur_coklu(
    blok1: str, indirim1: int, lnk1: str | None,
    blok2: str, indirim2: int, lnk2: str | None,
    btn_links: list[str] | None = None,
) -> str | None:
    """İki ürünü tek Telegram mesajında birleştirir."""
    if indirim1 <= 0 and indirim2 <= 0:
        return None

    bl    = btn_links or []
    mag1  = magaza_bul(blok1, lnk1)
    mag2  = magaza_bul(blok2, lnk2)
    # Birincil hashtag en yüksek indirimli üründen alınır
    ana_blok = blok1 if indirim1 >= indirim2 else blok2
    ana_mag  = mag1  if indirim1 >= indirim2 else mag2
    _, _, kat_tags = kategori_bul(ana_blok)
    kanal   = config.HEDEF_KANAL.lstrip("@")
    hashtag = _hashtag(kat_tags, ana_mag)

    s: list[str] = ["🔥 <b>ÇOKLU FIRSAT — 2 ÜRÜN</b>", ""]

    # Ürün 1
    s += _urun_blogu(blok1, indirim1, bl, numara=1)
    if lnk1:
        s.append(f"🔗 <a href='{lnk1}'>1. Ürüne Git</a>")

    s += ["", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", ""]

    # Ürün 2
    s += _urun_blogu(blok2, indirim2, bl, numara=2)
    if lnk2:
        s.append(f"🔗 <a href='{lnk2}'>2. Ürüne Git</a>")

    s += ["", "──────────────────────", hashtag, f"📢 @{kanal}"]
    return "\n".join(s)
