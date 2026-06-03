"""
═══════════════════════════════════════════════════════════════════════
Web Scraping — ürün sayfası doğrulama

Trendyol / Hepsiburada / Amazon TR ürün sayfalarından:
  • Open Graph meta etiketleri (og:title, og:image, og:price)
  • Twitter Card etiketleri
  • Schema.org JSON-LD (Product structured data)

Sadece HTML meta tag'leri okunuyor — JavaScript render gerekmez.
Hafif, harici kütüphane yok (urllib + regex).

KULLANIM:
  fiyat doğrulama → mesajdaki fiyatla site fiyatı uyuşuyor mu?
  görsel doğrulama → mesajdaki görsel yoksa siteden çek
  ürün adı düzeltme → siteden tam ad al

YASAL:
  Sadece public OG/meta okuyor, aggressive scraping yapmıyor.
  Rate-limited: aynı domaine 5 saniyede bir.
═══════════════════════════════════════════════════════════════════════
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from utils.log import log

# Rate limit — domain başına son istek zamanı
_son_istek: dict[str, float] = {}
_MIN_BEKLE = 5.0   # aynı domaine 5sn bekle
_TIMEOUT = 8       # HTTP timeout
_USER_AGENT = (
    "Mozilla/5.0 (compatible; FirsatPulsuBot/1.0; "
    "+https://t.me/kacirmabak)"
)

# Desteklenen domainler
_DESTEKLENEN = {
    "trendyol.com", "hepsiburada.com", "amazon.com.tr",
    "n11.com", "teknosa.com", "gratis.com", "boyner.com.tr",
    "mediamarkt.com.tr", "vatanbilgisayar.com", "morhipo.com",
    "watsons.com.tr", "rossmann.com.tr",
}


def _domain_cek(url: str) -> str:
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
        if d.startswith("www."):
            d = d[4:]
        return d
    except Exception:
        return ""


def _destekleniyor_mu(url: str) -> bool:
    d = _domain_cek(url)
    if not d:
        return False
    return any(d == s or d.endswith("." + s) for s in _DESTEKLENEN)


def _rate_limit_uygula(domain: str) -> bool:
    """Aynı domaine 5sn'den önce istek atma. True = atılabilir."""
    son = _son_istek.get(domain, 0)
    if time.time() - son < _MIN_BEKLE:
        return False
    _son_istek[domain] = time.time()
    return True


def _html_indir(url: str) -> Optional[str]:
    """URL'yi indir. None hata durumunda."""
    if not _destekleniyor_mu(url):
        return None
    domain = _domain_cek(url)
    if not _rate_limit_uygula(domain):
        return None   # rate limit
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            # Sadece ilk 200KB — meta etiketleri en üstte olur
            raw = r.read(200 * 1024)
        # Charset tahmini
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return raw.decode("iso-8859-9", errors="ignore")
    except urllib.error.HTTPError as e:
        log("UYARI", f"Web scrape HTTP {e.code} → {url[:60]}")
    except urllib.error.URLError as e:
        log("UYARI", f"Web scrape network → {url[:60]}: {e}")
    except Exception as e:
        log("UYARI", f"Web scrape hata → {url[:60]}: {e}")
    return None


# ── Meta etiket çıkarıcılar ────────────────────────────────────

_OG_PATTERN = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?property=["\']og:([\w:]+)["\'][^>]*?\s+content=["\']([^"\']+)["\']',
    re.I,
)
_OG_PATTERN_REV = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?content=["\']([^"\']+)["\'][^>]*?\s+property=["\']og:([\w:]+)["\']',
    re.I,
)
_TW_PATTERN = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?name=["\']twitter:([\w:]+)["\'][^>]*?\s+content=["\']([^"\']+)["\']',
    re.I,
)
_JSONLD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.+?)</script>',
    re.I | re.DOTALL,
)


def _og_meta_cek(html: str) -> dict[str, str]:
    """Open Graph meta etiketlerini parse et."""
    sonuc: dict[str, str] = {}
    for m in _OG_PATTERN.finditer(html):
        sonuc[m.group(1).lower()] = m.group(2).strip()
    # Bazı siteler content'i önce yazar
    for m in _OG_PATTERN_REV.finditer(html):
        if m.group(2).lower() not in sonuc:
            sonuc[m.group(2).lower()] = m.group(1).strip()
    return sonuc


def _twitter_meta_cek(html: str) -> dict[str, str]:
    sonuc: dict[str, str] = {}
    for m in _TW_PATTERN.finditer(html):
        sonuc[m.group(1).lower()] = m.group(2).strip()
    return sonuc


def _jsonld_urun_cek(html: str) -> Optional[dict]:
    """Schema.org Product structured data ara."""
    for m in _JSONLD_PATTERN.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
            # Tek nesne ya da liste
            if isinstance(data, list):
                for it in data:
                    if isinstance(it, dict) and it.get("@type") == "Product":
                        return it
            elif isinstance(data, dict):
                t = data.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    return data
                # @graph içinde olabilir
                graph = data.get("@graph")
                if isinstance(graph, list):
                    for it in graph:
                        if isinstance(it, dict) and it.get("@type") == "Product":
                            return it
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


# ── Genel API ──────────────────────────────────────────────────

def urun_bilgisi(url: str) -> Optional[dict]:
    """Ürün sayfasından meta bilgilerini çek.

    Döner:
      {
        "ad":     ürün adı,
        "fiyat":  float fiyat (TL),
        "gorsel": görsel URL,
        "magaza": tahmini mağaza (domain bazlı),
        "stok":   "in_stock" / "out_of_stock" / None
      }
    """
    if not url:
        return None
    html = _html_indir(url)
    if not html:
        return None

    og = _og_meta_cek(html)
    tw = _twitter_meta_cek(html)
    jld = _jsonld_urun_cek(html) or {}

    # Ürün adı — birden çok kaynaktan dene
    ad = (og.get("title") or tw.get("title") or jld.get("name", "")).strip()
    # v23.0 — TEK MERKEZİ KAPI: scrape'ten gelen "Amazon" gibi çöp başlıkları ele.
    # og:title bazen sayfa adını ("Amazon") döndürüyor — bu ürün adı değil.
    try:
        from services.urun_kapisi import gecerli_urun_adi
        ad_dogrulanmis = gecerli_urun_adi(ad)
        ad = ad_dogrulanmis or ""
    except Exception:
        pass

    # Görsel
    gorsel = og.get("image") or tw.get("image", "")
    if isinstance(jld.get("image"), str):
        gorsel = gorsel or jld["image"]
    elif isinstance(jld.get("image"), list) and jld["image"]:
        gorsel = gorsel or (jld["image"][0] if isinstance(jld["image"][0], str)
                            else jld["image"][0].get("url", ""))
    elif isinstance(jld.get("image"), dict):
        gorsel = gorsel or jld["image"].get("url", "")

    # Fiyat — JSON-LD'den çekmek en güvenilir
    fiyat = None
    offers = jld.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if isinstance(offers, dict):
        p = offers.get("price") or offers.get("lowPrice")
        if p:
            try:
                fiyat = float(str(p).replace(",", "."))
            except ValueError:
                pass

    # Fiyat OG'den
    if fiyat is None:
        for k in ("product:price:amount", "price:amount", "price"):
            if k in og:
                try:
                    fiyat = float(og[k].replace(",", "."))
                    break
                except ValueError:
                    pass

    # Stok
    stok = None
    if isinstance(offers, dict):
        availability = offers.get("availability", "")
        if "InStock" in availability:
            stok = "in_stock"
        elif "OutOfStock" in availability:
            stok = "out_of_stock"

    return {
        "ad":     ad or None,
        "fiyat":  fiyat,
        "gorsel": gorsel or None,
        "magaza": _domain_cek(url),
        "stok":   stok,
    }


def fiyat_dogrula(url: str, beklenen_fiyat: float, tolerans: float = 0.15) -> tuple[bool, str]:
    """Site fiyatı mesajdaki fiyatla uyuşuyor mu?

    Args:
      url: ürün sayfası
      beklenen_fiyat: mesajdaki TL fiyat
      tolerans: kabul edilen yüzde fark (0.15 = %15)

    Döner: (uyuşuyor_mu, açıklama)
    """
    if not url or beklenen_fiyat is None:
        return True, "doğrulanmadı"
    bilgi = urun_bilgisi(url)
    if not bilgi or bilgi.get("fiyat") is None:
        return True, "site fiyatı okunamadı"

    site_fiyat = bilgi["fiyat"]
    fark = abs(site_fiyat - beklenen_fiyat) / max(beklenen_fiyat, 1)
    if fark > tolerans:
        return False, f"site fiyatı {site_fiyat} TL, mesaj {beklenen_fiyat} TL (fark %{fark*100:.0f})"
    return True, f"uyuştu (site {site_fiyat} ≈ mesaj {beklenen_fiyat})"


def destekleniyor_mu(url: str) -> bool:
    """Bu URL'den scraping yapabilir miyiz?"""
    return _destekleniyor_mu(url)


def istatistik() -> dict:
    """Son istek zamanları (debug)."""
    return {
        "destek_domain_sayi":   len(_DESTEKLENEN),
        "son_istek_domain":     dict(_son_istek),
        "rate_limit_sn":        _MIN_BEKLE,
    }
