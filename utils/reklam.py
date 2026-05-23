"""
═══════════════════════════════════════════════════════════════════════
Reklam / Ürün Ayrımı — YAPISAL MANTIK (kalıp/kelime listesi YOK)

Eski yaklaşım: "şu kelimeler reklamdır" diye liste tutuyordu → her yeni
reklam çeşidini kaçırıyordu. Bu yaklaşım terk edildi.

YENİ MANTIK — bir mesajın "ne yaptığına" bakar, hangi kelimeleri
içerdiğine değil:

  Bir mesaj GERÇEK ÜRÜN'dür ancak ve ancak şu yapısal koşulları taşırsa:
    1. Satılabilir SOMUT bir nesneye işaret eder (ürün tanıyıcı modeli)
    2. O nesnenin bir FİYATI veya net bir İNDİRİMİ vardır
    3. Bir mağaza/satış linkine gider

  Bunların hiçbiri yoksa → mesaj bir şeyi SATMIYOR, bir EYLEM istiyor
  (katıl, takip et, kazan, tıkla...) → REKLAM/DUYURU.

Bu mantık spesifik kelimelere bağlı DEĞİL. "Kanalımıza katıl" da,
"Join our community" de, "Sürpriz seni bekliyor 🎁" de, daha önce hiç
görülmemiş bir reklam türü de aynı şekilde elenir: çünkü hiçbirinde
satılık somut ürün+fiyat yoktur.

Pure Python, harici bağımlılık yok.
═══════════════════════════════════════════════════════════════════════
"""
import re

# Fiyat var mı? (somut satış işareti)
_FIYAT_RE = re.compile(r"\d[\d.,]*\s*(?:tl|₺|lira|usd|eur|dolar|euro)", re.I)
# İndirim oranı var mı?
_INDIRIM_RE = re.compile(r"%\s*\d+|\d+\s*%|\d+\s*(?:tl|₺)\s*indirim", re.I)
# Mağaza/satış linki var mı? (somut ürüne giden)
_MAGAZA_RE = re.compile(
    r"(trendyol|hepsiburada|amazon|mediamarkt|teknosa|n11|migros|"
    r"ciceksepeti|aliexpress|gratis|boyner|watsons|defacto|lcw|"
    r"vatan|epttavm|morhipo|ty\.gl|hb\.gl|amzn\.to|sl\.n11)",
    re.I,
)


def reklam_mi(metin: str, link: str = "", urun_adi: str = "",
              fiyat_var: bool = False) -> tuple[bool, str]:
    """Mesaj reklam/duyuru mu, satılık gerçek ürün mü?

    Döner: (reklam_mi, sebep)

    YAPISAL MANTIK — kelime listesi yok:
      Bir mesaj "ürün"dür eğer SATILIK SOMUT BİR ŞEY içeriyorsa.
      "Satılık somut şey" = ürün adı (model onaylı) + (fiyat VEYA indirim).

      Hiçbiri yoksa mesaj bir şey SATMIYOR → bir eylem/yönlendirme
      istiyor → reklam/duyuru.
    """
    if not metin or len(metin.strip()) < 3:
        return True, "boş/çok kısa"

    # ── Somut satış sinyallerini ölç (kelimelere değil, yapıya bak) ──
    fiyat_sinyali = fiyat_var or bool(_FIYAT_RE.search(metin))
    indirim_sinyali = bool(_INDIRIM_RE.search(metin))
    magaza_sinyali = bool(_MAGAZA_RE.search(metin)) or bool(_MAGAZA_RE.search(link or ""))

    # Ürün adı: model tarafından onaylanmış somut nesne mi?
    # urun_adi parametresi zaten urun_taniyici modelinden geliyor.
    # Boşsa, modeli burada tekrar deneyelim (bağımsız doğrulama).
    urun_sinyali = bool(urun_adi and len(urun_adi.strip()) >= 3)
    if not urun_sinyali:
        try:
            from utils import urun_taniyici
            tahmin = urun_taniyici.urun_adi_cikar(metin)
            urun_sinyali = bool(tahmin)
        except Exception:
            pass

    # ── KARAR: Satılık somut ürün var mı? ──
    #
    # Gerçek ürün = somut nesne (urun_sinyali) + bir değer göstergesi
    #               (fiyat VEYA indirim).
    #
    # Mağaza linki tek başına yeterli değil — reklam da link içerebilir.
    # Asıl belirleyici: SOMUT NESNE + DEĞER birlikte var mı?

    if urun_sinyali and (fiyat_sinyali or indirim_sinyali):
        return False, "gerçek ürün (somut nesne + fiyat/indirim)"

    # Marka kampanyası: ürün adı yok ama net indirim + mağaza var
    # ("Adidas ürünlerinde %50", "Trendyol'da %40'a varan")
    if indirim_sinyali and magaza_sinyali:
        return False, "marka kampanyası (indirim + mağaza)"

    # Ürün adı var + mağaza linki var ama fiyat yok — sınırda ama paylaşılabilir
    # (link gerçek bir ürüne gidiyor, fiyat sayfada)
    if urun_sinyali and magaza_sinyali:
        return False, "ürün + mağaza linki"

    # ── Buraya geldiyse: satılık somut ürün YOK ──
    # Mesaj bir nesne satmıyor → bir eylem/yönlendirme istiyor → reklam.
    eksikler = []
    if not urun_sinyali:
        eksikler.append("somut ürün yok")
    if not (fiyat_sinyali or indirim_sinyali):
        eksikler.append("fiyat/indirim yok")
    return True, "reklam/duyuru: " + ", ".join(eksikler)


def reklam_skoru(metin: str, link: str = "", urun_adi: str = "") -> float:
    """0.0 (kesin ürün) - 1.0 (kesin reklam). Raporlama için."""
    rek, _ = reklam_mi(metin, link, urun_adi)
    if not rek:
        return 0.0
    # Reklamsa: ne kadar "boş" olduğuna göre skor
    skor = 0.5
    if not _FIYAT_RE.search(metin or ""):
        skor += 0.25
    if not _MAGAZA_RE.search((metin or "") + (link or "")):
        skor += 0.25
    return min(1.0, skor)
