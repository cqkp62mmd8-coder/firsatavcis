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
# v23.20 — "X TL'ye Düştü/Düşüyor" → kodsuz indirimli fiyat (Güral formatı)
_DUSTU = re.compile(r"([\d.,]+)\s*TL['\u2019]?\s*ye\s+[Dd]üş", re.I)
# "Piyasası X TL" / "Normal X TL" → eski/piyasa fiyatı
_PIYASA = re.compile(r"(?:[Pp]iyasası|[Nn]ormal(?:i)?|[Ee]ski)\s+(?:[Ff]iyat[ıi]?\s+)?([\d.,]+)\s*TL", re.I)
# "X/Y TL" indirim açıklaması → bu bir FİYAT DEĞİL (kupon mekaniği)
_INDIRIM_ACIK = re.compile(r"\d+\s*/\s*\d+\s*TL")
# Ürün başlığı işareti (🔥🔻 ile başlayan satır = yeni ürün)
_BASLIK = re.compile(r"^[🔥🔻🆕⚡🎯]")


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
    """Bu mesaj kupon/çoklu-fırsat formatında mı?
    (kod+'Kodu İle' VEYA 'X TL'ye Düştü' kalıbı)"""
    if not metin:
        return False
    if _KOD.search(metin) and _INDIRIMLI.search(metin):
        return True
    # v23.20 — "X TL'ye Düştü - Piyasası Y TL" formatı (kodsuz, Güral)
    if _DUSTU.search(metin) and _PIYASA.search(metin):
        return True
    return False


def ayristir(metin: str) -> list[dict]:
    """Kupon/çoklu-fırsat mesajını ürünlere ayır.

    Döner: [{urun, kod, fiyat, eski_fiyat}, ...] — ilk eleman ANA üründür.
    Boş liste → uygun format değil veya çözülemedi.
    """
    if not kupon_mesaji_mi(metin):
        return []

    satirlar = [s.strip() for s in metin.split("\n") if s.strip()]
    urunler = []

    # "Son görülen başlık" — kodsuz fiyat satırı için ürün adını buradan al.
    # Format: 🔥ÜrünAdı \n (boş) \n ✅1.599TL'ye Düştü ...
    son_baslik = None

    def _baslik_temizle(s):
        return re.sub(r"^[^\wA-Za-zÇĞİÖŞÜ]+", "", s).strip()

    for satir in satirlar:
        # Kupon açıklama satırı (X/Y TL) → fiyat kısmını maskele
        temiz_satir = _INDIRIM_ACIK.sub("", satir)

        # Bu satır bir ürün BAŞLIĞI mı? (🔥🔻 ile başlıyor)
        baslik_mi = bool(_BASLIK.match(satir))

        # Fiyat var mı? (Kodu İle X / X TL'ye Düştü)
        indirimli = _INDIRIMLI.search(temiz_satir) or _DUSTU.search(temiz_satir)
        fiyat = _fiyat_to_float(indirimli.group(1)) if indirimli else None

        # Başlık satırında inline fiyat olabilir (🔻Flormar ... 99TL) — onu da dene
        if not fiyat and baslik_mi:
            inline = re.search(r"([\d.,]+)\s*TL", temiz_satir)
            if inline:
                fiyat = _fiyat_to_float(inline.group(1))

        # Başlık satırı ama HİÇ fiyat yok → ürün adı olarak hatırla, sonraki
        # fiyat satırına bağla (🔥Güral \n ✅1.599TL'ye Düştü)
        if baslik_mi and not fiyat:
            son_baslik = _baslik_temizle(satir)
            continue

        if not fiyat or fiyat < 10:
            continue

        kodlar = _KOD.findall(satir)
        kod = kodlar[0] if kodlar else None

        piyasa_m = _PIYASA.search(temiz_satir)
        eski = _fiyat_to_float(piyasa_m.group(1)) if piyasa_m else None

        # Ürün adını belirle (öncelik sırası):
        satir_urun = None
        if kod:
            # "🔻Salomon Ayakkabı HAZIRAN500 Kodu İle" → koddan öncesi
            on = _baslik_temizle(satir.split(kod)[0])
            if len(on.split()) >= 2 and not _INDIRIMLI.search(on):
                satir_urun = on
        elif baslik_mi:
            # Aynı satırda başlık+fiyat (Flormar): fiyat/TL kısmını at, adı al
            on = _baslik_temizle(satir)
            on = re.sub(r"\s*[\d.,]+\s*TL.*$", "", on, flags=re.I).strip()
            on = _DUSTU.sub("", on).strip()
            if len(on.split()) >= 2:
                satir_urun = on

        # Kodsuz fiyat satırı (✅1.599TL'ye Düştü) → son başlığı kullan
        urun_adi = satir_urun or son_baslik
        if not urun_adi:
            continue
        son_baslik = None  # kullanıldı, sıfırla

        urunler.append({
            "urun": urun_adi,
            "kod": kod,
            "fiyat": fiyat,
            "eski_fiyat": eski,
        })

    return urunler
