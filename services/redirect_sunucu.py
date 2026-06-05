"""
═══════════════════════════════════════════════════════════════════════
REDIRECT SUNUCUSU (v23.18) — DORMANT

Tıklama takibi için küçük HTTP sunucusu. Buton linki
'<BASE_URL>/git/<kisa_id>' şeklindedir; kullanıcı tıklayınca buraya gelir,
tıklama kaydedilir, sonra gerçek (affiliate) URL'ye 302 ile yönlendirilir.

ÖNEMLİ: Bu sunucu SADECE config.TIKLAMA_TAKIP_AKTIF=True iken başlatılır
(main.py kontrol eder). Kapalıyken hiç import edilmez, port açılmaz —
bot bugünküyle birebir aynı çalışır.

aiohttp gerektirir (requirements.txt'e eklendi, kapalıyken kullanılmaz).
═══════════════════════════════════════════════════════════════════════
"""
from utils.log import log


async def sunucu_baslat(port: int = 8080):
    """Redirect sunucusunu başlat. Sadece tıklama takibi aktifken çağrılır."""
    try:
        from aiohttp import web
    except ImportError:
        log("UYARI", "aiohttp kurulu değil — redirect sunucusu başlatılamadı. "
                     "requirements.txt'e aiohttp ekleyip yeniden deploy edin.")
        return None

    from utils import tiklama

    async def _git(request):
        kid = request.match_info.get("kid", "")
        bilgi = tiklama.hedef_bul(kid)
        if not bilgi or not bilgi.get("hedef_url"):
            return web.Response(text="Link bulunamadı.", status=404)
        # Tıklamayı kaydet (hata olsa bile yönlendir)
        try:
            tiklama.tiklama_kaydet(kid)
        except Exception:
            pass
        raise web.HTTPFound(bilgi["hedef_url"])   # 302 redirect

    async def _saglik(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/git/{kid}", _git)
    app.router.add_get("/", _saglik)
    app.router.add_get("/saglik", _saglik)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log("SISTEM", f"🔗 Redirect sunucusu başladı (port {port}) — tıklama takibi AKTİF")
    return runner
