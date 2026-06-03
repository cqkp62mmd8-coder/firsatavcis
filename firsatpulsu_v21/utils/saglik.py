"""
═══════════════════════════════════════════════════════════════════════
SAĞLIK METRİKLERİ — Bot kendi kendini izler

Amaç: Bot, işleme sırasında neyi neden atladığını/başardığını sayar.
Böylece sistemsel bir sorun (örn. ürün adı sürekli çıkmıyor, Gemini
sürekli hata veriyor) admin fark etmeden ÖNCE tespit edilir.

Bellek-içi, hafif sayaçlar. Watchdog bunları periyodik okur ve anormallik
görürse admin'e bildirir.

Örnek anormallikler:
  • Son 1 saatte işlenen mesajların >%80'i atlandı → kaynak/parse sorunu
  • Ürün adı çıkarma başarısızlığı çok yüksek → format değişti
  • Gemini hata oranı çok yüksek → API/kota sorunu
═══════════════════════════════════════════════════════════════════════
"""
import time
from collections import deque

# Son olayların zaman damgalı kaydı (kayan pencere)
_PENCERE = 3600   # 1 saat
_olaylar: deque = deque(maxlen=5000)   # (ts, tip, alt_sebep)


def kaydet(tip: str, alt_sebep: str = "") -> None:
    """Bir işleme olayını kaydet.
    tip: 'paylasildi' | 'atlandi' | 'urun_adi_yok' | 'reklam' |
         'link_yok' | 'gemini_basari' | 'gemini_hata' | 'hata'
    """
    _olaylar.append((time.time(), tip, alt_sebep))


def _son_pencere() -> list:
    kesim = time.time() - _PENCERE
    return [o for o in _olaylar if o[0] >= kesim]


def ozet() -> dict:
    """Son 1 saatin işleme özeti."""
    son = _son_pencere()
    if not son:
        return {"toplam": 0}
    sayim: dict[str, int] = {}
    for _, tip, _alt in son:
        sayim[tip] = sayim.get(tip, 0) + 1
    return {"toplam": len(son), **sayim}


def saglik_kontrol() -> list[str]:
    """Sistemsel anormallikleri tespit et. Sorun listesi döner (boşsa sağlıklı).

    Bu, botun kendi kendini teşhis etmesidir — admin fark etmeden önce."""
    son = _son_pencere()
    toplam = len(son)
    sorunlar: list[str] = []

    # Yeterli veri yoksa kontrol etme (en az 10 olay)
    if toplam < 10:
        return sorunlar

    sayim: dict[str, int] = {}
    for _, tip, _alt in son:
        sayim[tip] = sayim.get(tip, 0) + 1

    paylasildi = sayim.get("paylasildi", 0)
    atlandi = toplam - paylasildi

    # 1. Atlama oranı çok yüksek (>%85) — parse/format sorunu olabilir
    if toplam >= 20 and atlandi / toplam > 0.85:
        sorunlar.append(
            f"⚠️ Son 1 saatte mesajların %{int(atlandi/toplam*100)}'i atlandı "
            f"({atlandi}/{toplam}). Kaynak format değişmiş olabilir."
        )

    # 2. Ürün adı çıkarma başarısızlığı yüksek
    urun_yok = sayim.get("urun_adi_yok", 0)
    if urun_yok >= 10 and urun_yok / toplam > 0.5:
        sorunlar.append(
            f"⚠️ Mesajların %{int(urun_yok/toplam*100)}'inde ürün adı çıkmadı "
            f"({urun_yok}). Mesaj formatı tanınmıyor olabilir."
        )

    # 3. Gemini hata oranı yüksek
    g_basari = sayim.get("gemini_basari", 0)
    g_hata = sayim.get("gemini_hata", 0)
    if g_hata + g_basari >= 10 and g_hata / (g_hata + g_basari) > 0.5:
        sorunlar.append(
            f"⚠️ Gemini hata oranı yüksek (%{int(g_hata/(g_hata+g_basari)*100)}). "
            f"Yedek sisteme dönüldü ama API/kota kontrol edilmeli."
        )

    return sorunlar
