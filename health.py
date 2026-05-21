"""
#6 — HTTP health endpoint.
Basit aiohttp olmadan, sade asyncio TCP server.
UptimeRobot bunu kontrol eder, ölü ise sana SMS atar.

Endpoint:
  GET /health → 200 + JSON durum
  GET /       → kısa HTML sayfası
"""
import asyncio
import json

from utils.log import log, simdi_tr

_baslangic_zamani: float = 0.0
_son_mesaj_zaman: float = 0.0
_paylasilan_sayisi: int = 0


def son_mesaj_kaydet() -> None:
    """Bot mesaj attığında çağrılır — health check için."""
    global _son_mesaj_zaman, _paylasilan_sayisi
    _son_mesaj_zaman = simdi_tr().timestamp()
    _paylasilan_sayisi += 1


def _durum_json(kuyruk_size: int = 0) -> bytes:
    simdi_ts = simdi_tr().timestamp()
    uptime = int(simdi_ts - _baslangic_zamani) if _baslangic_zamani else 0
    son_mesaj_gecen = int(simdi_ts - _son_mesaj_zaman) if _son_mesaj_zaman else None

    saglikli = True
    sebep = "ok"
    # Eğer 4 saatten beri mesaj yoksa unhealthy
    if son_mesaj_gecen is not None and son_mesaj_gecen > 14400:
        saglikli = False
        sebep = f"son mesajdan {son_mesaj_gecen//3600}sa geçti"

    obj = {
        "saglikli": saglikli,
        "sebep":    sebep,
        "uptime_sn": uptime,
        "uptime_dakika": uptime // 60,
        "son_mesaj_sn_once": son_mesaj_gecen,
        "paylasilan_toplam": _paylasilan_sayisi,
        "kuyruk_size": kuyruk_size,
        "zaman": simdi_tr().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, kuyruk=None) -> None:
    """Tek istek işle."""
    try:
        veri = await asyncio.wait_for(reader.read(1024), timeout=5)
        if not veri:
            return
        ilk_satir = veri.decode("utf-8", errors="ignore").split("\r\n")[0]
        # "GET /health HTTP/1.1"
        try:
            yol = ilk_satir.split(" ")[1]
        except IndexError:
            yol = "/"

        kuyruk_size = kuyruk.qsize() if kuyruk else 0

        if yol.startswith("/health"):
            body = _durum_json(kuyruk_size)
            durum_obj = json.loads(body.decode())
            kod = 200 if durum_obj["saglikli"] else 503
            kod_metin = "OK" if kod == 200 else "Service Unavailable"
            cevap = (
                f"HTTP/1.1 {kod} {kod_metin}\r\n"
                f"Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("utf-8") + body
        else:
            html = b"<h1>FirsatPulsu Bot</h1><p>Calisiyor. <a href='/health'>Health check</a></p>"
            cevap = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(html)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("utf-8") + html

        writer.write(cevap)
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def baslat(kuyruk, port: int = 8080) -> None:
    """Health server'ı port'ta dinlet."""
    global _baslangic_zamani
    _baslangic_zamani = simdi_tr().timestamp()

    async def handler(r, w):
        await _handle(r, w, kuyruk=kuyruk)

    server = await asyncio.start_server(handler, "0.0.0.0", port)
    log("OK", f"Health endpoint başladı → 0.0.0.0:{port}/health")
    async with server:
        await server.serve_forever()
