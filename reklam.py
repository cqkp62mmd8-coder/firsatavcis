"""
═══════════════════════════════════════════════════════════════════════
Reklam / Promosyon Tespiti

İndirim oranı olmayan ama gerçek ürün olan mesajları paylaşmak istiyoruz.
Ama kanal reklamlarını, davet mesajlarını, genel duyuruları DEĞİL.

Bu modül bir mesajın "reklam/duyuru" mı yoksa "gerçek ürün fırsatı" mı
olduğunu ayırt eder.

REKLAM SİNYALLERİ:
  • Kanala katılım çağrısı ("kanalımıza katıl", "abone ol", "join")
  • Genel duyuru ("en iyi fırsatlar burada", "günün fırsatları")
  • Çekiliş / promosyon ("çekiliş", "hediye kazan", "yarışma")
  • Sosyal medya yönlendirme ("instagram", "youtube", "takip et")
  • Ürün/fiyat YOKLUĞU (somut ürün adı + fiyat yoksa şüpheli)
  • Aşırı çağrı-eylem ("hemen tıkla", "kaçırma", "acele et" yığını)

ÜRÜN SİNYALLERİ (reklam DEĞİL):
  • Somut ürün adı (marka + model)
  • Fiyat (TL)
  • Mağaza linki (Trendyol, Hepsiburada, Amazon...)

Pure Python, harici bağımlılık yok.
═══════════════════════════════════════════════════════════════════════
"""
import re

# ── Reklam/duyuru kalıpları (güçlü sinyal) ──
_REKLAM_KALIPLARI = [
    # Kanal/grup daveti
    r"kanal[ıi]m[ıi]z[ae]?\s*(?:katıl|abone|gel|bekliyoruz)",
    r"grub[au]m[ıi]z[ae]?\s*(?:katıl|gel)",
    r"\babone\s*ol",
    r"\bkatılmak\s*için",
    r"\bjoin\b",
    r"üye\s*ol(?:un)?\b",
    r"takip\s*et(?:meyi)?\s*unutma",
    r"bizi\s*takip",
    # Sosyal medya yönlendirme
    r"instagram(?:'?d[ae]n?)?\s*(?:takip|bizi)",
    r"youtube\s*kanal",
    r"tiktok'?ta",
    r"sosyal\s*medya(?:m[ıi]z)?",
    # Çekiliş / promosyon
    r"çekiliş",
    r"hediye\s*kazan",
    r"yarışma(?:m[ıi]z)?",
    r"ödül\s*kazan",
    r"\bsweepstake",
    r"\bgiveaway\b",
    # Genel duyuru
    r"günün\s*fırsat",
    r"en\s*iyi\s*fırsatlar\s*(?:burada|bizde|kanal)",
    r"fırsatları?\s*kaçırma(?:mak)?\s*için\s*(?:kanal|takip|abone)",
    r"tüm\s*fırsatlar\s*için",
    r"daha\s*fazla(?:sı)?\s*için\s*(?:kanal|tıkla|takip)",
    r"reklam\s*(?:ve\s*)?(?:iş\s*birliği|işbirliği|için)",
    r"iletişim\s*için\s*(?:dm|mesaj|@)",
    r"\bsponsor",
    # Bot tanıtım
    r"bot'?umuz",
    r"botu\s*(?:dene|kullan)",
]
_REKLAM_RE = [re.compile(p, re.I) for p in _REKLAM_KALIPLARI]

# ── Ürün sinyali kalıpları ──
_FIYAT_RE = re.compile(r"\d[\d.,]*\s*(?:tl|₺|lira)", re.I)
_MAGAZA_LINK_RE = re.compile(
    r"(trendyol|hepsiburada|amazon|mediamarkt|teknosa|n11|"
    r"ciceksepeti|aliexpress|gratis|boyner|watsons|migros|"
    r"ty\.gl|hb\.gl|amzn\.to)",
    re.I,
)


def reklam_mi(metin: str, link: str = "", urun_adi: str = "",
              fiyat_var: bool = False) -> tuple[bool, str]:
    """Mesaj reklam/duyuru mu, gerçek ürün mü?

    Döner: (reklam_mi, sebep)
      reklam_mi=True  → paylaşma (kanal reklamı/duyuru)
      reklam_mi=False → gerçek ürün, paylaşılabilir

    Mantık:
      1. Güçlü reklam kalıbı varsa → reklam (ürün sinyali olsa bile riskli)
      2. Hiç ürün sinyali yoksa (fiyat YOK + ürün adı YOK + mağaza linki YOK)
         → reklam/duyuru
      3. Aksi halde → gerçek ürün
    """
    if not metin:
        return True, "boş mesaj"

    ml = metin.lower()

    # ── 1. Güçlü reklam kalıbı ──
    reklam_eslesme = 0
    eslesileri = []
    for rx in _REKLAM_RE:
        if rx.search(ml):
            reklam_eslesme += 1
            eslesileri.append(rx.pattern[:25])

    # ── Ürün sinyallerini say ──
    fiyat_sinyali = fiyat_var or bool(_FIYAT_RE.search(metin))
    magaza_sinyali = bool(_MAGAZA_LINK_RE.search(metin)) or bool(_MAGAZA_LINK_RE.search(link))
    urun_sinyali = bool(urun_adi and len(urun_adi) >= 5)
    sinyal_sayi = sum([fiyat_sinyali, magaza_sinyali, urun_sinyali])

    # 2 veya daha fazla güçlü reklam kalıbı → kesin reklam
    if reklam_eslesme >= 2:
        return True, f"reklam ({reklam_eslesme} kalıp: {', '.join(eslesileri[:2])})"

    # 1 reklam kalıbı VE zayıf ürün sinyali → reklam
    if reklam_eslesme == 1 and sinyal_sayi < 2:
        return True, f"reklam (1 kalıp + zayıf ürün sinyali: {eslesileri[0]})"

    # ── 3. Hiç ürün sinyali yok → duyuru/reklam ──
    if sinyal_sayi == 0:
        return True, "ürün sinyali yok (fiyat/mağaza/ürün adı hiçbiri)"

    # ── Sadece 1 zayıf sinyal varsa, ek kontrol ──
    # Mağaza linki var ama fiyat/ürün adı yok → "kampanya duyurusu" olabilir
    # ama yine de paylaşılabilir nitelikte (link gerçek ürüne gidiyor)
    if sinyal_sayi == 1 and magaza_sinyali and not (fiyat_sinyali or urun_sinyali):
        # Marka kampanyası mı? ("%X indirim" ya da "tüm ürünlerde")
        if re.search(r"%\s*\d+|tüm\s+\w+\s+ürünler|\d+\s*al\s*\d+\s*öde", ml):
            return False, "marka kampanyası (link + indirim ifadesi)"
        # Aksi halde belirsiz, riskli — atla
        return True, "sadece link var, ürün belirsiz"

    # Gerçek ürün
    return False, "gerçek ürün"


def reklam_skoru(metin: str) -> float:
    """0.0 (kesin ürün) - 1.0 (kesin reklam) arası skor.
    İnce ayar/raporlama için."""
    if not metin:
        return 1.0
    ml = metin.lower()
    skor = 0.0
    for rx in _REKLAM_RE:
        if rx.search(ml):
            skor += 0.35
    if not _FIYAT_RE.search(metin):
        skor += 0.2
    if not _MAGAZA_LINK_RE.search(metin):
        skor += 0.15
    return min(1.0, skor)
