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
import hashlib
import hmac

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


def _panel_token() -> str:
    """PANEL_SIFRE'den türetilen oturum çerezi token'ı (parola değişince geçersiz)."""
    import config
    sifre = (getattr(config, "PANEL_SIFRE", "") or "")
    return hmac.new(b"firsatpulsu-panel-oturum", sifre.encode(),
                    hashlib.sha256).hexdigest()[:32]


def _yetkili_mi(headers: dict) -> bool:
    """Panel erişimi: PANEL_SIFRE boşsa açık; doluysa geçerli çerez gerekir."""
    import config
    if not getattr(config, "PANEL_SIFRE", ""):
        return True
    token = _panel_token()
    for parca in (headers.get("cookie", "") or "").split(";"):
        k, _, v = parca.strip().partition("=")
        if k == "fp_oturum" and hmac.compare_digest(v.strip(), token):
            return True
    return False


def _form_alan(govde: str, ad: str) -> str:
    """application/x-www-form-urlencoded gövdeden bir alanı çöz."""
    import urllib.parse
    try:
        return urllib.parse.parse_qs(govde).get(ad, [""])[0]
    except Exception:
        return ""


def _giris_html(hata: str = "") -> str:
    """Parola giriş sayfası (marka renkleriyle)."""
    hata_blok = (f"<p class='hata'>{hata}</p>" if hata else "")
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FırsatPulsu — Giriş</title><style>
:root{{--indigo:#4F46E5;--mor:#7C3AED;--cam:#06B6D4;--zemin:#0F172A;--kart:#1E293B;--metin:#E2E8F0;--soluk:#94A3B8}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;
background:radial-gradient(1200px 600px at 50% -10%,#1e1b4b,var(--zemin));
font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--metin)}}
.kart{{background:var(--kart);border:1px solid #334155;border-radius:20px;padding:32px 28px;
width:min(92vw,360px);box-shadow:0 20px 60px rgba(0,0,0,.4)}}
.amblem{{width:56px;height:56px;border-radius:16px;margin:0 auto 16px;
background:linear-gradient(135deg,var(--mor),var(--indigo) 55%,var(--cam));
display:grid;place-items:center;font-size:26px}}
h1{{font-size:20px;text-align:center;margin:0 0 4px}}
.alt{{text-align:center;color:var(--soluk);font-size:13px;margin:0 0 22px}}
label{{display:block;font-size:13px;color:var(--soluk);margin:0 0 6px}}
input{{width:100%;padding:12px 14px;border-radius:12px;border:1px solid #475569;
background:#0f172a;color:var(--metin);font-size:15px}}
input:focus{{outline:2px solid var(--indigo);border-color:transparent}}
button{{width:100%;margin-top:16px;padding:12px;border:0;border-radius:12px;cursor:pointer;
background:linear-gradient(135deg,var(--indigo),var(--cam));color:#fff;font-size:15px;font-weight:600}}
.hata{{background:#7f1d1d;color:#fecaca;padding:10px 12px;border-radius:10px;font-size:13px;margin:0 0 14px}}
</style></head><body>
<form class="kart" method="POST" action="/panel/giris">
<div class="amblem">⚡</div>
<h1>FırsatPulsu</h1><p class="alt">Yönetim paneli</p>
{hata_blok}
<label for="s">Parola</label>
<input id="s" name="sifre" type="password" autofocus autocomplete="current-password">
<button type="submit">Giriş yap</button>
</form></body></html>"""


def _yanit(kod: int, kod_metin: str, govde: bytes, tip: str = "text/html",
           ek_baslik: str = "") -> bytes:
    """HTTP yanıtı kur."""
    return (
        f"HTTP/1.1 {kod} {kod_metin}\r\n"
        f"Content-Type: {tip}; charset=utf-8\r\n"
        f"Content-Length: {len(govde)}\r\n"
        f"{ek_baslik}"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8") + govde


async def _istek_oku(reader: asyncio.StreamReader) -> tuple[str, str, dict, str]:
    """HTTP isteğini oku → (method, path, headers, body)."""
    veri = b""
    try:
        while b"\r\n\r\n" not in veri and len(veri) < 16384:
            parca = await asyncio.wait_for(reader.read(2048), timeout=5)
            if not parca:
                break
            veri += parca
    except Exception:
        pass
    if not veri:
        return "GET", "/", {}, ""
    try:
        bas, _, govde = veri.partition(b"\r\n\r\n")
        satirlar = bas.decode("utf-8", "ignore").split("\r\n")
        ilk = satirlar[0].split(" ")
        method = ilk[0] if ilk else "GET"
        path = ilk[1] if len(ilk) > 1 else "/"
        headers = {}
        for s in satirlar[1:]:
            if ":" in s:
                k, _, v = s.partition(":")
                headers[k.strip().lower()] = v.strip()
        try:
            clen = int(headers.get("content-length", "0"))
        except ValueError:
            clen = 0
        while len(govde) < clen and len(veri) < 65536:
            parca = await asyncio.wait_for(reader.read(2048), timeout=5)
            if not parca:
                break
            govde += parca
            veri += parca
        return method, path, headers, govde.decode("utf-8", "ignore")
    except Exception:
        return "GET", "/", {}, ""


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, kuyruk=None) -> None:
    """Tek istek işle."""
    try:
        method, yol, headers, govde = await _istek_oku(reader)
        kuyruk_size = kuyruk.qsize() if kuyruk else 0

        # POST /panel/giris — parola kontrolü → oturum çerezi
        if method == "POST" and yol.startswith("/panel/giris"):
            import config
            girilen = _form_alan(govde, "sifre")
            dogru = getattr(config, "PANEL_SIFRE", "")
            if dogru and hmac.compare_digest(girilen, dogru):
                cerez = (f"Set-Cookie: fp_oturum={_panel_token()}; HttpOnly; "
                         f"Path=/; Max-Age=604800; SameSite=Lax\r\n")
                cevap = _yanit(302, "Found", b"", ek_baslik="Location: /panel\r\n" + cerez)
            else:
                cevap = _yanit(200, "OK", _giris_html("Parola hatalı.").encode("utf-8"))

        elif yol.startswith("/health"):
            body = _durum_json(kuyruk_size)
            durum_obj = json.loads(body.decode())
            kod = 200 if durum_obj["saglikli"] else 503
            cevap = _yanit(kod, "OK" if kod == 200 else "Service Unavailable",
                           body, tip="application/json")

        elif yol.startswith("/panel"):
            # v23.40 — Parola korumalı. PANEL_SIFRE boşsa açık (eski davranış).
            if not _yetkili_mi(headers):
                cevap = _yanit(200, "OK", _giris_html().encode("utf-8"))
            else:
                cevap = _yanit(200, "OK", _panel_html(kuyruk_size).encode("utf-8"))

        elif yol.startswith("/git/"):
            # Tıklama takibi: kısa kimliği çöz, kaydet, affiliate URL'ye 302.
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
                cevap = _yanit(302, "Found", b"", ek_baslik=f"Location: {hedef}\r\n")
            else:
                cevap = _yanit(404, "Not Found", b"Link bulunamadi.", tip="text/plain")

        else:
            html = (b"<h1>FirsatPulsu Bot</h1><p>Calisiyor. "
                    b"<a href='/health'>Health</a> | <a href='/panel'>Panel</a></p>")
            cevap = _yanit(200, "OK", html)

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
