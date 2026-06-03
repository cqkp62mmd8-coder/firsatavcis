"""
═══════════════════════════════════════════════════════════════════════
SELF-HEALING — Model bozulmasını otomatik tespit edip onar (v22)

Sorun: Model zaman zaman zehirleniyor (zorlu Razer/Amazon TR döngüsü).
Çözüm: Son N paylaşımın kategorisini izle. Eğer hepsi aynı (örn. son
15 mesaj hep "Pet Shop") VE bu çeşitlilik kaybı sürerse → model bozulmuş.
Otomatik sıfırla, admin'e bildir.

Bu, kullanıcının elle '/model_sifirla' yazmasına gerek bırakmaz —
bot kendini kurtarır.
═══════════════════════════════════════════════════════════════════════
"""
import time
from collections import deque
from typing import Optional

import config
from utils.log import log

# Son N paylaşımın kategorileri (in-memory, restart'ta sıfırlanır)
_son_kategoriler: deque = deque(maxlen=50)
# En son ne zaman bozulma tespit edildi (spam önleme)
_son_iyilesme_ts: float = 0.0


def kayit_ekle(kategori: Optional[str]) -> None:
    """Bir paylaşımın kategorisini izleme deque'una ekle."""
    if kategori:
        _son_kategoriler.append(str(kategori))


def bozuk_mu() -> Optional[dict]:
    """Model bozulmuş mu? Son MODEL_TEKRAR_ESIK paylaşımın tamamı aynı
    kategorideyse → bozulmuş kabul edilir.

    Döner: bozuksa {'kategori': X, 'tekrar': N} dict, normalde None."""
    if not config.MODEL_IZLEME_AKTIF:
        return None
    esik = config.MODEL_TEKRAR_ESIK
    if len(_son_kategoriler) < esik:
        return None
    son = list(_son_kategoriler)[-esik:]
    benzersiz = set(son)
    # Hepsi aynı + 'genel' veya bilinen-yanlış kategorilerden değilse bozuk
    if len(benzersiz) == 1:
        kat = son[0]
        # 'genel' aynı çıkabilir normal (belirsiz tahminler), o bozulma değil
        if kat == "genel":
            return None
        return {"kategori": kat, "tekrar": esik}
    return None


def otomatik_onar(force: bool = False) -> Optional[dict]:
    """Model bozuksa otomatik sıfırla. Admin bildirimi için sonuç döner.

    Spam önleme: son onarımın üzerinden en az 1 saat geçmemişse atla."""
    global _son_iyilesme_ts
    bozuk = bozuk_mu()
    if not bozuk and not force:
        return None
    simdi = time.time()
    if not force and (simdi - _son_iyilesme_ts) < 600:
        return None   # spam önleme: 10 dakikada bir (v22.1: 1h→10dk)
    _son_iyilesme_ts = simdi
    try:
        from utils import urun_taniyici, ml_kategori
        urun_taniyici.sifirla()
        ml_kategori.sifirla()
        _son_kategoriler.clear()   # izleme geçmişi de sıfırlansın
        log("KRITIK", f"SELF-HEALING: Model bozulmuştu (son {bozuk['tekrar'] if bozuk else '?'} "
                      f"paylaşım: '{bozuk['kategori'] if bozuk else '?'}'), "
                      f"otomatik sıfırlandı")
        return {"onarildi": True, "tetik": bozuk}
    except Exception as e:
        log("UYARI", f"Self-healing onarım: {e}")
        return {"onarildi": False, "hata": str(e)}


def durum() -> dict:
    """İzleme durumu (admin /saglik için)."""
    return {
        "aktif":         config.MODEL_IZLEME_AKTIF,
        "esik":          config.MODEL_TEKRAR_ESIK,
        "izlenen_son":   len(_son_kategoriler),
        "bozuk_mu":      bozuk_mu() is not None,
        "son_kategoriler": list(_son_kategoriler)[-10:],
    }
