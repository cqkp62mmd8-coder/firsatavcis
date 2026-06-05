"""
═══════════════════════════════════════════════════════════════════════
REDIRECT SUNUCUSU — v23.24'TE KULLANIM DIŞI

Tıklama redirect'i artık AYRI sunucu değil, health sunucusunun içinde
(/git/ yolu — services/health.py). Sebep: Railway genel alan adını tek
public porta yönlendirir; ayrı port açmak 'address already in use'
(Errno 98) hatasına yol açıyordu.

Bu dosya geriye dönük uyumluluk için duruyor; çağrılırsa hiçbir şey
başlatmaz, sadece bilgilendirir.
═══════════════════════════════════════════════════════════════════════
"""
from utils.log import log


async def sunucu_baslat(port: int = 8080):
    """KULLANIM DIŞI — redirect health sunucusuna taşındı (/git/)."""
    log("BILGI", "redirect_sunucu kullanım dışı — redirect health sunucusunda (/git/)")
    return None
