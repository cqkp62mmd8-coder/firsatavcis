"""
cok_kiraci/havuz.py — Ortak fırsat havuzu + müşteri-başına yönlendirme (Faz 2).

Kaynaklardan (feed/kazıma — KAYNAK-BAĞIMSIZ) toplanan fırsatlar merkezi
'firsatlar' tablosunda tutulur. Her müşteri için ayarına göre (kategori, min
indirim) filtrelenip HENÜZ O MÜŞTERİYE gönderilmemiş olanlar seçilir
(gonderim_log ile). Havuza yazan kaynak önemli değil; tek arayüz firsat_ekle().

Fırsat sözlüğü (firsat_ekle girdisi) beklenen alanlar:
    baslik, urun_url, gorsel_url, magaza, kategori, alt_kategori,
    fiyat, eski_fiyat, indirim, urun_anahtar (ops.), veri (ops. dict)
"""
import json
import hashlib
from datetime import timedelta

from utils import db
from cok_kiraci import depo
from utils.log import simdi_tr


def anahtar_uret(magaza: str, url: str) -> str:
    """Ürün adresinden kararlı kimlik üret (urun_anahtar verilmediyse)."""
    temel = (url or "").split("?")[0].strip().lower().rstrip("/")
    h = hashlib.sha1(temel.encode("utf-8")).hexdigest()[:16]
    return f"{(magaza or '').lower()}:{h}"


def firsat_ekle(firsat: dict) -> bool:
    """Fırsatı havuza ekle/güncelle. Havuz-seviyesi tekilleştirme urun_anahtar ile.
    Yeni eklendiyse True; zaten varsa (fiyat/başlık güncellenir, ilk görülme korunur) False."""
    depo.kur()
    anahtar = (firsat.get("urun_anahtar")
               or anahtar_uret(firsat.get("magaza"), firsat.get("urun_url")))
    veri = firsat.get("veri", {})
    if not isinstance(veri, str):
        veri = json.dumps(veri, ensure_ascii=False)
    alanlar = (
        firsat.get("baslik", "") or "",
        firsat.get("urun_url", "") or "",
        firsat.get("gorsel_url", "") or "",
        (firsat.get("magaza", "") or "").lower(),
        firsat.get("kategori", "") or "",
        firsat.get("alt_kategori", "") or "",
        firsat.get("fiyat"),
        firsat.get("eski_fiyat"),
        int(firsat.get("indirim", 0) or 0),
        veri,
    )
    with db.cursor() as c:
        c.execute("SELECT id FROM firsatlar WHERE urun_anahtar=?", (anahtar,))
        if c.fetchone():
            c.execute(
                "UPDATE firsatlar SET baslik=?, urun_url=?, gorsel_url=?, magaza=?, "
                "kategori=?, alt_kategori=?, fiyat=?, eski_fiyat=?, indirim=?, veri=? "
                "WHERE urun_anahtar=?",
                (*alanlar, anahtar),
            )
            return False
        c.execute(
            "INSERT INTO firsatlar (urun_anahtar, baslik, urun_url, gorsel_url, magaza, "
            "kategori, alt_kategori, fiyat, eski_fiyat, indirim, veri, eklendi) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (anahtar, *alanlar, simdi_tr().isoformat()),
        )
        return True


def musteri_icin_firsatlar(musteri_id: int, ayar: dict, limit: int = 20) -> list:
    """Müşterinin ayarına uyan ve henüz ona gönderilmemiş fırsatları döndür (yeniden eskiye).

    ayar: musteri.ayar_getir() çıktısı — {min_indirim, kategoriler, ...}.
    kategoriler boş liste ise tüm kategoriler kabul edilir.
    """
    depo.kur()
    min_ind = int(ayar.get("min_indirim", 0) or 0)
    kategoriler = ayar.get("kategoriler") or []
    sonuc = []
    with db.cursor() as c:
        c.execute(
            "SELECT * FROM firsatlar WHERE indirim >= ? ORDER BY id DESC LIMIT ?",
            (min_ind, max(limit * 5, 100)),
        )
        for r in c.fetchall():
            d = dict(r)
            if kategoriler and d.get("kategori") not in kategoriler:
                continue
            if depo.gonderildi_mi(musteri_id, d["urun_anahtar"]):
                continue
            sonuc.append(d)
            if len(sonuc) >= limit:
                break
    return sonuc


def son_firsatlar(limit: int = 50) -> list:
    depo.kur()
    with db.cursor() as c:
        c.execute("SELECT * FROM firsatlar ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]


def firsat_sayisi() -> int:
    depo.kur()
    with db.cursor() as c:
        c.execute("SELECT COUNT(*) AS n FROM firsatlar")
        return c.fetchone()["n"]


def eski_temizle(max_yas_sn: int) -> int:
    """Havuzdan max_yas_sn saniyeden eski fırsatları sil; silinen sayıyı döndür."""
    depo.kur()
    esik = (simdi_tr() - timedelta(seconds=max_yas_sn)).isoformat()
    with db.cursor() as c:
        c.execute("DELETE FROM firsatlar WHERE eklendi < ?", (esik,))
        return c.rowcount
