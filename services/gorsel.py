"""Logo watermark: ürün görselinin alt ortasına tek logo ekler."""
import os
from io import BytesIO

from PIL import Image

import config
from utils.log import log


def logo_ekle(gorsel_bytes: bytes) -> bytes:
    """Görselin alt ortasına tek logo yapıştırır. Hata durumunda orijinali döndürür."""
    if not os.path.exists(config.LOGO_DOSYA):
        return gorsel_bytes
    try:
        urun = Image.open(BytesIO(gorsel_bytes)).convert("RGBA")
        w, h = urun.size
        logo = Image.open(config.LOGO_DOSYA).convert("RGBA")
        _, lh = logo.size

        # Logo: alt-orta — genişliğin %12'si, max 120px
        hedef_w = max(50, min(120, int(w * 0.12)))
        hedef_h = int(hedef_w * lh / logo.size[0])
        logo_r  = logo.resize((hedef_w, hedef_h), Image.LANCZOS)

        x = (w - hedef_w) // 2          # yatay ortalama
        y = h - hedef_h - 14            # alttan 14px boşluk
        urun.paste(logo_r, (max(0, x), max(0, y)), logo_r)

        cikti = BytesIO()
        urun.convert("RGB").save(cikti, format="JPEG", quality=92)
        cikti.seek(0)
        return cikti.read()
    except Exception as e:
        log("UYARI", f"Logo ekleme hatası: {e}")
        return gorsel_bytes
