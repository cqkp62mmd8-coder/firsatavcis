"""
cok_kiraci/sablonlar.py — Müşteri-seçimli gönderi şablonları (Faz 3).

Her müşteri panelden bir şablon seçer; gönderim hattı o şablonla fırsatı
biçimler. Şablonlar havuzdaki fırsat sözlüğünden + affiliate-enjekte edilmiş
linkten düz metin üretir (Telegram URL'leri otomatik bağlar).

Yeni şablon eklemek: bir render fonksiyonu yazıp SABLONLAR'a ekle.
"""

# Mağaza kodu → görünen ad
_MAGAZA_AD = {
    "amazon": "Amazon",
    "trendyol": "Trendyol",
    "hepsiburada": "Hepsiburada",
    "n11": "n11",
    "teknosa": "Teknosa",
    "gratis": "Gratis",
    "boyner": "Boyner",
}


def _magaza_ad(magaza: str) -> str:
    m = (magaza or "").lower()
    return _MAGAZA_AD.get(m, m.title() if m else "")


def _fiyat(deger) -> str:
    """Türkçe biçim: 1.299,90"""
    if deger is None or deger == "":
        return ""
    try:
        s = f"{float(deger):,.2f}"            # 1,299.90
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(deger)


def _klasik(f: dict, link: str) -> str:
    baslik = f.get("baslik", "") or "Fırsat"
    fiyat = _fiyat(f.get("fiyat"))
    eski = _fiyat(f.get("eski_fiyat"))
    indirim = int(f.get("indirim", 0) or 0)
    magaza = _magaza_ad(f.get("magaza"))
    satirlar = [f"🔥 {baslik}", ""]
    fiyat_satir = f"💰 {fiyat} TL" if fiyat else "💰"
    if eski:
        fiyat_satir += f"  (eski {eski} TL)"
    satirlar.append(fiyat_satir)
    if indirim > 0:
        satirlar.append(f"📉 %{indirim} indirim")
    if magaza:
        satirlar.append(f"🏪 {magaza}")
    satirlar += ["", f"🛒 {link}"]
    return "\n".join(satirlar)


def _minimal(f: dict, link: str) -> str:
    baslik = f.get("baslik", "") or "Fırsat"
    fiyat = _fiyat(f.get("fiyat"))
    indirim = int(f.get("indirim", 0) or 0)
    orta = f"{fiyat} TL" if fiyat else ""
    if indirim > 0:
        orta = (orta + f" · %{indirim} indirim").strip(" ·")
    parcalar = [baslik]
    if orta:
        parcalar.append(orta)
    parcalar.append(link)
    return "\n".join(parcalar)


def _vurgulu(f: dict, link: str) -> str:
    baslik = f.get("baslik", "") or "Fırsat"
    fiyat = _fiyat(f.get("fiyat"))
    eski = _fiyat(f.get("eski_fiyat"))
    indirim = int(f.get("indirim", 0) or 0)
    magaza = _magaza_ad(f.get("magaza"))
    satirlar = ["⚡ KAÇMAZ FIRSAT ⚡", baslik, ""]
    if eski:
        satirlar.append(f"❌ {eski} TL")
    son = f"✅ {fiyat} TL" if fiyat else "✅"
    if indirim > 0:
        son += f"  (%{indirim} indirim!)"
    satirlar.append(son)
    if magaza:
        satirlar.append(f"🏪 {magaza}")
    satirlar += ["", f"👉 {link}"]
    return "\n".join(satirlar)


SABLONLAR = {
    "klasik": _klasik,
    "minimal": _minimal,
    "vurgulu": _vurgulu,
}


def sablon_listesi() -> list:
    """Panelde gösterilecek şablon kimlikleri."""
    return list(SABLONLAR.keys())


def render(sablon_id: str, firsat: dict, link: str) -> str:
    """Seçili şablonla fırsatı biçimle. Bilinmeyen kimlik → klasik."""
    fn = SABLONLAR.get(sablon_id) or SABLONLAR["klasik"]
    return fn(firsat, link)
