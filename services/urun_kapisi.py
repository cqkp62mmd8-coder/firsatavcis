"""
═══════════════════════════════════════════════════════════════════════
ÜRÜN ADI KAPISI (v23.0 — TEK MERKEZİ DOĞRULAMA NOKTASI)

SORUN: Ürün adı 4 farklı bağımsız kaynaktan gelebiliyordu:
  1. ML model (urun_taniyici)
  2. Yapısal çıkarım (regex)
  3. Gemini
  4. Web scrape (og:title)
Her biri kendi başına buyruktu, doğrulama dağınıktı. "Amazon" bir
kaynaktan sızıyordu çünkü o kaynak _urun_adi_makul'a uğramıyordu.

ÇÖZÜM (araştırılmış "validation gateway" deseni):
  Ürün adı HANGİ kaynaktan gelirse gelsin, kanala çıkmadan önce
  MUTLAKA bu tek fonksiyondan (gecerli_urun_adi) geçer.
  Tek nokta = tek yerde yamalanır, bypass edilemez.

TEMEL İLKE:
  Bir ürün adı geçerlidir ANCAK VE ANCAK:
   • mağaza adı + jenerik kelimelerden FAZLASINI içeriyorsa
   • yani en az bir "ayırt edici" kelime (marka/model/ürün tipi) varsa
  "Amazon" → ayırt edici kelime yok → REDDEDİLİR
  "Amazon Echo Dot" → "echo", "dot" ayırt edici → KABUL
═══════════════════════════════════════════════════════════════════════
"""
import re

# Mağaza adları — ürün adının ayırt edici kısmı OLAMAZ
_MAGAZALAR = {
    "amazon", "trendyol", "hepsiburada", "n11", "mediamarkt", "media",
    "markt", "teknosa", "vatan", "gittigidiyor", "morhipo", "boyner",
    "lcwaikiki", "lcw", "defacto", "carrefoursa", "carrefour", "a101",
    "bim", "migros", "şok", "sok", "ikea", "decathlon", "gratis",
    "watsons", "rossmann", "flo", "koton", "mavi", "beymen",
}

# Jenerik / bağlam kelimeleri — ayırt edici DEĞİL
_JENERIK = {
    "tr", "türkiye", "turkiye", "com", "store", "mağaza", "magaza",
    "official", "resmi", "shop", "ürün", "urun", "ürünleri", "urunleri",
    "ürünler", "urunler", "ürünlerde", "ürünlerinde", "seri", "serisi",
    # Fiyat/kampanya bağlamı
    "indirim", "indirimli", "fiyat", "fiyatı", "normal", "kampanya",
    "fırsat", "fırsatı", "tl", "lira", "ucuz", "ücretsiz", "kargo",
    "sepette", "sepet", "kupon", "kod", "şimdi", "hemen", "son", "adet",
    "var", "yok", "stokta", "stok", "ek", "varan", "kadar", "özel",
    "tüm", "tum", "seçili", "secili", "çeşitli", "binlerce",
    # Kategori adları (tek başına ürün değil)
    "elektronik", "giyim", "ev", "kozmetik", "spor", "kitap", "oyuncak",
    "mobilya", "bahçe", "otomotiv", "market", "bilgisayar", "telefon",
    "aksesuar", "moda", "anne", "bebek", "yapı", "gıda", "gida",
    # Bağlaçlar / dolgu
    "ve", "ile", "için", "the", "bir", "yeni", "set", "modern",
    "klasik", "klasikler", "büyük", "küçük", "mini", "maxi",
    # Pazarlama sıfatları (tek başına ürün değil)
    "süper", "super", "harika", "muhteşem", "muhtesem", "inanılmaz",
    "inanilmaz", "efsane", "kaçırılmayacak", "kacirilmayacak", "müthiş",
    "muthis", "şahane", "sahane", "bomba", "dev", "mega",
}

# Ürün-benzeri jenerik kelimeler — tek başına yetmez ama varsa zayıf sinyal
# (bunlar ayırt edici sayılmaz; gerçek marka/model gerekir)


def _tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def _kelimeler(ad: str) -> list[str]:
    """Ürün adını anlamlı kelimelere ayır (noktalama temizlenmiş)."""
    ham = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", ad)
    return [_tr_lower(k) for k in ham if k]


def ayirt_edici_kelimeler(ad: str) -> list[str]:
    """Ürün adındaki AYIRT EDİCİ kelimeleri döndür.
    Ayırt edici = mağaza adı değil, jenerik değil, salt rakam değil,
    en az 2 harf içeren gerçek bir kelime (marka/model/ürün tipi)."""
    sonuc = []
    for k in _kelimeler(ad):
        if k in _MAGAZALAR or k in _JENERIK:
            continue
        if k.isdigit():           # salt rakam (fiyat/kod parçası)
            continue
        if len(k) < 2:
            continue
        # En az 2 harf içermeli (sadece "x1" gibi değil)
        harf = sum(1 for c in k if c.isalpha())
        if harf < 2:
            continue
        sonuc.append(k)
    return sonuc


def gecerli_urun_adi(aday: str | None, kaynak_metin: str = "") -> str | None:
    """★ TEK MERKEZİ KAPI ★
    Bir ürün adı adayını doğrula. Geçerliyse temizlenmiş adı, değilse None döner.

    Bir ad geçerlidir ANCAK en az 1 ayırt edici kelime içeriyorsa
    (mağaza adı + jenerik kelimelerden fazlası). Böylece "Amazon",
    "Amazon TR", "İndirimli Fiyat", "Tüm elektronik" gibi adlar — hangi
    kaynaktan (ML/Gemini/scrape/yapısal) gelirse gelsin — reddedilir.
    """
    if not aday or not isinstance(aday, str):
        return None
    aday = aday.strip()
    if len(aday) < 3:
        return None

    # v23.1 — Kupon/kod kalıbı: "Kupon: X", "Kod: X", "İndirim kodu: X" → ürün değil
    if re.match(r"^\s*(kupon|kod|indirim\s*kodu)\s*[:=]", aday, re.I):
        return None

    ayirt = ayirt_edici_kelimeler(aday)
    if not ayirt:
        # Hiç ayırt edici kelime yok → mağaza/jenerik çöpü
        return None

    # v23.1 — Anlamsız tek-tip harf dizisi (AAAA, XXXX) → ürün değil
    for k in ayirt:
        harfler = [c for c in k if c.isalpha()]
        if len(k) >= 4 and harfler and len(set(harfler)) == 1:
            return None

    # En az 1 ayırt edici kelime + toplam anlamlı uzunluk
    toplam_ayirt_harf = sum(len(k) for k in ayirt)
    if toplam_ayirt_harf < 3:
        return None

    return aday


def gecerli_mi(aday: str | None) -> bool:
    """Sadece geçerlilik kontrolü (bool). gecerli_urun_adi'nin kısa hali."""
    return gecerli_urun_adi(aday) is not None
