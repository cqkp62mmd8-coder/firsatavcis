"""
Şablon oluşturma: ham mesajdan Telegram HTML çıktısı üretir.
"""
import re
from datetime import datetime
from config.settings import HEDEF_KANAL, MAGAZA_EMOJI, MAGAZA_HASHTAG, KATEGORI_YAZI
from core.parser import (
    magaza_bul, urun_adi_bul, fiyat_bul, link_bul,
    stok_durumu_bul, indirim_turu_bul, kategori_bul,
    kupon_bul, minimum_siparis_bul, sahte_indirim_mi,
    firsat_skoru_hesapla,
)


# ─── Yardımcılar ───────────────────────────────────────────────
def ozel_etiket(metin: str, indirim: int) -> str | None:
    ml = metin.lower()
    if any(k in ml for k in ["flash", "anlık", "saatlik"]):  return "⚡ FLASH SALE"
    if any(k in ml for k in ["hediye", "ücretsiz kargo"]):   return "🎁 HEDİYE KAMPANYA"
    if any(k in ml for k in ["son gün", "bugün bitiyor"]):   return "⏰ SON GÜN"
    if indirim >= 70:                                          return "🏆 SÜPER FIRSAT"
    return None


def yildiz_goster(indirim: int) -> str:
    if indirim >= 80: return "⭐⭐⭐⭐⭐"
    if indirim >= 70: return "⭐⭐⭐⭐"
    if indirim >= 60: return "⭐⭐⭐"
    return "⭐⭐"


def firsat_skoru_yildiz(skor: float) -> str:
    if skor >= 9:   return "🌟🌟🌟🌟🌟"
    if skor >= 7.5: return "🌟🌟🌟🌟"
    if skor >= 6:   return "🌟🌟🌟"
    if skor >= 4:   return "🌟🌟"
    return "🌟"


def akilli_baslik(indirim: int, indirim_turu: str) -> str:
    if indirim_turu == "marka":
        return f"🏷️ <b>MARKA İNDİRİMİ — %{indirim}</b>"
    if indirim >= 70: return f"🔥 <b>YANGIN FİYAT — %{indirim} İNDİRİM</b>"
    if indirim >= 50: return f"🔥 <b>BÜYÜK İNDİRİM — %{indirim}</b>"
    if indirim >= 30: return f"💰 <b>FIRSAT — %{indirim} İNDİRİM</b>"
    return f"💰 <b>%{indirim} İNDİRİM</b>"


def hashtag_olustur(kategori_hashtagler: list, magaza: str) -> str:
    hashtagler = list(kategori_hashtagler)
    mt = MAGAZA_HASHTAG.get(magaza, "")
    if mt and mt not in hashtagler:
        hashtagler.append(mt)
    hashtagler.append("#FırsatPulsu")
    return " ".join(hashtagler)


# ─── Ana Şablon ────────────────────────────────────────────────
def sablon_olustur(metin: str, indirim: int, buton_linkleri: list | None = None) -> str | None:
    if indirim <= 0:
        return None

    magaza       = magaza_bul(metin)
    urun         = urun_adi_bul(metin)
    eski_str, yeni_str, _, _ = fiyat_bul(metin)
    link         = link_bul(metin, buton_linkleri)
    stok_kritik  = stok_durumu_bul(metin)
    indirim_turu = indirim_turu_bul(metin)
    kat_adi, kat_ikon, kat_hashtagler = kategori_bul(metin)
    kupon        = kupon_bul(metin)
    min_siparis  = minimum_siparis_bul(metin)
    etiket       = ozel_etiket(metin, indirim)
    m_emoji      = MAGAZA_EMOJI.get(magaza, "🛒")
    kat_yazi     = KATEGORI_YAZI.get(kat_adi, "Alışveriş")
    kanal        = HEDEF_KANAL.lstrip("@")
    hashtagler   = hashtag_olustur(kat_hashtagler, magaza)
    baslik       = akilli_baslik(indirim, indirim_turu)
    zaman        = datetime.now().strftime("%H:%M")
    yildiz       = yildiz_goster(indirim)
    fs_skor      = firsat_skoru_hesapla(metin, indirim, buton_linkleri or [])
    fs_yildiz    = firsat_skoru_yildiz(fs_skor)

    s = []

    if indirim_turu == "marka":
        s.append(baslik)
        s.append("")
        s.append(f"{m_emoji} <b>{magaza}</b>  •  {kat_ikon} {kat_yazi}")
        s.append("")
        s.append(f"Seçili ürünlerde <b>%{indirim}'ye varan</b> indirim")
        if etiket:
            s.append(etiket)
        s.append("")
        if kupon:
            s.append(f"🎟️ Kupon: <code>{kupon}</code>")
        if min_siparis:
            s.append(f"🛒 Min. {min_siparis} alışverişte geçerli")
        s.append(f"⏰ Sınırlı süre!  •  🕐 {zaman}")
    else:
        s.append(f"{baslik}  {yildiz}")
        s.append(f"📊 Fırsat Skoru: <b>{fs_skor}/10</b>  {fs_yildiz}")
        if etiket:
            s.append(etiket)
        s.append("")
        if urun:
            s.append(f"📌 <b>{urun}</b>")
        s.append(f"{kat_ikon} {kat_yazi}")
        s.append("")
        if eski_str and yeni_str:
            s.append(f"🏷️ Normal Fiyat:    <s>{eski_str} TL</s>")
            s.append(f"💰 İndirimli Fiyat: <b>{yeni_str} TL</b>")
        elif yeni_str:
            s.append(f"💰 Fiyat: <b>{yeni_str} TL</b>")
        s.append("")
        s.append(f"{m_emoji} <b>{magaza}</b>  •  🕐 {zaman}")
        if stok_kritik:
            s.append("⚠️ <b>Son stoklar!</b>")
        if sahte_indirim_mi(metin, indirim):
            s.append("⚠️ <i>Bu indirim oranı alışılmışın dışında, satın almadan araştırın.</i>")
        if kupon:
            s.append(f"🎟️ Kupon: <code>{kupon}</code>")
        if min_siparis:
            s.append(f"🛒 Min. {min_siparis} alımda geçerli")

    s.append("")
    s.append("──────────────────────")
    s.append(hashtagler)
    s.append(f"📢 @{kanal}")

    return "\n".join(s)
