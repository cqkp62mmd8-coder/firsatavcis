"""
═══════════════════════════════════════════════════════════════════════
ETKİLEŞİM SİSTEMİ (v22.11 — Sistem 9)

Kanalı büyütecek etkileşim özellikleri:
  • Haftanın en beğenilen ürünü (en çok 🔥 oy alan)
  • Kategori bazlı ilgi raporu (hangi kategori daha çok oy alıyor)
  • En aktif oyveren kullanıcılar (gelecekte rozet için temel)

Mevcut oy verisi (kullanici_tikla + mesaj_meta) üzerinden çalışır,
yeni veri toplamaz — var olanı değerlendirir.
═══════════════════════════════════════════════════════════════════════
"""
import time
from utils import db
from utils.log import log


def haftanin_urunu(gun: int = 7) -> dict | None:
    """Son N günde en çok 🔥 oy alan ürünü bul."""
    try:
        kesim = int(time.time()) - gun * 86400
        with db.cursor() as c:
            r = c.execute("""
                SELECT m.urun_adi, m.kategori, m.magaza, COUNT(*) as oy
                FROM kullanici_tikla t
                JOIN mesaj_meta m ON t.mesaj_id = m.mesaj_id
                WHERE t.oy_turu='good' AND t.ts >= ? AND m.urun_adi != ''
                GROUP BY t.mesaj_id
                ORDER BY oy DESC LIMIT 1
            """, (kesim,)).fetchone()
            if r and r["oy"] >= 2:   # en az 2 oy anlamlı
                return {"urun": r["urun_adi"], "kategori": r["kategori"],
                        "magaza": r["magaza"], "oy": r["oy"]}
    except Exception as e:
        log("UYARI", f"Haftanın ürünü: {e}")
    return None


def kategori_ilgi(gun: int = 7) -> list:
    """Son N günde hangi kategori daha çok oy aldı?"""
    try:
        kesim = int(time.time()) - gun * 86400
        with db.cursor() as c:
            satirlar = c.execute("""
                SELECT m.kategori, COUNT(*) as oy
                FROM kullanici_tikla t
                JOIN mesaj_meta m ON t.mesaj_id = m.mesaj_id
                WHERE t.oy_turu='good' AND t.ts >= ? AND m.kategori != ''
                GROUP BY m.kategori ORDER BY oy DESC LIMIT 5
            """, (kesim,)).fetchall()
            return [(r["kategori"], r["oy"]) for r in satirlar]
    except Exception:
        return []


def en_aktif_kullanicilar(gun: int = 7, n: int = 5) -> list:
    """En çok oy veren kullanıcılar (gelecekte rozet temeli)."""
    try:
        kesim = int(time.time()) - gun * 86400
        with db.cursor() as c:
            satirlar = c.execute("""
                SELECT kullanici_id, COUNT(*) as oy
                FROM kullanici_tikla
                WHERE ts >= ? AND kullanici_id IS NOT NULL
                GROUP BY kullanici_id ORDER BY oy DESC LIMIT ?
            """, (kesim, n)).fetchall()
            return [(r["kullanici_id"], r["oy"]) for r in satirlar]
    except Exception:
        return []


def haftalik_vitrin_metni(gun: int = 7) -> str | None:
    """Haftalık özete eklenecek etkileşim vitrini (kanala paylaşılır)."""
    urun = haftanin_urunu(gun)
    kategoriler = kategori_ilgi(gun)
    if not urun and not kategoriler:
        return None
    satirlar = []
    if urun:
        satirlar.append(f"🏆 <b>Haftanın Favorisi:</b>\n{urun['urun'][:50]} "
                        f"({urun['oy']} 🔥)")
    if kategoriler:
        kat_str = ", ".join(f"{k} ({o})" for k, o in kategoriler[:3])
        satirlar.append(f"📊 <b>En çok ilgi:</b> {kat_str}")
    return "\n\n".join(satirlar) if satirlar else None
