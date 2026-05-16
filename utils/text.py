import re
import hashlib
import unicodedata


def emoji_temizle(metin: str) -> str:
    if not metin:
        return ""
    return "".join(
        k for k in metin
        if unicodedata.category(k) not in ("So", "Sm", "Sk")
    ).strip()


def markdown_temizle(metin: str) -> str:
    if not metin:
        return metin
    metin = re.sub(r'[*]{1,3}([^*]+)[*]{1,3}', r'\1', metin)
    metin = re.sub(r'[_]{1,2}([^_]+)[_]{1,2}', r'\1', metin)
    metin = re.sub(r'[`]([^`]+)[`]', r'\1', metin)
    metin = re.sub(r'[~]{1,2}([^~]+)[~]{1,2}', r'\1', metin)
    metin = re.sub(r'[|]{2}([^|]+)[|]{2}', r'\1', metin)
    return metin


def benzerlik_anahtari(metin: str, urun_adi_bul_fn, fiyat_bul_fn) -> str:
    """Duplikat tespiti için tekrarlanabilir hash üretir."""
    urun = urun_adi_bul_fn(metin) or ''
    _, yeni, _, _ = fiyat_bul_fn(metin)
    yeni = yeni or ''
    ham = (urun + yeni).lower().replace(' ', '')
    if len(ham) > 5:
        return hashlib.md5(ham.encode()).hexdigest()
    temiz = re.sub(r'\s+', ' ', (metin or '').strip().lower())
    return hashlib.md5(temiz.encode()).hexdigest()
