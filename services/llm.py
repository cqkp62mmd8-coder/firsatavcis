"""
LLM fallback — regex parser zayıf kaldığında devreye girer.
Anthropic Claude API kullanır. ANTHROPIC_API_KEY tanımlı değilse devre dışı.

İKİ KULLANIM:
  1. parse_et()        — regex zayıfsa fiyat/ürün adı/indirim çıkar
  2. kategori_sor()    — ML belirsizse otomatik öğretmen olarak çağrılır

OTOMATIK ÖĞRETMEN:
    ML modeli düşük güvende kaldığında (örn. <0.55), Claude'a kategoriyi
    sorarız. Cevap doğrulanmış öğrenme verisi olarak ML'e eklenir.
    Böylece kullanıcı /ogret komutu ile uğraşmaz — ML kendiliğinden
    bilgilenmiş bir "öğretmen"den öğrenir.

DİKKAT:
    - Her çağrı ~$0.001-0.005 maliyet
    - Senkron HTTP, ~1-3 saniye gecikme
    - Hata durumunda sessizce None döner
"""
import json
import os
import urllib.request
import urllib.error

from utils.log import log

_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
_MODEL      = "claude-haiku-4-5"
_API_URL    = "https://api.anthropic.com/v1/messages"
_MAX_TOKENS = 300

# Maliyet/oran kontrol: aynı oturum başına en fazla N LLM çağrısı
# (debug / kontrolsüz patlama önleme)
_OTURUM_LIMIT = 500
_oturum_sayac = 0


def aktif_mi() -> bool:
    return bool(_API_KEY) and _oturum_sayac < _OTURUM_LIMIT


def _claude_cagir(prompt: str, max_token: int = _MAX_TOKENS) -> str | None:
    """Düşük seviye Claude API çağrısı. Plain text döner."""
    global _oturum_sayac
    if not _API_KEY:
        return None
    if _oturum_sayac >= _OTURUM_LIMIT:
        return None
    _oturum_sayac += 1

    veri = json.dumps({
        "model": _MODEL,
        "max_tokens": max_token,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        _API_URL,
        data=veri,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            cevap = json.loads(r.read())
        text = cevap.get("content", [{}])[0].get("text", "").strip()
        return text
    except urllib.error.HTTPError as e:
        log("UYARI", f"LLM HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError) as e:
        log("UYARI", f"LLM zaman aşımı: {e}")
    except Exception as e:
        log("UYARI", f"LLM beklenmeyen hata: {e}")
    return None


def parse_et(metin: str) -> dict | None:
    """Mesajı LLM'e gönder, JSON sonucu döndür."""
    if not aktif_mi() or not metin or len(metin) < 10:
        return None

    prompt = (
        "Aşağıdaki Türkçe Telegram fırsat mesajından bilgileri çıkar. "
        "SADECE geçerli JSON dön, başka hiçbir şey yazma.\n\n"
        "Eski fiyat: orijinal/normal/piyasa fiyatı (TL, sayı).\n"
        "Yeni fiyat: indirimli fiyat (TL, sayı).\n"
        "İndirim yüzdesi: 0-99 arası tam sayı; metinde varsa onu, yoksa fiyatlardan hesapla.\n"
        "Mağaza: Trendyol/Hepsiburada/Amazon TR/MediaMarkt/N11/Teknosa/Gratis/Boyner vb. veya null.\n"
        "Kategori: elektronik, giyim, kozmetik, ev, market, spor, oyun, bebek, saglik, otomotiv, genel.\n\n"
        "Mesaj:\n" + metin[:1500] + "\n\n"
        "JSON çıktı:"
    )

    text = _claude_cagir(prompt)
    if not text:
        return None
    try:
        text = text.replace("```json", "").replace("```", "").strip()
        sonuc = json.loads(text)
        log("LLM", f"Parse → ind=%{sonuc.get('indirim_yuzdesi')} ürün={sonuc.get('urun_adi')!r}")
        return sonuc
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        log("UYARI", f"LLM cevap parse hatası: {e}")
    return None


# ════════════════════════════════════════════════════════════════
# KATEGORI ÖĞRETMENİ — ML düşük güvende kaldığında otomatik soru
# ════════════════════════════════════════════════════════════════

# Geçerli ana kategoriler — LLM cevabı buna sınırlanır
_GECERLI_ANA = {
    "elektronik", "giyim", "kozmetik", "ev", "market",
    "spor", "oyun", "bebek", "saglik", "otomotiv",
}

# Geçerli alt kategori sözlüğü (utils/ml_kategoriler.py ile senkron)
_GECERLI_ALT = {
    "elektronik": {"telefon", "bilgisayar", "tv", "ses", "saat", "beyaz_esya", "alet", "kamera", "aksesuar"},
    "giyim":      {"ayakkabi", "ust_giyim", "alt_giyim", "dis_giyim", "canta", "ic_giyim", "aksesuar"},
    "kozmetik":   {"yuz_bakim", "makyaj", "parfum", "sac_bakim", "vucut"},
    "ev":         {"tekstil", "mutfak", "mobilya", "dekor", "banyo", "bahce"},
    "market":     {"atistir", "icecek", "temel", "temizlik", "evcil"},
    "spor":       {"fitness", "outdoor", "bisiklet", "top", "su_sporu", "kayak"},
    "oyun":       {"lego", "konsol", "aksesuar", "oyuncak"},
    "bebek":      {"bez", "beslenme", "koltuk", "puset", "oyuncak"},
    "saglik":     {"vitamin", "takviye", "tibbi", "kisisel"},
    "otomotiv":   {"lastik", "yag", "aku", "bakim", "aksesuar"},
}


def kategori_sor(urun_adi: str, baglam: str = "") -> tuple[str, str] | None:
    """Bir ürün adı için Claude'dan (ana, alt) kategori çiftini ister.

    Kullanım:
      ML belirsiz kaldığında (güven < 0.55) çağırın.
      Cevap doğrulanmış bir öğrenme verisi olarak ML'e eklenir.

    Args:
      urun_adi: Ürün adı (ML'in tahmin yapamadığı)
      baglam:   Mesajın orijinal hali (opsiyonel, daha iyi karar için)

    Returns:
      (ana_kategori, alt_kategori) tuple, ya da None hata durumunda.
      alt_kategori boş string olabilir — sadece ana belirlenmişse.
    """
    if not aktif_mi() or not urun_adi or len(urun_adi) < 3:
        return None

    alt_listesi = "\n".join(
        f"  {ana}: {', '.join(sorted(alts))}"
        for ana, alts in _GECERLI_ALT.items()
    )

    prompt = (
        "Bir e-ticaret ürünü için ana kategori + alt kategori belirle. "
        "SADECE 'ana:alt' formatında, küçük harflerle, başka hiçbir şey yazma.\n\n"
        "GEÇERLİ KATEGORİLER:\n" + alt_listesi + "\n\n"
        f"ÜRÜN ADI: {urun_adi}\n"
        + (f"BAĞLAM: {baglam[:300]}\n" if baglam else "")
        + "\nCEVAP (ana:alt):"
    )

    text = _claude_cagir(prompt, max_token=30)
    if not text:
        return None

    # Cevabı temizle: "elektronik:telefon" gibi
    text = text.strip().strip("\"'`.,;").lower()
    # İlk satırı al (Claude bazen birden fazla satır yazabilir)
    text = text.split("\n")[0].strip()

    if ":" not in text:
        # Sadece ana kategori vermiş
        ana = text.strip()
        if ana in _GECERLI_ANA:
            log("LLM", f"Kategori → {ana} (alt belirsiz) | ürün: {urun_adi[:40]}")
            return (ana, "")
        return None

    ana, alt = text.split(":", 1)
    ana = ana.strip()
    alt = alt.strip()

    if ana not in _GECERLI_ANA:
        log("UYARI", f"LLM bilinmeyen ana kategori: {ana!r} | ürün: {urun_adi[:40]}")
        return None

    if alt and alt not in _GECERLI_ALT.get(ana, set()):
        log("UYARI", f"LLM bilinmeyen alt kategori: {ana}:{alt!r} | ürün: {urun_adi[:40]}")
        # Ana kabul, alt at
        alt = ""

    log("LLM", f"Kategori → {ana}:{alt} | ürün: {urun_adi[:40]}")
    return (ana, alt)


def oturum_istatistik() -> dict:
    """Bu oturumda yapılan LLM çağrılarının sayısı."""
    return {"oturum_cagri": _oturum_sayac, "limit": _OTURUM_LIMIT, "aktif": aktif_mi()}
