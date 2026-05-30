"""
═══════════════════════════════════════════════════════════════════════
RETRY — Akıllı yeniden deneme yardımcıları (v22)

Ağ/Telegram/DB hatalarında çökmek yerine akıllı yeniden dene:
  • Exponential backoff (her denemede süre 2'ye katlanır)
  • Belirli hata tiplerinde yeniden dene (timeout, connection)
  • Kalıcı hatalarda (auth, syntax) hemen vazgeç
  • Toplam max süre sınırı (sonsuz döngüye girme)
═══════════════════════════════════════════════════════════════════════
"""
import asyncio
import time
from typing import Callable, Any, Iterable

from utils.log import log


# Geçici hatalar (yeniden dene)
GECICI_HATALAR: tuple = (
    ConnectionError, TimeoutError, OSError,
    asyncio.TimeoutError,
)

# Kalıcı hatalar (vazgeç)
KALICI_HATALAR: tuple = (
    SyntaxError, AttributeError, NameError, TypeError, KeyError,
)


async def deneyerek(
    fonksiyon: Callable,
    *args,
    max_deneme: int = 3,
    baslangic_bekleme: float = 1.0,
    max_bekleme: float = 30.0,
    etiket: str = "işlem",
    **kwargs,
) -> Any:
    """Async fonksiyonu hata durumunda exponential backoff ile yeniden dene.

    Kullanım:
        sonuc = await deneyerek(
            client.send_message, hedef, metin,
            max_deneme=3, etiket="mesaj gönder"
        )
    """
    bekleme = baslangic_bekleme
    son_hata = None
    for deneme in range(1, max_deneme + 1):
        try:
            return await fonksiyon(*args, **kwargs)
        except KALICI_HATALAR as e:
            # Kod/yapı hatası → tekrar denemenin anlamı yok
            log("HATA", f"{etiket}: kalıcı hata, yeniden denenmedi ({type(e).__name__}: {e})")
            raise
        except Exception as e:
            son_hata = e
            if deneme == max_deneme:
                log("UYARI", f"{etiket}: {max_deneme} deneme başarısız ({type(e).__name__}: {e})")
                raise
            # Geçici hata mı?
            is_gecici = isinstance(e, GECICI_HATALAR) or "FloodWait" in type(e).__name__
            if not is_gecici and deneme >= 2:
                # 2 denemede de farklı bir hata → vazgeç
                raise
            log("BILGI", f"{etiket}: deneme #{deneme} başarısız ({type(e).__name__}), "
                          f"{bekleme:.1f}s sonra tekrar")
            await asyncio.sleep(bekleme)
            bekleme = min(bekleme * 2, max_bekleme)
    # Buraya teorik olarak ulaşılmaz
    if son_hata:
        raise son_hata


def deneyerek_sync(
    fonksiyon: Callable,
    *args,
    max_deneme: int = 3,
    baslangic_bekleme: float = 0.5,
    max_bekleme: float = 10.0,
    etiket: str = "işlem",
    **kwargs,
) -> Any:
    """Senkron sürüm — DB/dosya işlemleri için."""
    bekleme = baslangic_bekleme
    for deneme in range(1, max_deneme + 1):
        try:
            return fonksiyon(*args, **kwargs)
        except KALICI_HATALAR as e:
            log("HATA", f"{etiket}: kalıcı hata ({type(e).__name__}: {e})")
            raise
        except Exception as e:
            if deneme == max_deneme:
                log("UYARI", f"{etiket}: {max_deneme} deneme başarısız ({e})")
                raise
            time.sleep(bekleme)
            bekleme = min(bekleme * 2, max_bekleme)
