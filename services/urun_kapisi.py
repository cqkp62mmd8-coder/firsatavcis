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
    "ürünler", "urunler", "ürünlerde", "ürünlerinde",
    # Fiyat/kampanya bağlamı
    "indirim", "indirimli", "fiyat", "fiyatı", "normal", "kampanya",
    "fırsat", "fırsatı", "tl", "lira", "ucuz", "ücretsiz", "kargo",
    "sepette", "sepet", "kupon", "kod", "şimdi", "hemen", "son", "adet",
    "var", "yok", "stokta", "stok", "stoklar", "stoklarla", "ek", "varan", "kadar", "özel",
    "tüm", "tum", "seçili", "secili", "çeşitli", "binlerce",
    # Kategori adları (tek başına ürün değil)
    "elektronik", "giyim", "ev", "kozmetik", "spor", "kitap", "oyuncak",
    "alışveriş", "alisveris",  # v23.30 — "Alışveriş fırsatı"/"Alışveriş" sahte adı
    "mobilya", "bahçe", "otomotiv", "market", "bilgisayar", "telefon",
    "aksesuar", "moda", "anne", "bebek", "yapı", "gıda", "gida",
    # Bağlaçlar / dolgu
    "ve", "ile", "için", "the", "bir", "yeni", "set",
    "büyük", "küçük", "mini", "maxi",
    # Pazarlama sıfatları (tek başına ürün değil)
    "süper", "super", "harika", "muhteşem", "muhtesem", "inanılmaz",
    "inanilmaz", "efsane", "kaçırılmayacak", "kacirilmayacak", "müthiş",
    "muthis", "şahane", "sahane", "bomba", "dev", "mega",
    # v23.27 — Duyuru/kampanya fiilleri ve çağrıları (ürün adı DEĞİL)
    "başladı", "basladi", "geldi", "kaçırma", "kacirma", "kaçmaz", "kacmaz",
    "eriyor", "tükeniyor", "tukeniyor", "bitiyor", "acele", "fırsatı",
    "firsati", "firsat", "duyuru", "müjde", "mujde", "indi", "düştü",
    "dustu", "yakala", "başvur", "basvur", "kazan", "katıl", "katil",
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
    # v23.13 — AMA rakam içeren kelimeler (125mm, 20ll, 2tt) ölçü/model
    # kodudur, "mm"/"ll" tek-tip harf olsa bile reddedilmemeli.
    for k in ayirt:
        if any(c.isdigit() for c in k):
            continue  # rakam içeriyor → ölçü/model kodu, atla
        harfler = [c for c in k if c.isalpha()]
        if len(k) >= 4 and harfler and len(set(harfler)) == 1:
            return None

    # En az 1 ayırt edici kelime + toplam anlamlı uzunluk
    toplam_ayirt_harf = sum(len(k) for k in ayirt)
    if toplam_ayirt_harf < 3:
        return None

    # v23.7 — ÇÖP KUYRUK TEMİZLEME: Gemini bazen ürün adına mesajdaki çöp
    # satırları yapıştırıyor: "Üç Köşeli Dünya İndirimli Fiyat var Amazon TR".
    # Sondaki mağaza/jenerik kelime dizisini kes (gerçek ürün kelimesine kadar).
    kelimeler_ham = aday.split()
    # Her kelimenin "ayırt edici mi" haritası
    son_gercek_idx = -1
    for i, kh in enumerate(kelimeler_ham):
        k = _tr_lower(re.sub(r"[^\w]", "", kh))
        if not k or k in _MAGAZALAR or k in _JENERIK:
            continue
        harf = sum(1 for c in k if c.isalpha())
        rakam = sum(1 for c in k if c.isdigit())
        # Gerçek kelime sayılır: ya 2+ harf, YA DA harf+rakam karışımı
        # (model kodu: "S24", "M3", "A52", "GSR12V" gibi)
        if harf >= 2 or (harf >= 1 and rakam >= 1):
            son_gercek_idx = i
    # Son gerçek kelimeden sonrası çöp kuyruksa kes
    if son_gercek_idx >= 0 and son_gercek_idx < len(kelimeler_ham) - 1:
        temiz = " ".join(kelimeler_ham[:son_gercek_idx + 1]).strip()
        # Noktalama temizliği (sonda kalan : , - gibi)
        temiz = re.sub(r"[\s:;,\-]+$", "", temiz)
        if len(temiz) >= 3:
            aday = temiz

    return aday


def gecerli_mi(aday: str | None) -> bool:
    """Sadece geçerlilik kontrolü (bool). gecerli_urun_adi'nin kısa hali."""
    return gecerli_urun_adi(aday) is not None


# ═══════════════════════════════════════════════════════════════════════
# TANITIM (AÇIKLAMA) DOĞRULAMA — v23.2
# Gemini bazen ürünle alakasız açıklama uyduruyor:
#   "Otogizoshi" (kitap) → "aracınız için pratik bir çözüm"
# Açıklama, ürün adının yanlış yorumuna dayanıyorsa atılmalı.
# ═══════════════════════════════════════════════════════════════════════

# Kategori-spesifik kelimeler — açıklama bu kelimeleri içeriyorsa ama ürün
# o kategoride değilse, açıklama uydurma demektir.
_KATEGORI_IPUCU = {
    "otomotiv": {"araç", "araba", "oto", "otomobil", "motor", "lastik",
                 "araçlar", "sürüş", "direksiyon", "fren", "motosiklet"},
    "giyim": {"giyim", "kıyafet", "elbise", "tişört", "pantolon", "ayakkabı",
              "mont", "ceket", "giyilebilir", "kombin", "şık görünüm",
              "sneaker", "bot", "çorap", "şort", "etek", "gömlek"},
    "kozmetik": {"cilt", "makyaj", "güzellik", "bakım", "krem", "parfüm",
                 "saç", "ten", "nemlendirici", "ruj", "fondöten", "maskara"},
    "elektronik": {"şarj", "pil", "batarya", "ekran", "bağlantı", "kablosuz",
                   "teknoloji", "cihaz", "elektronik", "telefon", "kulaklık",
                   "bilgisayar", "tablet", "laptop", "kamera", "hoparlör"},
    "kitap": {"oku", "okuma", "sayfa", "yazar", "roman", "hikaye", "kitap",
              "edebiyat", "eser"},
    "ev": {"mutfak", "yemek", "ev", "temizlik", "dekorasyon"},
}


def tanitim_gecerli(tanitim: str | None, urun_adi: str = "",
                    kategori: str = "") -> str | None:
    """Gemini'nin ürün açıklamasını doğrula. Geçerliyse döndürür, değilse None.

    REDDETME KOŞULLARI:
     • Açıklama bir kategori ipucu içeriyor ama ürün o kategoride DEĞİL
       (örn. "aracınız için" diyor ama ürün otomotiv değil → uydurma)
     • Çok kısa / anlamsız
    """
    if not tanitim or not isinstance(tanitim, str):
        return None
    tanitim = tanitim.strip()
    if len(tanitim) < 10:
        return None

    t_low = _tr_lower(tanitim)
    kat_low = _tr_lower(kategori) if kategori else ""
    urun_low = _tr_lower(urun_adi) if urun_adi else ""

    # Açıklama doğrulaması için NET kategori kelimeleri (kısa/tuzak olan
    # "oto" hariç — o "Otogizoshi" gibi adlarda yanlış tetikleniyor).
    _TANITIM_IPUCU = {
        "otomotiv": {"araç", "aracınız", "aracın", "araba", "arabanız",
                     "otomobil", "sürüş", "direksiyon", "motosiklet", "lastik"},
        "giyim": {"giyim", "kıyafet", "elbise", "tişört", "pantolon",
                  "kombin", "şıklık", "gardırop"},
        "kozmetik": {"cilt", "makyaj", "güzellik", "nemlendir", "parfüm", "ten"},
        "elektronik": {"şarj", "batarya", "ekran", "gürültü engel",
                       "bağlantı", "teknoloji"},
        "kitap": {"oku", "okuma", "sayfa", "yazar", "roman", "edebiyat"},
    }
    for kat_adi, ipuclari in _TANITIM_IPUCU.items():
        if kat_adi == kat_low:
            continue
        eslesme = [ip for ip in ipuclari if ip in t_low]
        if not eslesme:
            continue
        urun_destekli = any(ip in urun_low for ip in ipuclari)
        if urun_destekli:
            continue
        if kat_low != kat_adi:
            return None

    return tanitim


# ═══════════════════════════════════════════════════════════════════════
# ÜRÜN ADI SEÇİCİ — v23.8
# Gemini ile saf-Python farklı ürün adı verince hangisi doğru?
# Gemini bazen uzun ürün adının ORTASINDAN kopuk bir parça veriyor:
#   "Apple A16 çipli iPad: ... Tüm Gün Süren Pil Ömrü — Gümüş Rengi"
#   → Gemini "Gün Süren Pil Ömrü Gümüş Rengi Satıcı Amazon Depo" (yanlış!)
# Ürün adı HER ZAMAN mesajın başında olur. Başta hangisi varsa o doğru.
# ═══════════════════════════════════════════════════════════════════════

def _ilk_kelimeler(metin: str, n: int = 3) -> list:
    """Metnin ilk n anlamlı kelimesi (küçük harf, noktalama temiz)."""
    kelimeler = _kelimeler(metin)
    return kelimeler[:n]


def en_iyi_urun_adi(gemini_ad: str | None, python_ad: str | None,
                    kaynak_metin: str = "") -> str | None:
    """Gemini ve saf-Python ürün adlarından doğru olanı seç.

    Strateji:
     1. İkisinden biri yoksa → diğerini döndür
     2. Aynıysa → o
     3. FARKLIYSA: Ürün adı mesajın BAŞINDA olur. Kaynak metnin başındaki
        kelimelerle hangisi örtüşüyorsa o doğru. Gemini ortadan kopuk parça
        verdiyse, mesaj başıyla örtüşmez → saf-Python kazanır.
    """
    g = (gemini_ad or "").strip()
    p = (python_ad or "").strip()
    if not g:
        return p or None
    if not p:
        return g or None
    if _tr_lower(g) == _tr_lower(p):
        return g

    if not kaynak_metin:
        return g  # kaynak yoksa eski davranış (Gemini öncelik)

    # Kaynak metnin ilk 3 anlamlı kelimesi
    bas_kelimeler = set(_ilk_kelimeler(kaynak_metin, 3))
    if not bas_kelimeler:
        return g

    g_bas = set(_ilk_kelimeler(g, 3))
    p_bas = set(_ilk_kelimeler(p, 3))

    g_ortusme = len(bas_kelimeler & g_bas)
    p_ortusme = len(bas_kelimeler & p_bas)

    # Mesajın başıyla daha çok örtüşen ad doğrudur
    if p_ortusme > g_ortusme:
        return p   # saf-Python mesaj başıyla örtüşüyor, Gemini kopuk parça
    return g


# ═══════════════════════════════════════════════════════════════════════
# ÜRÜN ADI GÜZELLEŞTİRME — v23.9
# Uzun teknik adları okunabilir hale getirir. Aboneler 70 karakterlik
# "Apple iPad: 11 inç Liquid Retina, 128 GB, Wi-Fi 6, 12 MP..." okumaz.
# Marka + model + en kritik özellik tut, teknik detayı kes.
# ═══════════════════════════════════════════════════════════════════════

# Atılabilir teknik gürültü (kelime bazlı — ürün kimliğini değiştirmez)
_GURULTU_KELIME = {
    # Bağlantı/teknik
    "wi-fi", "wifi", "bluetooth", "5g", "4g", "lte", "nfc",
    # Garanti/satıcı notları
    "garantili", "garanti", "türkiye", "turkiye", "ithalatçı", "distribütör",
    "resmi", "official", "orijinal", "original",
    # Kamera detayı
    "mp", "megapiksel", "ön", "arka", "kamera/12",
    # Ekran teknik
    "liquid", "retina", "amoled", "oled", "ips", "led",
}

# Bu kelimelerden SONRASI genelde teknik detay (kesilebilir)
_KESME_NOKTASI = {
    "wi-fi", "wifi", "ön", "arka", "touch", "face", "sensiq",
    "garantili", "garanti", "ithalatçı",
}


def guzellestir(ad: str | None, max_kelime: int = 9) -> str | None:
    """Ürün adını GÜVENLİ şekilde sadeleştir.

    v23.16 — ÖNEMLİ DEĞİŞİKLİK: Artık kelimeleri YENİDEN SEÇMİYOR/SIRALAMIYOR.
    Eski sürüm "Philips...Espresso Makinesi" → "...Espresso" gibi ürünün
    türünü (Makinesi, Taşlama) kesip yazım hataları yapıyordu.

    Yeni strateji — sadece GÜVENLİ işlemler, hiçbir kelimeyi ortadan atmaz:
     1. Parantez içini at: "(Samsung Türkiye Garantili)" → çıkar
     2. Belirgin teknik kuyruğu kes (virgülden sonra "Wi-Fi 6, 12 MP..." gibi)
     3. Hâlâ çok uzunsa kelime sınırında kes (ortadan kelime ATMAZ, sona "…" koyar)

    Sonuç her zaman baştan başlar, kelimeler bozulmaz, sıra korunur.
    """
    if not ad or not isinstance(ad, str):
        return ad
    ad = ad.strip()

    # 1. Parantez içini at (garanti notu vb.)
    ad = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*", " ", ad).strip()
    ad = re.sub(r"\s+", " ", ad)

    # 2. Belirgin teknik kuyruğu kes: ilk virgülden sonrası genelde teknik
    #    detaydır AMA sadece virgülden ÖNCEki kısım yeterince uzunsa (ürün
    #    adı + en az bir özellik içeriyorsa). Aksi halde dokunma.
    if "," in ad:
        on = ad.split(",")[0].strip()
        if len(on.split()) >= 3:   # virgül öncesi makul bir ürün adı
            ad = on

    # 3. İki nokta sonrası teknik detayı da kes (aynı güvenli mantık)
    if ":" in ad:
        on = ad.split(":")[0].strip()
        if len(on.split()) >= 2:
            ad = on

    # 4. Hâlâ çok uzunsa: kelime sınırında kes, sona "…" koy.
    #    Kelime ORTADAN atılmaz — sadece sondan budanır, okunabilir kalır.
    kelimeler = ad.split()
    if len(kelimeler) > max_kelime:
        ad = " ".join(kelimeler[:max_kelime]) + "…"

    return ad.strip(" ,-") if len(ad.strip(" ,-")) >= 3 else None
