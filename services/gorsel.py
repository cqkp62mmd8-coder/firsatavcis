"""
Görsel işleme: logo watermark + QR kod + boyut optimizasyonu.
"""
import os
from io import BytesIO

from PIL import Image, ImageOps
try:
    import qrcode
    _QR_VAR = True
except ImportError:
    _QR_VAR = False

import config
from utils.log import log

# ── Sabitler ────────────────────────────────────────────────────
HEDEF_MAX_BOYUT = 1280   # Telegram için ideal max boyut (px) — sıkıştırma azalır
HEDEF_MIN_BOYUT = 800    # Bu altındaysa upscale yapma, küçük kalsın


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


def logo_ekle(gorsel_bytes: bytes, link: str | None = None) -> bytes:
    """Ürün görseline:
    - Alt-orta: marka logosu (PNG, saydam)
    - Sol-alt: QR kod (link verilirse, beyaz arkaplanlı)
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

        cikti = BytesIO()
        urun.save(cikti, format="PNG", optimize=True)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", f"Logo/QR ekleme hatası: {e}")
        return gorsel_bytes
