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


def _panel_html(kuyruk_size: int = 0) -> str:
    """v23.22 — Kapsamlı canlı izleme paneli (telefon tarayıcısı için).
    Tüm detaylı istatistikleri yansıtır: paylaşım, kalite, kategori, mağaza,
    oylar, saatler, abonelikler, tıklama (aktifse), Gemini, sistem sağlığı."""
    import config
    veri = {}

    def _topla(ad, fn):
        try:
            veri[ad] = fn()
        except Exception:
            veri[ad] = {}

    _topla("dup", lambda: __import__("utils.duplicate", fromlist=["istatistik"]).istatistik())
    _topla("kalite", lambda: __import__("utils.kalite", fromlist=["istatistik"]).istatistik())
    _topla("gemini", lambda: __import__("utils.gemini", fromlist=["istatistik"]).istatistik())
    _topla("sh", lambda: __import__("utils.self_heal", fromlist=["durum"]).durum())
    _topla("kk", lambda: __import__("utils.karakutu", fromlist=["ozet"]).ozet())
    _topla("ist", lambda: __import__("utils.cache", fromlist=["ist_yukle"]).ist_yukle())

    dup = veri.get("dup", {})
    kal = veri.get("kalite", {})
    gem = veri.get("gemini", {})
    sh = veri.get("sh", {})
    kk = veri.get("kk", {})
    ist = veri.get("ist", {})

    # Ek istatistikler (hata olursa boş geç)
    beg_kat, oy, saatler, abone, tik, uptime_str = [], {}, [], {}, {}, "—"
    try:
        from utils import segment
        beg_kat = segment.begenilen_kategoriler(30, limit=6) or []
        oy = segment.oy_ozeti(7) or {}
    except Exception:
        pass
    try:
        from utils import zamanlama
        saatler = zamanlama.en_iyi_saatler(4) or []
    except Exception:
        pass
    try:
        from utils import istek
        abone = istek.kategori_istatistik() or {}
    except Exception:
        pass
    try:
        if getattr(config, "TIKLAMA_TAKIP_AKTIF", False):
            from utils import tiklama
            tik = tiklama.istatistik(7) or {}
    except Exception:
        pass
    try:
        simdi_ts = simdi_tr().timestamp()
        if _baslangic_zamani:
            us = int(simdi_ts - _baslangic_zamani)
            uptime_str = f"{us // 3600}sa {(us % 3600) // 60}dk"
    except Exception:
        pass

    surum = getattr(config, "SURUM", "?")
    sh_durum = "✅ Normal" if not sh.get("bozuk_mu") else "⚠️ Bozuk"
    gem_durum = f"{gem.get('basari', 0)}/{gem.get('istek', 0)}" if gem else "—"
    bugun = simdi_tr().strftime("%Y-%m-%d")
    bugun_pay = ist.get("gunluk", {}).get(bugun, 0)
    toplam_pay = ist.get("toplam", 0)

    # ── Mağaza dağılımı (ilk 6) ──
    magazalar = ist.get("magazalar", {}) or {}
    mag_sirali = sorted(magazalar.items(), key=lambda x: x[1], reverse=True)[:6]
    mag_html = "".join(
        f"<div class='row'><span>{_kacis(m)}</span><b>{n}</b></div>"
        for m, n in mag_sirali) or "<div class='row'><span>Henüz veri yok</span></div>"

    # ── Kategori dağılımı (paylaşılan, ilk 6) ──
    kategoriler = ist.get("kategoriler", {}) or {}
    kat_sirali = sorted(kategoriler.items(), key=lambda x: x[1], reverse=True)[:6]
    kat_html = "".join(
        f"<div class='row'><span>{_kacis(k)}</span><b>{n}</b></div>"
        for k, n in kat_sirali) or "<div class='row'><span>Henüz veri yok</span></div>"

    # ── Beğenilen kategoriler (oy ile) ──
    beg_html = "".join(
        f"<div class='row'><span>{_kacis(b.get('kategori','?'))}</span><b>👍 {b.get('sayi',0)}</b></div>"
        for b in beg_kat) or "<div class='row'><span>Henüz oy yok</span></div>"

    # ── En etkili saatler (en_iyi_saatler → [(saat, oran, paylasim), ...]) ──
    def _saat_no(x):
        return x[0] if isinstance(x, (list, tuple)) else x
    saat_html = ", ".join(f"{_saat_no(h):02d}:00" for h in saatler) if saatler else "—"

    # ── Tıklama bloğu (aktifse) ──
    tik_blok = ""
    if tik:
        en_cok = tik.get("en_cok", [])[:5]
        en_html = "".join(
            f"<div class='row'><span>{_kacis((a or '?')[:28])}</span><b>{n}</b></div>"
            for a, n in en_cok) or "<div class='row'><span>Henüz tıklama yok</span></div>"
        tik_blok = f"""
<div class="c full"><div class="l">🔗 Tıklama — Toplam (7g): {tik.get('toplam',0)}</div>
<div class="list">{en_html}</div></div>"""

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>FırsatPulsu Panel</title>
<style>
body{{font-family:-apple-system,system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:16px;max-width:680px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px}}
h2{{font-size:13px;color:#9aa;margin:18px 0 8px;text-transform:uppercase;letter-spacing:.5px}}
.s{{color:#888;font-size:12px;margin-bottom:16px}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.c{{background:#1a1d24;border-radius:12px;padding:14px}}
.c .l{{color:#999;font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
.c .v{{font-size:22px;font-weight:700;margin-top:4px}}
.full{{grid-column:1/3}}
.list{{margin-top:8px}}
.row{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #262a33;font-size:14px}}
.row:last-child{{border-bottom:none}}
.row b{{color:#4ade80}}
.ok{{color:#4ade80}}.warn{{color:#fbbf24}}
</style></head><body>
<h1>🤖 FırsatPulsu</h1>
<div class="s">{surum} · 30sn'de bir yenilenir</div>

<h2>📊 Özet</h2>
<div class="g">
<div class="c"><div class="l">Bugün Paylaşım</div><div class="v">{bugun_pay}</div></div>
<div class="c"><div class="l">Toplam Paylaşım</div><div class="v">{toplam_pay}</div></div>
<div class="c"><div class="l">Kuyruk</div><div class="v">{kuyruk_size}</div></div>
<div class="c"><div class="l">Çalışma Süresi</div><div class="v" style="font-size:16px">{uptime_str}</div></div>
<div class="c"><div class="l">Ort. Kalite</div><div class="v">{kal.get('ortalama','—')}</div></div>
<div class="c"><div class="l">Son 24s Tekrar</div><div class="v">{dup.get('son_24_saat','—')}</div></div>
</div>

<h2>🤖 Sistem</h2>
<div class="g">
<div class="c"><div class="l">Model</div><div class="v" style="font-size:16px">{sh_durum}</div></div>
<div class="c"><div class="l">Gemini (başarı/istek)</div><div class="v" style="font-size:18px">{gem_durum}</div></div>
<div class="c"><div class="l">Kalite Ölçüm</div><div class="v">{kal.get('toplam','—')}</div></div>
<div class="c"><div class="l">Olay (kara kutu)</div><div class="v">{kk.get('toplam','—')}</div></div>
<div class="c"><div class="l">Toplam Tekrar Kaydı</div><div class="v">{dup.get('toplam_kayit','—')}</div></div>
<div class="c"><div class="l">👍 / 👎 (7g)</div><div class="v" style="font-size:18px">{oy.get('toplam_iyi',0)} / {oy.get('toplam_kotu',0)}</div></div>
</div>

<h2>🏪 Mağaza Dağılımı</h2>
<div class="c full"><div class="list">{mag_html}</div></div>

<h2>📂 Kategori Dağılımı (paylaşılan)</h2>
<div class="c full"><div class="list">{kat_html}</div></div>

<h2>🏆 En Beğenilen Kategoriler (oy)</h2>
<div class="c full"><div class="list">{beg_html}</div></div>

<h2>⏰ Etkileşim & Abonelik</h2>
<div class="g">
<div class="c"><div class="l">En Etkili Saatler</div><div class="v" style="font-size:15px">{saat_html}</div></div>
<div class="c"><div class="l">Kategori Aboneleri</div><div class="v">{abone.get('abone_sayisi',0)}</div></div>
</div>
{tik_blok}
</body></html>"""


def _kacis(s) -> str:
    """HTML kaçışı (panelde mağaza/kategori adları güvenli görünsün)."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


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

    # Model durumları (gözlemlenebilirlik — opsiyonel, hata olursa atla)
    try:
        from utils import urun_taniyici, ml_kategori
        obj["modeller"] = {
            "urun_taniyici": urun_taniyici.istatistik(),
            "ml_kategori_egitim_bekliyor": ml_kategori.egitim_bekliyor_mu(),
        }
        from utils import gemini
        obj["gemini"] = gemini.istatistik()
    except Exception:
        pass

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
        elif yol.startswith("/panel"):
            # v22.7 — Sistem 11: Canlı izleme paneli (telefondan tarayıcıyla)
            html = _panel_html(kuyruk_size).encode("utf-8")
            cevap = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(html)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("utf-8") + html
        elif yol.startswith("/git/"):
            # v23.24 — Tıklama takibi: ayrı redirect sunucusu YERİNE buraya
            # eklendi (Railway tek public porta yönlendirir, port çakışması
            # 'address already in use' hatası bu yüzden çıkıyordu). Kısa
            # kimliği çöz, tıklamayı kaydet, gerçek (affiliate) URL'ye 302 at.
            kid = yol[len("/git/"):].split("?")[0].split("#")[0].strip("/")
            hedef = None
            try:
                from utils import tiklama
                bilgi = tiklama.hedef_bul(kid)
                if bilgi and bilgi.get("hedef_url"):
                    hedef = bilgi["hedef_url"]
                    try:
                        tiklama.tiklama_kaydet(kid)
                    except Exception:
                        pass
            except Exception:
                pass
            if hedef:
                cevap = (
                    f"HTTP/1.1 302 Found\r\n"
                    f"Location: {hedef}\r\n"
                    f"Content-Length: 0\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode("utf-8")
            else:
                body = b"Link bulunamadi."
                cevap = (
                    f"HTTP/1.1 404 Not Found\r\n"
                    f"Content-Type: text/plain; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode("utf-8") + body
        else:
            html = b"<h1>FirsatPulsu Bot</h1><p>Calisiyor. <a href='/health'>Health</a> | <a href='/panel'>Panel</a></p>"
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
