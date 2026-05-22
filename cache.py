"""
Görülmüş + istatistik kalıcılığı — artık SQLite tabanlı.
Telegram backup'ı paralel olarak duruyor (felaket senaryosunda kurtarma).

#1 DÜZELTME: Görülmüş cache artık SQLite'ta — Railway restart'ta kayıp yok.
#7 DÜZELTME: Günde bir Telegram'a tam backup atılıyor.
#13 DÜZELTME: Schema versiyonu DB'de tutuluyor.
"""
import asyncio
import json
import os

import config
from utils import db
from utils.log import log, simdi_tr

# ── Telegram backup için durum ──────────────────────────────────
_tg_client = None
_ist_msg_id: int | None = None
_kayit_kilidi = asyncio.Lock()
_VERI_BASLIK = "##FIRSATPULSU_IST_V2##"   # v2 = SQLite çağı


# ════════════════════════════════════════════════════════════════
# Görülmüş (SQLite) — duplikat tespiti
# ════════════════════════════════════════════════════════════════

def gorulmus_var_mi(mid: str) -> bool:
    with db.cursor() as c:
        c.execute("SELECT 1 FROM gorulmus WHERE msg_hash=? LIMIT 1", (mid,))
        return c.fetchone() is not None


def gorulmus_ekle(mid: str) -> None:
    with db.cursor() as c:
        c.execute(
            "INSERT OR IGNORE INTO gorulmus(msg_hash, eklendi_ts) VALUES (?, ?)",
            (mid, simdi_tr().timestamp()),
        )


def gorulmus_temizle() -> int:
    """TTL'i geçenleri sil. #11 — RAM şişmesini önler."""
    silinen = db.temizle_eski("gorulmus", "eklendi_ts", config.GORULMUS_TTL)
    if silinen > 0:
        log("BILGI", f"{silinen} eski görülmüş kaydı temizlendi")
    # Limit kontrol — fazlasını da sil
    with db.cursor() as c:
        c.execute("SELECT COUNT(*) FROM gorulmus")
        sayi = c.fetchone()[0]
        if sayi > config.GORULMUS_MAX:
            fazla = sayi - config.GORULMUS_MAX
            c.execute("""
                DELETE FROM gorulmus
                WHERE msg_hash IN (
                    SELECT msg_hash FROM gorulmus
                    ORDER BY eklendi_ts ASC LIMIT ?
                )
            """, (fazla,))
            log("BILGI", f"{fazla} eski görülmüş kaydı boyut limiti ile silindi")
    return silinen


# ════════════════════════════════════════════════════════════════
# İstatistik (SQLite KV store + Telegram backup)
# ════════════════════════════════════════════════════════════════

def _ist_oku(anahtar: str, default=None):
    with db.cursor() as c:
        c.execute("SELECT value FROM istatistik WHERE key=?", (anahtar,))
        row = c.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return default


def _ist_yaz(anahtar: str, deger) -> None:
    with db.cursor() as c:
        c.execute(
            "INSERT OR REPLACE INTO istatistik(key, value) VALUES (?, ?)",
            (anahtar, json.dumps(deger, ensure_ascii=False)),
        )


def ist_yukle() -> dict:
    """Tüm istatistiği dict olarak döndürür (geri uyumluluk için)."""
    return {
        "toplam":      _ist_oku("toplam", 0),
        "kanallar":    _ist_oku("kanallar", {}),
        "magazalar":   _ist_oku("magazalar", {}),
        "kategoriler": _ist_oku("kategoriler", {}),
        "gunluk":      _ist_oku("gunluk", {}),
    }


def ist_kaydet() -> None:
    """Eski API uyumluluğu için. SQLite zaten anlık yazıyor.
    Telegram backup için async tetikleyici."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_telegram_kaydet())
    except RuntimeError:
        pass


def ist_guncelle(kanal: str, magaza: str, kategori: str) -> None:
    """Bir fırsat paylaşımı sayar."""
    bugun = simdi_tr().strftime("%Y-%m-%d")
    toplam = _ist_oku("toplam", 0) + 1
    _ist_yaz("toplam", toplam)

    for tablo_ad, alt_anahtar in [
        ("kanallar", kanal),
        ("magazalar", magaza),
        ("kategoriler", kategori),
        ("gunluk", bugun),
    ]:
        d = _ist_oku(tablo_ad, {})
        d[alt_anahtar] = d.get(alt_anahtar, 0) + 1
        _ist_yaz(tablo_ad, d)


# ════════════════════════════════════════════════════════════════
# Telegram backup (#7 — felaket kurtarma)
# ════════════════════════════════════════════════════════════════

async def telegram_yukle(tg_client) -> None:
    """Bot başlangıcında: önce SQLite'a bak (db.init zaten yaptı),
    SQLite boşsa Telegram'dan restore et."""
    global _tg_client, _ist_msg_id
    _tg_client = tg_client

    # SQLite'da veri var mı?
    toplam = _ist_oku("toplam", 0)
    if toplam > 0:
        log("OK", f"İstatistik SQLite'tan yüklendi (toplam: {toplam})")
        # Mevcut Telegram backup mesaj ID'sini bul
        if config.ADMIN_ID:
            try:
                admin_id = int(config.ADMIN_ID)
                async for msg in tg_client.iter_messages(admin_id, limit=200):
                    if msg.text and msg.text.startswith(_VERI_BASLIK):
                        _ist_msg_id = msg.id
                        break
            except Exception:
                pass
        return

    # SQLite boş — Telegram'dan restore et
    if not config.ADMIN_ID:
        log("BILGI", "İstatistik sıfırdan başlatıldı (admin yok, restore edilemez)")
        return

    try:
        admin_id = int(config.ADMIN_ID)
        async for msg in tg_client.iter_messages(admin_id, limit=300):
            if not msg.text:
                continue
            if msg.text.startswith(_VERI_BASLIK) or msg.text.startswith("##FIRSATPULSU_IST_V1##"):
                try:
                    json_str = msg.text.split("\n", 1)[1].strip()
                    data = json.loads(json_str)
                    # SQLite'a yaz
                    for k, v in data.items():
                        _ist_yaz(k, v)
                    _ist_msg_id = msg.id
                    log("OK", f"İstatistik Telegram'dan restore edildi (toplam: {data.get('toplam', 0)})")
                    return
                except Exception as e:
                    log("UYARI", f"Backup parse hatası: {e}")
    except Exception as e:
        log("UYARI", f"Telegram restore: {e}")


async def _telegram_kaydet() -> None:
    """SQLite'taki tüm istatistiği Telegram'a tek mesaj olarak yaz."""
    global _ist_msg_id
    if not _tg_client or not config.ADMIN_ID:
        return

    async with _kayit_kilidi:
        try:
            admin_id = int(config.ADMIN_ID)
            data = ist_yukle()

            # Gunluk kayıtları 30 gün ile sınırla (4KB Telegram limiti için)
            if "gunluk" in data and len(data["gunluk"]) > 30:
                sirali = sorted(data["gunluk"].items(), reverse=True)[:30]
                data["gunluk"] = dict(sirali)
                _ist_yaz("gunluk", data["gunluk"])

            metin = _VERI_BASLIK + "\n" + json.dumps(data, ensure_ascii=False)
            if len(metin) > 4000:
                # Hâlâ uzunsa kanallar/mağazalar top 10 ile sınırla
                for k in ("kanallar", "magazalar"):
                    if len(data.get(k, {})) > 10:
                        ust = dict(sorted(data[k].items(), key=lambda x: -x[1])[:10])
                        data[k] = ust
                metin = _VERI_BASLIK + "\n" + json.dumps(data, ensure_ascii=False)

            if _ist_msg_id:
                try:
                    await _tg_client.edit_message(admin_id, _ist_msg_id, metin)
                except Exception:
                    msg = await _tg_client.send_message(admin_id, metin)
                    _ist_msg_id = msg.id
            else:
                msg = await _tg_client.send_message(admin_id, metin)
                _ist_msg_id = msg.id
        except Exception as e:
            log("UYARI", f"Telegram istatistik kaydetme: {e}")


async def periyodik_kaydet(aralik: int = 600) -> None:
    """Arka plan: her N saniyede bir Telegram'a backup atar."""
    while True:
        await asyncio.sleep(aralik)
        try:
            await _telegram_kaydet()
        except Exception as e:
            log("UYARI", f"Periyodik kayıt: {e}")


async def gunluk_yedek() -> None:
    """#7 — Günde 1 kez tam SQLite dump'ı Telegram'a yolla."""
    while True:
        # Sabah 04:00'te yedekle (en sakin saat)
        from datetime import timedelta
        simdi = simdi_tr()
        hedef = simdi.replace(hour=4, minute=0, second=0, microsecond=0)
        if simdi >= hedef:
            hedef += timedelta(days=1)
        bekle = (hedef - simdi).total_seconds()
        await asyncio.sleep(bekle)

        if not _tg_client or not config.ADMIN_ID:
            continue

        try:
            admin_id = int(config.ADMIN_ID)
            # DB dosyasını binary olarak yolla
            if os.path.exists(db.DB_FILE):
                await _tg_client.send_file(
                    admin_id,
                    db.DB_FILE,
                    caption=f"📦 Günlük yedek — {simdi_tr().strftime('%Y-%m-%d')}",
                )
                log("OK", "Günlük yedek Telegram'a yollandı")
        except Exception as e:
            log("UYARI", f"Günlük yedek: {e}")
