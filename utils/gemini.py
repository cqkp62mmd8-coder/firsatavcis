"""
═══════════════════════════════════════════════════════════════════════
Gemini Anlama Katmanı — GERÇEK yapay zeka ile mesaj analizi

Saf-Python istatistik modelleri (urun_taniyici, reklam, ml_kategori)
yerine, mesajı gerçekten ANLAYAN bir dil modeli kullanır.

Tek bir API çağrısıyla şunları birden döndürür:
  • Bu mesaj satılık bir ürün mü, yoksa reklam/duyuru mu?
  • Ürünse adı ne? (markası bilinmese bile anlar)
  • Kategorisi ne?

Kalıp YOK, örnek listesi YOK. Model mesajı okuyup anlıyor — bu yüzden
daha önce hiç görülmemiş reklam türlerini de, bilinmeyen markaları da
doğru değerlendirir.

DAYANIKLILIK:
  • Sonuçlar cache'lenir (aynı mesaj 2 kez sorulmaz — kota tasarrufu)
  • Rate limit / hata / kota dolması → saf-Python yedeğe otomatik döner
  • API anahtarı yoksa → sessizce yedek sisteme düşer (bot durmaz)

KURULUM:
  Railway'de environment variable: GEMINI_API_KEY=...
  (aistudio.google.com'dan ücretsiz alınır)

Ücretsiz katman (2026): Gemini 2.5 Flash-Lite — 15 istek/dk, 1000 istek/gün.
Kota dolunca bot saf-Python sistemine döner, durmaz.
═══════════════════════════════════════════════════════════════════════
"""
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

from utils.log import log

# ── Yapılandırma ──
_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
_TIMEOUT = 12          # saniye — yavaşsa yedeğe düş
_CACHE_MAKS = 2000     # bellekte tutulacak sonuç sayısı

# ── Durum ──
aktif = bool(_API_KEY)          # anahtar varsa Gemini kullan
_cache: dict[str, dict] = {}    # mesaj hash → sonuç
_son_hata_ts = 0.0              # arka arkaya hata olursa bir süre dinlen
_hata_say = 0
_DINLENME = 60                  # saniye — çok hata olursa bu kadar dinlen
_kota_doldu_ts = 0.0            # 429 alındığı an
_KOTA_DINLENME = 3600           # kota dolunca 1 saat dinlen (kota saatlik/günlük)
_istek_say = 0
_basari_say = 0


def kullanilabilir() -> bool:
    """Gemini şu an kullanılabilir mi? (anahtar var + dinlenmede değil)"""
    if not aktif:
        return False
    # Kota doldu (429) → uzun süre dinlen, gereksiz istek atma
    if _kota_doldu_ts and (time.time() - _kota_doldu_ts) < _KOTA_DINLENME:
        return False
    # Arka arkaya çok hata → kısa dinlen
    if _hata_say >= 5 and (time.time() - _son_hata_ts) < _DINLENME:
        return False
    return True


def _prompt(mesaj: str) -> str:
    """Modele verilecek talimat — net, kısa, JSON isteyen."""
    return (
        "Sen bir Türkçe e-ticaret fırsat kanalı için uzman mesaj analiz "
        "asistanısın. Sana bir Telegram mesajı veriyorum. Şunları belirle:\n\n"
        "1. reklam: Bu mesaj SATILIK SOMUT BİR ÜRÜN mü tanıtıyor (false), "
        "yoksa bir REKLAM/DUYURU mu (true)? Reklam örnekleri: kanala katıl, "
        "çekiliş, işbirliği, sponsor, bonus/puan kazan, takip et, davet et, "
        "üyelik tanıtımı. Satılık somut ürün yoksa true.\n"
        "2. urun_adi: Üründü ise ürünün TEMİZ adı (marka + model + önemli "
        "özellik). Slogan, fiyat, kargo, kupon, indirim ifadelerini KATMA. "
        "Reklamsa null.\n"
        "3. kategori: Ana kategori — elektronik, giyim, kozmetik, ev, market, "
        "spor, oyun, bebek, saglik, otomotiv. Emin değilsen 'genel'.\n"
        "4. alt_kategori: Daha spesifik tür (telefon, ayakkabi, parfum, "
        "supurge, oyuncak vb). Bilmiyorsan ''.\n"
        "5. kalite: Bu bir fırsat olarak ne kadar cazip/paylaşmaya değer? "
        "1 (zayıf) - 5 (mükemmel fırsat). Reklamsa 0.\n"
        "6. tanitim: Üründü ise, bu ürünü kanal takipçisine tanıtan KISA, "
        "doğal, çekici tek cümle (en fazla 12 kelime). Abartı/clickbait YOK, "
        "ürünün gerçek bir faydasını/özelliğini vurgula. Reklamsa ''.\n"
        "7. fiyat_uyari: Eğer indirim/fiyat ŞÜPHELİ görünüyorsa (ör. gerçekçi "
        "olmayan %90 indirim, şişirilmiş eski fiyat) kısa bir uyarı yaz, "
        "yoksa ''. Çoğu üründe '' olmalı.\n\n"
        "SADECE şu JSON formatında cevap ver, başka hiçbir şey yazma:\n"
        '{"reklam": true/false, "urun_adi": "..." veya null, '
        '"kategori": "...", "alt_kategori": "...", "kalite": 0-5, '
        '"tanitim": "...", "fiyat_uyari": "..."}\n\n'
        f"Mesaj:\n{mesaj[:1000]}"
    )


def _gemini_cagir(mesaj: str) -> Optional[dict]:
    """Gemini API'sine tek istek. Sonuç dict veya None (hata)."""
    global _son_hata_ts, _hata_say, _istek_say, _basari_say, _kota_doldu_ts

    if not _API_KEY:
        return None

    govde = json.dumps({
        "contents": [{"parts": [{"text": _prompt(mesaj)}]}],
        "generationConfig": {
            "temperature": 0,            # tutarlı/deterministik
            "maxOutputTokens": 350,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    url = _API_URL.format(model=_MODEL)
    req = urllib.request.Request(
        url, data=govde, method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": _API_KEY,
        },
    )

    try:
        _istek_say += 1
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            ham = r.read().decode("utf-8", errors="ignore")
        veri = json.loads(ham)
        # Gemini cevabını çıkar
        metin = (
            veri.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        sonuc = json.loads(metin)
        # Başarı — hata/kota sayaçlarını sıfırla
        _hata_say = 0
        _kota_doldu_ts = 0.0
        _basari_say += 1
        try:
            kalite = int(sonuc.get("kalite", 0))
        except (ValueError, TypeError):
            kalite = 0
        return {
            "reklam":        bool(sonuc.get("reklam", False)),
            "urun_adi":      (sonuc.get("urun_adi") or None),
            "kategori":      (sonuc.get("kategori") or "genel"),
            "alt_kategori":  (sonuc.get("alt_kategori") or ""),
            "kalite":        max(0, min(5, kalite)),
            "tanitim":       (sonuc.get("tanitim") or "").strip(),
            "fiyat_uyari":   (sonuc.get("fiyat_uyari") or "").strip(),
        }
    except urllib.error.HTTPError as e:
        _hata_say += 1
        _son_hata_ts = time.time()
        if e.code == 429:
            _kota_doldu_ts = time.time()
            log("UYARI", "Gemini kota doldu (429) — 1 saat yedek sisteme dönülüyor")
        else:
            log("UYARI", f"Gemini HTTP {e.code} — yedeğe dönülüyor")
        return None
    except Exception as e:
        _hata_say += 1
        _son_hata_ts = time.time()
        log("UYARI", f"Gemini hatası ({type(e).__name__}) — yedeğe dönülüyor")
        return None


def _hash(mesaj: str) -> str:
    """Cache anahtarı — mesajın ilk 200 karakteri yeterli."""
    return mesaj.strip()[:200]


def analiz_et(mesaj: str) -> Optional[dict]:
    """Bir mesajı Gemini ile analiz et.

    Döner:
      {"reklam": bool, "urun_adi": str|None, "kategori": str}
      veya None (Gemini kullanılamıyor → çağıran yedek sisteme düşmeli)

    Bu fonksiyon SENKRON — async kodda run_in_executor ile çağrılmalı.
    """
    if not mesaj or not kullanilabilir():
        return None

    anahtar = _hash(mesaj)
    if anahtar in _cache:
        return _cache[anahtar]

    sonuc = _gemini_cagir(mesaj)
    if sonuc is not None:
        # Cache'e ekle (boyut sınırı)
        if len(_cache) >= _CACHE_MAKS:
            # En eski yarısını at (basit FIFO)
            for k in list(_cache.keys())[: _CACHE_MAKS // 2]:
                del _cache[k]
        _cache[anahtar] = sonuc
    return sonuc


def kisa_metin(talimat: str, maks_token: int = 80) -> Optional[str]:
    """Gemini'ye serbest, kısa bir metin ürettir (başlık, özet, duyuru vb).
    JSON değil düz metin döner. Hata/kota olursa None.

    SENKRON — async kodda run_in_executor ile çağrılmalı."""
    global _son_hata_ts, _hata_say, _istek_say, _basari_say
    if not talimat or not kullanilabilir() or not _API_KEY:
        return None

    govde = json.dumps({
        "contents": [{"parts": [{"text": talimat}]}],
        "generationConfig": {
            "temperature": 0.7,   # biraz yaratıcılık (başlık/özet için)
            "maxOutputTokens": maks_token,
        },
    }).encode("utf-8")
    url = _API_URL.format(model=_MODEL)
    req = urllib.request.Request(
        url, data=govde, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": _API_KEY},
    )
    try:
        _istek_say += 1
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            ham = r.read().decode("utf-8", errors="ignore")
        veri = json.loads(ham)
        metin = (
            veri.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        ).strip()
        _hata_say = 0
        _basari_say += 1
        return metin or None
    except Exception as e:
        _hata_say += 1
        _son_hata_ts = time.time()
        log("UYARI", f"Gemini kısa metin hatası ({type(e).__name__})")
        return None


def istatistik() -> dict:
    kota_aktif = bool(_kota_doldu_ts and (time.time() - _kota_doldu_ts) < _KOTA_DINLENME)
    return {
        "aktif":        aktif,
        "model":        _MODEL if aktif else "(devre dışı — anahtar yok)",
        "istek":        _istek_say,
        "basari":       _basari_say,
        "hata":         _hata_say,
        "cache_boyut":  len(_cache),
        "dinlenmede":   not kullanilabilir() and aktif,
        "kota_doldu":   kota_aktif,
    }
