"""
Görülmüş + istatistik kalıcı önbelleği.

KALICILIK STRATEJİSİ:
- gorulmus: yerel JSON dosyası (Heroku'da restart'ta kaybedilir, 7 günlük TTL var, tolere edilebilir).
- istatistik: Hem yerel diske hem Telegram'a (admin DM'ine) edit-edilen sabit bir mesaja yazılır.
  Bot her başlangıçta Telegram'dan yükler — Heroku ephemeral disk problemini çözer.
"""
import asyncio
import json
from datetime import datetime, timezone

import config
from utils.log import log, simdi_tr

# ── İç durum ────────────────────────────────────────────────────
_gorulmus: dict[str, float] | None = None
_istatistik: dict | None = None
_ist_degisim: int = 0

# Telegram kalıcılığı
_tg_client = None
_ist_msg_id: int | None = None
_kayit_kilidi = asyncio.Lock()
_VERI_BASLIK = "##FIRSATPULSU_IST_V1##"


# ════════════════════════════════════════════════════════════════
# Görülmüş (yerel disk — restart'ta kaybedilebilir)
# ════════════════════════════════════════════════════════════════
def _gorulmus_yukle() -> dict[str, float]:
    global _gorulmus
    if _gorulmus is None:
        try:
            with open(config.GORULMUS_FILE) as f:
                _gorulmus = json.load(f)
        except Exception:
            _gorulmus = {}
    return _gorulmus


def _gorulmus_kaydet() -> None:
    if _gorulmus is None:
        return
    try:
        kayit = _gorulmus
        if len(kayit) > config.GORULMUS_MAX:
            kayit = dict(sorted(kayit.items(), key=lambda x: x[1], reverse=True)[: config.GORULMUS_MAX])
            _gorulmus.clear()
            _gorulmus.update(kayit)
        with open(config.GORULMUS_FILE, "w") as f:
            json.dump(_gorulmus, f)
    except Exception as e:
        log("HATA", f"görülmüş kaydetme: {e}")


def gorulmus_var_mi(mid: str) -> bool:
    return mid in _gorulmus_yukle()


def gorulmus_ekle(mid: str) -> None:
    _gorulmus_yukle()[mid] = datetime.now(timezone.utc).timestamp()
    _gorulmus_kaydet()


def gorulmus_temizle() -> None:
    g = _gorulmus_yukle()
    simdi = datetime.now(timezone.utc).timestamp()
    onceki = len(g)
    eskiler = [k for k, v in g.items() if simdi - v >= config.GORULMUS_TTL]
    for k in eskiler:
        del g[k]
    if len(g) > config.GORULMUS_MAX:
        fazla = sorted(g.items(), key=lambda x: x[1])[: len(g) - config.GORULMUS_MAX]
        for k, _ in fazla:
            del g[k]
    temizlenen = onceki - len(g)
    if temizlenen > 0:
        log("BILGI", f"{temizlenen} eski görülmüş kaydı temizlendi")
    _gorulmus_kaydet()


# ════════════════════════════════════════════════════════════════
# İstatistik — Telegram kalıcılığı
# ════════════════════════════════════════════════════════════════

def _bos_istatistik() -> dict:
    return {
        "toplam": 0,
        "kanallar": {},
        "gunluk": {},
        "kategoriler": {},
        "magazalar": {},
    }


async def telegram_yukle(tg_client) -> None:
    """Bot başlangıcında çağrılır. Admin DM'inden istatistik mesajını yükler.
    Bulamazsa yerel diski dener, o da yoksa boş başlatır."""
    global _istatistik, _ist_msg_id, _tg_client
    _tg_client = tg_client

    yuklendi = False

    # 1) Telegram'dan dene
    if config.ADMIN_ID:
        try:
            admin_id = int(config.ADMIN_ID)
            async for msg in tg_client.iter_messages(admin_id, limit=300):
                if msg.text and msg.text.startswith(_VERI_BASLIK):
                    try:
                        json_str = msg.text[len(_VERI_BASLIK):].strip()
                        _istatistik = json.loads(json_str)
                        _ist_msg_id = msg.id
                        yuklendi = True
                        log("OK", f"İstatistik Telegram'dan yüklendi (toplam: {_istatistik.get('toplam', 0)})")
                        break
                    except json.JSONDecodeError as e:
                        log("UYARI", f"İstatistik JSON parse hatası: {e}")
        except Exception as e:
            log("UYARI", f"Telegram istatistik yükleme: {e}")

    # 2) Yerel diskten dene (Telegram'dan gelmediyse)
    if not yuklendi:
        try:
            with open(config.ISTATISTIK_FILE) as f:
                _istatistik = json.load(f)
                log("OK", f"İstatistik diskten yüklendi (toplam: {_istatistik.get('toplam', 0)})")
                yuklendi = True
        except Exception:
            pass

    # 3) Sıfırdan başla
    if not yuklendi:
        _istatistik = _bos_istatistik()
        log("BILGI", "İstatistik sıfırdan başlatıldı")

    # Telegram'a ilk kaydı yap (mesaj ID kazanmak için)
    if config.ADMIN_ID and _tg_client and _ist_msg_id is None:
        await _telegram_kaydet()


async def _telegram_kaydet() -> None:
    """İstatistiği admin DM'ine kaydet. Edit varsa edit, yoksa yeni gönder."""
    global _ist_msg_id
    if not _tg_client or not config.ADMIN_ID or _istatistik is None:
        return

    async with _kayit_kilidi:
        try:
            admin_id = int(config.ADMIN_ID)
            metin = _VERI_BASLIK + "\n" + json.dumps(_istatistik, ensure_ascii=False)
            # 4096 karakter Telegram sınırı
            if len(metin) > 4000:
                # Eski günlük kayıtları kırp (sadece son 30 gün)
                gunluk = _istatistik.get("gunluk", {})
                if len(gunluk) > 30:
                    sirali = sorted(gunluk.items(), reverse=True)[:30]
                    _istatistik["gunluk"] = dict(sirali)
                metin = _VERI_BASLIK + "\n" + json.dumps(_istatistik, ensure_ascii=False)

            if _ist_msg_id:
                try:
                    await _tg_client.edit_message(admin_id, _ist_msg_id, metin)
                except Exception:
                    # Edit başarısız (mesaj silinmiş olabilir) — yeniden gönder
                    msg = await _tg_client.send_message(admin_id, metin)
                    _ist_msg_id = msg.id
            else:
                msg = await _tg_client.send_message(admin_id, metin)
                _ist_msg_id = msg.id
        except Exception as e:
            log("UYARI", f"Telegram istatistik kaydetme: {e}")


def _disk_kaydet() -> None:
    """Yerel diske de yaz (Telegram fallback olarak)."""
    if _istatistik is None:
        return
    try:
        with open(config.ISTATISTIK_FILE, "w") as f:
            json.dump(_istatistik, f)
    except Exception:
        pass


def ist_yukle() -> dict:
    """Sync: bellekteki kopyayı dön. Önce telegram_yukle() çağrılmış olmalı."""
    global _istatistik
    if _istatistik is None:
        _istatistik = _bos_istatistik()
    return _istatistik


def ist_kaydet() -> None:
    """Sync — disk ve background olarak Telegram'a yazar."""
    if _istatistik is None:
        return
    _disk_kaydet()
    # Async Telegram kaydını fire-and-forget tetikle (event loop varsa)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_telegram_kaydet())
    except RuntimeError:
        pass   # event loop dışında, sessizce geç


def ist_guncelle(kanal: str, magaza: str, kategori: str) -> None:
    global _ist_degisim
    ist = ist_yukle()
    ist["toplam"] = ist.get("toplam", 0) + 1
    ist["kanallar"][kanal]       = ist["kanallar"].get(kanal, 0) + 1
    ist["magazalar"][magaza]     = ist["magazalar"].get(magaza, 0) + 1
    ist["kategoriler"][kategori] = ist["kategoriler"].get(kategori, 0) + 1
    bugun = simdi_tr().strftime("%Y-%m-%d")
    ist["gunluk"][bugun] = ist["gunluk"].get(bugun, 0) + 1
    _ist_degisim += 1
    if _ist_degisim >= 5:           # Her 5 güncellemede bir kalıcılaştır
        ist_kaydet()
        _ist_degisim = 0


async def periyodik_kaydet(aralik: int = 600) -> None:
    """Arka plan görevi: her N saniyede bir Telegram'a istatistik kaydet."""
    while True:
        await asyncio.sleep(aralik)
        if _ist_degisim > 0:
            await _telegram_kaydet()
            _disk_kaydet()
            globals()["_ist_degisim"] = 0
