"""
═══════════════════════════════════════════════════════════════════════
KUPON MESAJI AYRIŞTIRICI (v23.15)

Bazı kaynaklar "kupon kodu" formatında, tek mesajda BİRDEN FAZLA ürün +
kupon paylaşıyor:

  🔥Philips Espresso Makinesi
  ✅HAZIRAN1000 Kodu İle 23.899TL'ye Düşüyor - Piyasası 24.999TL
  🔻Salomon Ayakkabı HAZIRAN500 Kodu İle 6.492TL

Eski fiyat çıkarıcı bu mesajlarda ŞAŞIRYORDU: "500" (HAZIRAN500'den) veya
"1000" (10000/1000TL indirim açıklamasından) fiyat sanıyordu.

Bu modül her satırı "KOD + ürün + indirimli fiyat + piyasa" üçlüsü olarak
çözer, kupon açıklamalarındaki (10000/1000TL) sayıları fiyattan ayırır.
═══════════════════════════════════════════════════════════════════════
"""
import re

# Kupon kodu: en az 3 büyük harf + en az 2 rakam (HAZIRAN1000, INDIRIM500)
_KOD = re.compile(r"\b([A-ZÇĞİÖŞÜ]{3,}\d{2,})\b")
# "Kodu İle X TL'ye Düşüyor" / "Kodu İle X TL" → gerçek indirimli fiyat
_INDIRIMLI = re.compile(r"[Kk]odu\s+İle\s+([\d.,]+)\s*TL", re.I)
# "Piyasası X TL" / "Normal X TL" → eski/piyasa fiyatı
_PIYASA = re.compile(r"(?:[Pp]iyasası|[Nn]ormal(?:i)?|[Ee]ski)\s+(?:[Ff]iyat[ıi]?\s+)?([\d.,]+)\s*TL", re.I)
# "X/Y TL" indirim açıklaması → bu bir FİYAT DEĞİL (kupon mekaniği)
_INDIRIM_ACIK = re.compile(r"\d+\s*/\s*\d+\s*TL")


def _fiyat_to_float(s: str) -> float | None:
    """'23.899' veya '23.899,50' → 23899.0 / 23899.5"""
    if not s:
        return None
    s = s.strip()
    # Türkçe format: nokta=binlik, virgül=ondalık
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # Sadece nokta var — binlik ayracı mı ondalık mı?
        # "23.899" → binlik (3 hane sonra), "23.5" → ondalık
        parcalar = s.split(".")
        if len(parcalar) == 2 and len(parcalar[1]) == 3:
            s = s.replace(".", "")   # binlik
        # else: ondalık bırak
    try:
        return float(s)
    except ValueError:
        return None


def kupon_mesaji_mi(metin: str) -> bool:
    """Bu mesaj kupon-kodu formatında mı? (en az 1 kod + 'Kodu İle' kalıbı)"""
    if not metin:
        return False
    return bool(_KOD.search(metin) and _INDIRIMLI.search(metin))


def ayristir(metin: str) -> list[dict]:
    """Kupon mesajını ürünlere ayır.

    Döner: [{urun, kod, fiyat, eski_fiyat}, ...] — ilk eleman ANA üründür.
    Boş liste → kupon mesajı değil veya çözülemedi.
    """
    if not kupon_mesaji_mi(metin):
        return []

    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    urunler = []
    # İlk satır genelde ana ürün adı (🔥 ile başlar, kod/fiyat içermez)
    ana_urun_adi = None
    if satirlar:
        ilk = satirlar[0]
        if not _INDIRIMLI.search(ilk) and not _KOD.search(ilk):
            # Emoji temizle, ürün adı al
            ana_urun_adi = re.sub(r"^[^\wA-Za-zÇĞİÖŞÜ]+", "", ilk).strip()

    for satir in satirlar:
        # Kupon açıklama satırı (X/Y TL indirim) → atla, fiyat içermez
        temiz_satir = _INDIRIM_ACIK.sub("", satir)

        indirimli = _INDIRIMLI.search(temiz_satir)
        if not indirimli:
            continue  # bu satırda gerçek fiyat yok

        fiyat = _fiyat_to_float(indirimli.group(1))
        if not fiyat or fiyat < 10:
            continue

        kodlar = _KOD.findall(satir)
        kod = kodlar[0] if kodlar else None

        piyasa_m = _PIYASA.search(temiz_satir)
        eski = _fiyat_to_float(piyasa_m.group(1)) if piyasa_m else None

        # Bu satırın ürün adını çıkar: koddan ÖNCEki kısım, yoksa ana ürün
        satir_urun = None
        # "🔻Salomon Ayakkabı HAZIRAN500 Kodu İle" → "Salomon Ayakkabı"
        if kod:
            on = satir.split(kod)[0]
            on = re.sub(r"^[^\wA-Za-zÇĞİÖŞÜ]+", "", on).strip()
            # Çok kısa değilse (en az 2 kelime, marka adı) ürün adıdır
            if len(on.split()) >= 2 and not _INDIRIMLI.search(on):
                satir_urun = on

        urun_adi = satir_urun or ana_urun_adi
        if not urun_adi:
            continue

        urunler.append({
            "urun": urun_adi,
            "kod": kod,
            "fiyat": fiyat,
            "eski_fiyat": eski,
        })

    return urunler
