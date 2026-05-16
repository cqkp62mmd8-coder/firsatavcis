"""Logo watermark: ürün görselinin üzerine logo ekler."""
import os
from io import BytesIO

from PIL import Image

import config
from utils.log import log


def logo_ekle(gorsel_bytes: bytes) -> bytes:
    """Görsele iki konumda logo yapıştırır. Hata durumunda orijinali döndürür."""
    if not os.path.exists(config.LOGO_DOSYA):
        return gorsel_bytes
    try:
        urun = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun.size
        logo = Image.open(config.LOGO_DOSYA).convert("RGBA")
        lw, lh = logo.size
        pad = 10

        # Sağ alt – büyük (%30 genişlik)
        bw = max(100, min(220, int(w * 0.30)))
        bh = int(bw * lh / lw)
        b_logo = logo.resize((bw, bh), Image.LANCZOS)
        urun.paste(b_logo, (max(0, w - bw - pad), max(0, h - bh - pad)), b_logo)

        # Sol alt – küçük (%15 genişlik, rakip logo üzeri)
        kw = max(60, min(120, int(w * 0.15)))
        kh = int(kw * lh / lw)
        k_logo = logo.resize((kw, kh), Image.LANCZOS)
        urun.paste(k_logo, (pad, h - kh - pad), k_logo)

        cikti = BytesIO()
        urun.convert("RGB").save(cikti, format="JPEG", quality=92)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", f"Logo ekleme hatası: {e}")
        return gorsel_bytes
