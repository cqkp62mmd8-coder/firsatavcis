"""
LLM fallback — regex parser zayıf kaldığında devreye girer.
Anthropic Claude API kullanır. ANTHROPIC_API_KEY tanımlı değilse devre dışı.

KULLANIM:
    Sadece regex'in başarısız olduğu (urun_adi=None veya indirim=0) ama
    metinde fiyat/yüzde gözüken mesajlarda kullan.

DİKKAT:
    - Her çağrı ~$0.001-0.005 maliyet
    - Senkron HTTP, ~1-3 saniye gecikme
    - Hata durumunda sessizce None döner, regex sonucu kullanılır
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


def aktif_mi() -> bool:
    return bool(_API_KEY)


def parse_et(metin: str) -> dict | None:
    """Mesajı LLM'e gönder, JSON sonucu döndür.
    Beklenen JSON şeması:
      {
        "urun_adi": "string|null",
        "eski_fiyat": "number|null",
        "yeni_fiyat": "number|null",
        "indirim_yuzdesi": "number 0-100",
        "magaza": "string|null",
        "kategori": "elektronik|giyim|kozmetik|ev|market|spor|oyun|bebek|kitap|genel"
      }
    """
    if not _API_KEY or not metin or len(metin) < 10:
        return None

    prompt = (
        "Aşağıdaki Türkçe Telegram fırsat mesajından bilgileri çıkar. "
        "SADECE geçerli JSON dön, başka hiçbir şey yazma.\n\n"
        "Eski fiyat: orijinal/normal/piyasa fiyatı (TL, sayı).\n"
        "Yeni fiyat: indirimli fiyat (TL, sayı).\n"
        "İndirim yüzdesi: 0-99 arası tam sayı; metinde varsa onu, yoksa fiyatlardan hesapla.\n"
        "Mağaza: Trendyol/Hepsiburada/Amazon TR/MediaMarkt/N11/Teknosa/Gratis/Boyner vb. veya null.\n"
        "Kategori: elektronik, giyim, kozmetik, ev, market, spor, oyun, bebek, kitap, genel.\n\n"
        "Mesaj:\n" + metin[:1500] + "\n\n"
        "JSON çıktı:"
    )

    veri = json.dumps({
        "model": _MODEL,
        "max_tokens": _MAX_TOKENS,
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
        # Claude cevabı: content[0].text
        text = cevap.get("content", [{}])[0].get("text", "").strip()
        # ```json fence'lerini sök
        text = text.replace("```json", "").replace("```", "").strip()
        sonuc = json.loads(text)
        log("LLM", f"Parse → ind=%{sonuc.get('indirim_yuzdesi')} ürün={sonuc.get('urun_adi')!r}")
        return sonuc
    except urllib.error.HTTPError as e:
        log("UYARI", f"LLM HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError) as e:
        log("UYARI", f"LLM zaman aşımı: {e}")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        log("UYARI", f"LLM cevap parse hatası: {e}")
    except Exception as e:
        log("UYARI", f"LLM beklenmeyen hata: {e}")
    return None
