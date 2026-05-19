"""
#11 — Stok takip: bot mesaj atınca, N saat sonra ürün linkini kontrol eder.
Stok yoksa mesajı edit ederek "❌ TÜKENDİ" etiketi ekler.

#7 PERSISTENCE:
  • Bekleyen kayıtlar JSON dosyasına yazılır (atomic write).
  • Bot restart olsa bile 6 saat bekleyen ürünler unutulmaz.
"""
import asyncio
import json
import os
import re
import tempfile
import urllib.request
import urllib.error

import config
from utils.log import log, simdi_tr

# Bekleyen kayıtlar
_bekleyen: list[dict] = []
_yuklendi = False
_MAX_KAYIT = 200
_STOK_FILE = os.path.join(config.DATA_DIR, "stok_bekleyen.json")


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


def _yukle() -> None:
    """JSON'dan bekleyenleri yükle (bir kere, lazy)."""
    global _bekleyen, _yuklendi
    if _yuklendi:
        return
    _yuklendi = True
    try:
        with open(_STOK_FILE) as f:
            _bekleyen = json.load(f)
        log("OK", f"Stok bekleyen yüklendi: {len(_bekleyen)} kayıt")
    except Exception:
        _bekleyen = []


def _kaydet() -> None:
    """JSON'a atomik yaz: tempfile + rename. Crash sırasında bozulmaz."""
    try:
        dn = os.path.dirname(_STOK_FILE) or "."
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dn, delete=False, suffix=".tmp", encoding="utf-8"
        ) as f:
            json.dump(_bekleyen, f, ensure_ascii=False)
            geçici = f.name
        os.replace(geçici, _STOK_FILE)
    except Exception as e:
        log("UYARI", f"Stok bekleyen kaydetme: {e}")


def kayit_ekle(msg, link: str) -> None:
    """Yeni gönderilen mesajı stok takip listesine ekle."""
    if config.STOK_KONTROL_SAAT <= 0 or not link or not msg:
        return
    _yukle()
    _bekleyen.append({
        "msg_id":  msg.id,
        "kanal":   config.HEDEF_KANAL,
        "link":    link,
        "metin":   (msg.text or "")[:3500],   # Telegram limit
        "eklendi": simdi_tr().timestamp(),
    })
    while len(_bekleyen) > _MAX_KAYIT:
        _bekleyen.pop(0)
    _kaydet()


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
    _yukle()
    if config.STOK_KONTROL_SAAT <= 0:
        log("BILGI", "Stok takip devre dışı (STOK_KONTROL_SAAT=0)")
        return

    log("BILGI", f"Stok takip başladı — her ürün {config.STOK_KONTROL_SAAT}s sonra kontrol")

    while True:
        await asyncio.sleep(600)   # 10 dk
        try:
            simdi = simdi_tr().timestamp()
            hedef_yas = config.STOK_KONTROL_SAAT * 3600
            isle = [k for k in _bekleyen if simdi - k["eklendi"] >= hedef_yas]
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
                    if kayit in _bekleyen:
                        _bekleyen.remove(kayit)
                    await asyncio.sleep(2)
                except Exception as e:
                    log("UYARI", f"Stok kontrol döngüsü: {e}")
            _kaydet()
        except Exception as e:
            log("HATA", f"Stok takip: {e}")
