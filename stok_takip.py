"""
#11 — Stok takip: bot mesaj atınca, N saat sonra ürün linkini kontrol eder.
Stok yoksa mesajı edit ederek "❌ TÜKENDİ" etiketi ekler.

#3 — Bekleyenler artık SQLite'ta (db.stok_takip tablosu).
Bot restart olsa bile veriler korunur.
"""
import asyncio
import re
import urllib.request
import urllib.error

import config
from utils import db
from utils.log import log, simdi_tr

_MAX_KAYIT = 200

# Stok yok pattern'leri
_TUKENDI_KALIPLAR = [
    r"stokta\s*yok",
    r"tükendi",
    r"out\s*of\s*stock",
    r"şu\s*an\s*satışta\s*değil",
    r"ürün\s*bulunamadı",
    r"sayfa\s*bulunamadı",
    r"this\s*page\s*can.?t\s*be\s*found",
    r"şu\s*anda\s*satışta\s*olmayan",
]
_TUKENDI_RE = re.compile("|".join(_TUKENDI_KALIPLAR), re.I)


def kayit_ekle(msg, link: str) -> None:
    """Yeni gönderilen mesajı stok takip listesine ekle (SQLite)."""
    if config.STOK_KONTROL_SAAT <= 0 or not link or not msg:
        return
    try:
        with db.cursor() as c:
            c.execute("""
                INSERT OR REPLACE INTO stok_takip(msg_id, kanal, link, metin, eklendi_ts)
                VALUES (?, ?, ?, ?, ?)
            """, (
                msg.id, config.HEDEF_KANAL, link,
                (msg.text or "")[:3500],
                simdi_tr().timestamp(),
            ))
            # Limit
            c.execute("SELECT COUNT(*) FROM stok_takip")
            sayi = c.fetchone()[0]
            if sayi > _MAX_KAYIT:
                fazla = sayi - _MAX_KAYIT
                c.execute("""
                    DELETE FROM stok_takip
                    WHERE id IN (SELECT id FROM stok_takip ORDER BY eklendi_ts ASC LIMIT ?)
                """, (fazla,))
    except Exception as e:
        log("UYARI", f"Stok kayıt: {e}")


def _stokta_var_mi(link: str) -> bool | None:
    """True/False/None döner."""
    try:
        req = urllib.request.Request(
            link,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 404:
                return False
            if r.status >= 400:
                return None
            icerik = r.read(102_400).decode("utf-8", errors="ignore").lower()
            if _TUKENDI_RE.search(icerik):
                return False
            return True
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:
        return None


async def kontrol_dongusu(client) -> None:
    """Arka plan görevi: 10 dakikada bir bekleyenleri kontrol eder."""
    if config.STOK_KONTROL_SAAT <= 0:
        log("BILGI", "Stok takip devre dışı (STOK_KONTROL_SAAT=0)")
        return

    log("BILGI", f"Stok takip başladı — her ürün {config.STOK_KONTROL_SAAT}s sonra kontrol")

    while True:
        await asyncio.sleep(600)   # 10 dk
        try:
            simdi = simdi_tr().timestamp()
            hedef_yas = config.STOK_KONTROL_SAAT * 3600
            esik = simdi - hedef_yas

            # Yaşı dolmuş kayıtları çek
            with db.cursor() as c:
                c.execute(
                    "SELECT id, msg_id, kanal, link, metin FROM stok_takip WHERE eklendi_ts <= ?",
                    (esik,),
                )
                isle = c.fetchall()

            if not isle:
                continue

            log("BILGI", f"Stok kontrol: {len(isle)} ürün")
            for kayit in isle:
                try:
                    loop = asyncio.get_running_loop()
                    sonuc = await loop.run_in_executor(None, _stokta_var_mi, kayit["link"])
                    if sonuc is False:
                        yeni_metin = "❌ <b>TÜKENDİ</b>\n\n" + kayit["metin"]
                        try:
                            await client.edit_message(
                                kayit["kanal"], kayit["msg_id"],
                                yeni_metin, parse_mode="html",
                            )
                            log("OK", f"Tükendi etiketi eklendi (msg {kayit['msg_id']})")
                        except Exception as e:
                            log("UYARI", f"Mesaj edit hatası: {e}")
                    # Sonuç ne olursa olsun kayıttan sil
                    with db.cursor() as c:
                        c.execute("DELETE FROM stok_takip WHERE id=?", (kayit["id"],))
                    await asyncio.sleep(2)
                except Exception as e:
                    log("UYARI", f"Stok kontrol döngüsü: {e}")

        except Exception as e:
            log("HATA", f"Stok takip: {e}")
