"""
Görsel işleme: kalite kontrolü + logo watermark + QR kod + boyut optimizasyonu.

v18 yenilikleri:
  • gorsel_kaliteli_mi() — çok küçük/bulanık görselleri reddet
  • renk_yogunlugu() — beyaz/tek-renk placeholder tespiti
  • boyut_ve_oran() — meta bilgileri
"""
import os
from io import BytesIO

from PIL import Image, ImageOps, ImageStat
try:
    import qrcode
    _QR_VAR = True
except ImportError:
    _QR_VAR = False

import config
from utils.log import log

# ── Sabitler ────────────────────────────────────────────────────
HEDEF_MAX_BOYUT = 1280
HEDEF_MIN_BOYUT = 800


def gorsel_kaliteli_mi(gorsel_bytes: bytes) -> tuple[bool, str]:
    """Görselin paylaşıma uygun kalitede olup olmadığını kontrol et.

    Reddedilenler:
      • Çok küçük (< config.MIN_GORSEL_BOYUT × MIN_GORSEL_BOYUT)
      • Tek renk / boş placeholder (varyans < 100)
      • Aşırı uzun/kısa oran (5:1'den daha eğri)

    Döner: (kaliteli_mi, sebep)
    """
    if not gorsel_bytes or len(gorsel_bytes) < 1000:
        return False, f"görsel çok küçük ({len(gorsel_bytes)} bayt)"
    try:
        img = Image.open(BytesIO(gorsel_bytes))
        w, h = img.size

        # 1) Boyut kontrolü
        if w < config.MIN_GORSEL_BOYUT or h < config.MIN_GORSEL_BOYUT:
            return False, f"boyut çok küçük ({w}×{h}, min {config.MIN_GORSEL_BOYUT})"

        # 2) Aşırı oran kontrolü (uzun bant gibi)
        oran = max(w, h) / max(min(w, h), 1)
        if oran > 5:
            return False, f"oran aşırı ({w}×{h}, oran {oran:.1f})"

        # 3) Renk varyansı — boş/tek renk placeholder kontrolü
        # Küçült ki hızlı olsun
        kucuk = img.convert("RGB").resize((100, 100), Image.LANCZOS)
        stat = ImageStat.Stat(kucuk)
        # Varyans her renk kanalı için, ortalama al
        ort_varyans = sum(stat.var) / 3
        if ort_varyans < 100:   # neredeyse tek renk
            return False, f"görsel boş/placeholder (varyans={ort_varyans:.0f})"

        return True, ""
    except Exception as e:
        return False, f"görsel açılamadı: {e}"


def boyut_ve_oran(gorsel_bytes: bytes) -> dict:
    """Görsel meta bilgileri — debug için."""
    try:
        img = Image.open(BytesIO(gorsel_bytes))
        w, h = img.size
        return {
            "genislik": w,
            "yukseklik": h,
            "format": img.format,
            "boyut_bayt": len(gorsel_bytes),
        }
    except Exception:
        return {}


def _optimize_boyut(img: Image.Image) -> Image.Image:
    """Görseli Telegram için ideal boyuta getirir.
    Çok büyükse küçült, küçükse dokunma."""
    w, h = img.size
    max_kenar = max(w, h)
    if max_kenar <= HEDEF_MAX_BOYUT:
        return img
    oran = HEDEF_MAX_BOYUT / max_kenar
    yeni_w = int(w * oran)
    yeni_h = int(h * oran)
    return img.resize((yeni_w, yeni_h), Image.LANCZOS)


def _qr_kod_uret(link: str, boyut: int) -> Image.Image | None:
    """Verilen link için QR kod görseli üretir."""
    if not link or not _QR_VAR:
        return None
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        return img.resize((boyut, boyut), Image.LANCZOS)
    except Exception as e:
        log("UYARI", f"QR kod üretilemedi: {e}")
        return None


def logo_ekle(gorsel_bytes: bytes, link: str | None = None,
              indirim: int = 0) -> bytes:
    """Ürün görseline:
    - Alt-orta: marka logosu (PNG, saydam)
    - Sol-alt: QR kod (link verilirse, beyaz arkaplanlı)
    - Sağ-üst: indirim rozeti (%X, indirim >= 20 ise) — v23.9
    Çıktı: PNG byte dizisi.
    Hata durumunda orijinali döndürür."""
    if not os.path.exists(config.LOGO_DOSYA):
        return gorsel_bytes
    try:
        urun = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        # ─ 0. Minimum boyut kontrolü (#F) ────────────────────
        w0, h0 = urun.size
        if w0 < config.MIN_GORSEL_BOYUT or h0 < config.MIN_GORSEL_BOYUT:
            log("UYARI", f"Görsel çok küçük ({w0}x{h0}), logo eklenmedi")
            return gorsel_bytes
        # ─ 1. Boyut optimizasyonu ────────────────────────────
        urun = _optimize_boyut(urun)
        w, h = urun.size

        # ─ 2. Logo (alt-orta) ────────────────────────────────
        logo = Image.open(config.LOGO_DOSYA).convert("RGBA")
        lw, lh = logo.size
        hedef_w = max(50, min(120, int(w * 0.12)))
        hedef_h = int(hedef_w * lh / lw)
        logo_r  = logo.resize((hedef_w, hedef_h), Image.LANCZOS)
        x = (w - hedef_w) // 2
        y = h - hedef_h - 14
        urun.paste(logo_r, (max(0, x), max(0, y)), logo_r)

        # ─ 3. QR kod (sol-alt) ───────────────────────────────
        if link and config.QR_KOD_AKTIF:
            qr_boyut = max(80, min(160, int(w * 0.14)))
            qr_img = _qr_kod_uret(link, qr_boyut)
            if qr_img:
                # Beyaz çerçeveli kart üzerine yerleştir
                pad = 6
                kart_w = qr_boyut + pad * 2
                kart_h = qr_boyut + pad * 2
                kart = Image.new("RGBA", (kart_w, kart_h), (255, 255, 255, 230))
                kart.paste(qr_img, (pad, pad), qr_img)
                qx = 12
                qy = h - kart_h - 12
                urun.paste(kart, (qx, qy), kart)

        # ─ 4. İndirim rozeti — v23.17'de KALDIRILDI (kullanıcı gereksiz buldu) ─
        # Eskiden sağ-üst köşeye "%X" rozeti basılıyordu (v23.9). Artık yok.

        cikti = BytesIO()
        urun.save(cikti, format="PNG", optimize=True)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", f"Logo/QR ekleme hatası: {e}")
        return gorsel_bytes
