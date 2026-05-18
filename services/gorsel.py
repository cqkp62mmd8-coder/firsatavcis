"""Logo watermark: ürün görselinin alt ortasına PNG logo yapıştırır."""
import os
from io import BytesIO

from PIL import Image

import config
from utils.log import log


def logo_ekle(gorsel_bytes: bytes) -> bytes:
    """Ürün görselinin alt ortasına PNG logosu (saydam) yapıştırır.
    Çıktı PNG olarak döner (saydamlık korunur).
    Hata durumunda orijinali döndürür."""
    if not os.path.exists(config.LOGO_DOSYA):
        return gorsel_bytes
    try:
        urun = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun.size
        logo = Image.open(config.LOGO_DOSYA).convert("RGBA")
        lw, lh = logo.size

        # Logo: alt-orta — genişliğin %12'si, max 120px
        hedef_w = max(50, min(120, int(w * 0.12)))
        hedef_h = int(hedef_w * lh / lw)
        logo_r  = logo.resize((hedef_w, hedef_h), Image.LANCZOS)

        x = (w - hedef_w) // 2
        y = h - hedef_h - 14
        urun.paste(logo_r, (max(0, x), max(0, y)), logo_r)

        cikti = BytesIO()
        # PNG olarak kaydet — logonun saydamlığı korunur
        urun.save(cikti, format="PNG", optimize=True)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", f"Logo ekleme hatası: {e}")
        return gorsel_bytes
