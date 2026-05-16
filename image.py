from io import BytesIO
from PIL import Image
from config.settings import LOGO_DOSYA
from utils.logger import log
import os


def logo_ekle(gorsel_bytes: bytes) -> bytes:
    """Ürün görselinın üzerine logo watermark ekler."""
    try:
        if not os.path.exists(LOGO_DOSYA):
            return gorsel_bytes

        urun_img = Image.open(BytesIO(gorsel_bytes)).convert('RGBA')
        w, h = urun_img.size
        logo_ham = Image.open(LOGO_DOSYA).convert('RGBA')
        lw, lh = logo_ham.size
        bosluk = 10

        # Sağ alt – büyük logo (%30 genişlik)
        hedef_w = max(100, min(220, int(w * 0.30)))
        hedef_h = int(hedef_w * (lh / lw))
        logo_buyuk = logo_ham.resize((hedef_w, hedef_h), Image.LANCZOS)
        x = max(0, w - hedef_w - bosluk)
        y = max(0, h - hedef_h - bosluk)
        urun_img.paste(logo_buyuk, (x, y), logo_buyuk)

        # Sol alt – küçük logo (rakip logo üzeri için)
        kucuk_w = max(60, min(120, int(w * 0.15)))
        kucuk_h = int(kucuk_w * (lh / lw))
        logo_kucuk = logo_ham.resize((kucuk_w, kucuk_h), Image.LANCZOS)
        urun_img.paste(logo_kucuk, (bosluk, h - kucuk_h - bosluk), logo_kucuk)

        cikti = BytesIO()
        urun_img.convert('RGB').save(cikti, format='JPEG', quality=92)
        cikti.seek(0)
        return cikti.read()

    except Exception as e:
        log('UYARI', f'Logo ekleme hatası: {e}')
        return gorsel_bytes
