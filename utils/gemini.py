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
_istek_say = 0
_basari_say = 0

# v22.3 — Akıllı kota yönetimi (Free tier: 1000/gün, 15/dakika, UTC sıfırlanır)
_dakika_istekleri: list = []    # son dakika içindeki istek timestamp'leri
_DAKIKA_LIMIT = 12              # 15 limit ama 12'de fren (güvenli marj)
_kota_doldu_gun = ""            # 'YYYY-MM-DD' (UTC) — bu günde dolduysa bir daha deneme


def _utc_gun() -> str:
    """UTC tarihi YYYY-MM-DD — Gemini kotası UTC gece yarısı sıfırlanır."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def kullanilabilir() -> bool:
    """Gemini şu an kullanılabilir mi?
    v22.3: Günlük kota dolduysa UTC gün dönene kadar BEKLEME (eskiden 1 saat
    boş yere deniyordu — kota günlüktür, saatlik değil)."""
    if not aktif:
        return False
    # Günlük kota dolduysa: o günün UTC tarihinde bir daha denemeyiz
    if _kota_doldu_gun and _kota_doldu_gun == _utc_gun():
        return False
    # Arka arkaya çok hata → kısa dinlen
    if _hata_say >= 5 and (time.time() - _son_hata_ts) < _DINLENME:
        return False
    # Dakikalık limit kontrolü (önleyici fren)
    simdi = time.time()
    # 60 saniyeden eski kayıtları temizle
    while _dakika_istekleri and _dakika_istekleri[0] < simdi - 60:
        _dakika_istekleri.pop(0)
    if len(_dakika_istekleri) >= _DAKIKA_LIMIT:
        return False   # bu dakika için doldu, biraz bekleyelim
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
        "ÖNEMLİ: Mesajda somut bir ürün + fiyat/indirim varsa bu bir ÜRÜNDÜR "
        "(reklam=false). 'Google'da Karşılaştır', 'fiyat karşılaştır', mağaza "
        "linki gibi ifadeler ürünü reklam YAPMAZ — bunları yok say.\n"
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
        "yoksa ''. Çoğu üründe '' olmalı.\n"
        "8. fiyat: Ürünün GÜNCEL/İNDİRİMLİ satış fiyatı (sadece sayı, TL, "
        "nokta/virgül olmadan tam sayı). Yoksa 0.\n"
        "9. eski_fiyat: Varsa indirimden ÖNCEKİ fiyat (sadece sayı). Yoksa 0.\n\n"
        "SADECE şu JSON formatında cevap ver, başka hiçbir şey yazma:\n"
        '{"reklam": true/false, "urun_adi": "..." veya null, '
        '"kategori": "...", "alt_kategori": "...", "kalite": 0-5, '
        '"tanitim": "...", "fiyat_uyari": "...", "fiyat": 0, "eski_fiyat": 0}\n\n'
        f"Mesaj:\n{mesaj[:1000]}"
    )


def _gemini_cagir(mesaj: str) -> Optional[dict]:
    """Gemini API'sine tek istek. Sonuç dict veya None (hata)."""
    global _son_hata_ts, _hata_say, _istek_say, _basari_say, _kota_doldu_ts
    global _kota_doldu_gun

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
        _dakika_istekleri.append(time.time())
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            ham = r.read().decode("utf-8", errors="ignore")
        veri = json.loads(ham)
        # Gemini cevabını çıkar
        metin = (
            veri.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        ).strip()
        # Gemini bazen ```json ... ``` ile sarar — temizle
        if metin.startswith("```"):
            metin = metin.lstrip("`")
            if metin[:4].lower() == "json":
                metin = metin[4:]
            metin = metin.strip("`").strip()
        # JSON gövdesini izole et (baştaki/sondaki gürültüyü at)
        if "{" in metin and "}" in metin:
            metin = metin[metin.index("{"): metin.rindex("}") + 1]
        if not metin:
            raise ValueError("boş Gemini yanıtı")
        sonuc = json.loads(metin)
        # Başarı — hata/kota sayaçlarını sıfırla
        _hata_say = 0
        _kota_doldu_ts = 0.0
        _kota_doldu_gun = ""   # v22.3: gün döndü, kota açıldı
        _basari_say += 1
        try:
            kalite = int(sonuc.get("kalite", 0))
        except (ValueError, TypeError):
            kalite = 0
        def _sayi(v):
            try:
                return int(float(str(v).replace(".", "").replace(",", "")))
            except (ValueError, TypeError):
                return 0
        return {
            "reklam":        bool(sonuc.get("reklam", False)),
            "urun_adi":      (sonuc.get("urun_adi") or None),
            "kategori":      (sonuc.get("kategori") or "genel"),
            "alt_kategori":  (sonuc.get("alt_kategori") or ""),
            "kalite":        max(0, min(5, kalite)),
            "tanitim":       (sonuc.get("tanitim") or "").strip(),
            "fiyat_uyari":   (sonuc.get("fiyat_uyari") or "").strip(),
            "fiyat":         _sayi(sonuc.get("fiyat", 0)),
            "eski_fiyat":    _sayi(sonuc.get("eski_fiyat", 0)),
        }
    except urllib.error.HTTPError as e:
        _hata_say += 1
        _son_hata_ts = time.time()
        if e.code == 429:
            # v22.3: Günlük kota dolduysa o gün için Gemini'yi tamamen kapat.
            # UTC gece yarısı (TR 03:00) sıfırlanır → ertesi gün otomatik açılır.
            _kota_doldu_gun = _utc_gun()
            _kota_doldu_ts = time.time()
            log("UYARI", f"Gemini günlük kota doldu (429) — UTC {_kota_doldu_gun} "
                          "günü için Gemini kapatıldı, yarın TR 03:00'te otomatik açılır")
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
        _dakika_istekleri.append(time.time())
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
    # v22.3: günlük kota durumu
    kota_aktif = bool(_kota_doldu_gun and _kota_doldu_gun == _utc_gun())
    # Dakika içindeki istek sayısı (canlı izleme)
    simdi = time.time()
    while _dakika_istekleri and _dakika_istekleri[0] < simdi - 60:
        _dakika_istekleri.pop(0)
    return {
        "aktif":          aktif,
        "model":          _MODEL if aktif else "(devre dışı — anahtar yok)",
        "istek":          _istek_say,
        "basari":         _basari_say,
        "hata":           _hata_say,
        "cache_boyut":    len(_cache),
        "dinlenmede":     not kullanilabilir() and aktif,
        "kota_doldu":     kota_aktif,
        "dakika_istegi":  len(_dakika_istekleri),
        "dakika_limit":   _DAKIKA_LIMIT,
    }
