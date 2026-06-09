"""
cok_kiraci/panel.py — Müşteri web paneli (Faz 4) — SUNUCUDAN BAĞIMSIZ çekirdek.

Müşteri lisans anahtarıyla giriş yapar; kanalını, kategorilerini, min indirimini,
şablonunu ve affiliate etiketlerini yönetir. Bu modül oturum + sayfa (HTML) + form
işleme MANTIĞINI içerir ve bir HTTP sunucusuna bağlanır (VDS'te FastAPI ya da mevcut
hafif sunucu). Mantık burada test edilir; sunucu katmanı ince kalır.

Çerez: fp_musteri=<lisans_key>.<imza>  (müşteriyi tanımlar, HMAC ile kurcalanamaz).
"""
import hashlib
import hmac
import html

from cok_kiraci import musteri, sablonlar, affiliate
from utils.log import simdi_tr
from datetime import datetime

_OTURUM_TUZ = b"firsatpulsu-musteri-oturum"

# Affiliate alanları (panelde gösterilen platformlar)
_PLATFORMLAR = [("amazon", "Amazon"), ("trendyol", "Trendyol"),
                ("hepsiburada", "Hepsiburada"), ("n11", "n11")]


# ── oturum ────────────────────────────────────────────────────────
def _imza(lisans_key: str) -> str:
    return hmac.new(_OTURUM_TUZ, lisans_key.encode(), hashlib.sha256).hexdigest()[:24]


def oturum_token(lisans_key: str) -> str:
    return f"{lisans_key}.{_imza(lisans_key)}"


def oturum_coz(token: str):
    """Çerezi doğrula → lisans anahtarı; geçersizse None."""
    if not token or "." not in token:
        return None
    key, _, imza = token.rpartition(".")
    if key and hmac.compare_digest(imza, _imza(key)):
        return key
    return None


def cerezden_musteri(token: str):
    """Çerez → aktif müşteri (oturum + abonelik kontrolü); yoksa None."""
    key = oturum_coz(token)
    return musteri.giris(key) if key else None


# ── form işleme ──────────────────────────────────────────────────
def form_isle(musteri_id: int, form: dict) -> None:
    """Ayar formundan gelen alanları kaydet."""
    kwargs = {}
    if form.get("kanal") is not None:
        kwargs["kanal"] = form.get("kanal", "")
    if form.get("min_indirim") not in (None, ""):
        try:
            kwargs["min_indirim"] = int(form["min_indirim"])
        except ValueError:
            pass
    if form.get("kategoriler") is not None:
        kwargs["kategoriler"] = [k.strip() for k in form["kategoriler"].split(",") if k.strip()]
    if form.get("sablon"):
        kwargs["sablon"] = form["sablon"]
    if "aktif" in form:
        kwargs["aktif"] = form.get("aktif") in ("1", "on", "true", "evet")
    if kwargs:
        musteri.ayar_kaydet(musteri_id, **kwargs)
    for kod, _ad in _PLATFORMLAR:
        v = form.get(f"aff_{kod}")
        if v is not None:
            musteri.affiliate_kaydet(musteri_id, kod, v)


# ── sayfalar (HTML) ──────────────────────────────────────────────
_STIL = """
:root{--indigo:#4F46E5;--mor:#7C3AED;--cam:#06B6D4;--zemin:#0F172A;--kart:#1E293B;--metin:#E2E8F0;--soluk:#94A3B8}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(1200px 600px at 50% -10%,#1e1b4b,var(--zemin));font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--metin)}
.sar{max-width:560px;margin:0 auto;padding:24px 16px}
.amblem{width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,var(--mor),var(--indigo) 55%,var(--cam));display:grid;place-items:center;font-size:22px}
.kart{background:var(--kart);border:1px solid #334155;border-radius:18px;padding:22px;margin:16px 0;box-shadow:0 12px 40px rgba(0,0,0,.3)}
h1{font-size:20px;margin:8px 0 2px}h2{font-size:15px;color:var(--cam);margin:0 0 14px;text-transform:uppercase;letter-spacing:.04em}
label{display:block;font-size:13px;color:var(--soluk);margin:12px 0 6px}
input,select{width:100%;padding:11px 13px;border-radius:11px;border:1px solid #475569;background:#0f172a;color:var(--metin);font-size:15px}
input:focus,select:focus{outline:2px solid var(--indigo);border-color:transparent}
button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:11px;cursor:pointer;background:linear-gradient(135deg,var(--indigo),var(--cam));color:#fff;font-size:15px;font-weight:600}
.ust{display:flex;align-items:center;gap:12px}.rozet{margin-left:auto;font-size:12px;color:var(--soluk)}
.ipucu{font-size:12px;color:var(--soluk);margin-top:4px}.hata{background:#7f1d1d;color:#fecaca;padding:10px 12px;border-radius:10px;font-size:13px;margin:0 0 14px}
.cikis{display:inline-block;margin-top:8px;color:var(--soluk);font-size:13px;text-decoration:none}
.pasif{color:#fca5a5}
"""


def giris_html(hata: str = "") -> str:
    hata_blok = f"<p class='hata'>{html.escape(hata)}</p>" if hata else ""
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>FırsatPulsu — Panel</title>
<style>{_STIL}</style></head><body><div class="sar"><div class="kart" style="max-width:360px;margin:12vh auto 0">
<div class="amblem" style="margin:0 auto 14px">⚡</div>
<h1 style="text-align:center">FırsatPulsu</h1>
<p style="text-align:center;color:var(--soluk);font-size:13px;margin:0 0 20px">Müşteri paneli</p>
{hata_blok}
<form method="POST" action="/musteri/giris">
<label for="l">Lisans anahtarı</label>
<input id="l" name="lisans" placeholder="FP-XXXX-XXXX-XXXX" autofocus autocomplete="off">
<button type="submit">Giriş yap</button></form>
</div></div></body></html>"""


def _kalan_gun(bitis: str) -> str:
    try:
        k = (datetime.fromisoformat(bitis) - simdi_tr()).days
        return f"{k} gün kaldı" if k >= 0 else "süresi doldu"
    except Exception:
        return ""


def panel_html(m: dict, ayar: dict, affiliateler: dict) -> str:
    kanal = html.escape(ayar.get("kanal", "") or "")
    min_ind = int(ayar.get("min_indirim", 20) or 20)
    kategoriler = html.escape(", ".join(ayar.get("kategoriler", []) or []))
    secili_sablon = ayar.get("sablon", "klasik")
    yayinda = ayar.get("aktif", True)
    plan = html.escape(m.get("plan", "") or "")
    kalan = _kalan_gun(m.get("bitis", ""))

    sablon_secenek = "".join(
        f"<option value='{html.escape(s)}'{' selected' if s == secili_sablon else ''}>{html.escape(s)}</option>"
        for s in sablonlar.sablon_listesi()
    )
    aff_alan = ""
    for kod, ad in _PLATFORMLAR:
        deger = html.escape(affiliateler.get(kod, "") or "")
        destek = affiliate.desteklenen_platform(kod)
        not_metin = "" if destek else " <span class='pasif'>(ağ bağlantısı gerekli)</span>"
        aff_alan += (f"<label>{ad} etiketi{not_metin}</label>"
                     f"<input name='aff_{kod}' value='{deger}' autocomplete='off'>")

    yayin_secenek = ("<option value='1'{}>Açık</option>"
                     "<option value='0'{}>Duraklatıldı</option>").format(
        " selected" if yayinda else "", "" if yayinda else " selected")

    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>FırsatPulsu — Panel</title>
<style>{_STIL}</style></head><body><div class="sar">
<div class="ust"><div class="amblem">⚡</div><div><h1>FırsatPulsu</h1>
<div class="rozet">Plan: {plan or '—'} · {kalan}</div></div></div>

<form method="POST" action="/musteri/ayar">
<div class="kart"><h2>Kanal ve yayın</h2>
<label for="kanal">Telegram kanalın</label>
<input id="kanal" name="kanal" value="{kanal}" placeholder="@kanaladi">
<p class="ipucu">Platform botunu kanalına yönetici olarak eklemeyi unutma.</p>
<label for="aktif">Yayın durumu</label>
<select id="aktif" name="aktif">{yayin_secenek}</select></div>

<div class="kart"><h2>Filtreler</h2>
<label for="min">Minimum indirim (%)</label>
<input id="min" name="min_indirim" type="number" min="0" max="99" value="{min_ind}">
<label for="kat">Kategoriler</label>
<input id="kat" name="kategoriler" value="{kategoriler}" placeholder="elektronik, moda (boş = tümü)">
<p class="ipucu">Virgülle ayır. Boş bırakırsan tüm kategoriler gelir.</p>
<label for="sab">Gönderi şablonu</label>
<select id="sab" name="sablon">{sablon_secenek}</select></div>

<div class="kart"><h2>Affiliate etiketleri</h2>
{aff_alan}
<p class="ipucu">Linklerin kazancı sana ait. Şu an otomatik enjeksiyon yalnız Amazon'da çalışır.</p></div>

<button type="submit">Ayarları kaydet</button></form>
<a class="cikis" href="/musteri/cikis">Çıkış yap</a>
</div></body></html>"""
