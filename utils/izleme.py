"""
#2 — Single Point of Failure azaltma: kritik hataları admin'e DM olarak gönder.
Sentry tam entegrasyonu yerine basit, bağımlılıksız çözüm.

#8 — Secret guard: log'larda token/hash çıkmasın diye sansür.

Kullanım:
  await izleme.kritik_uyari(tg_client, "Bot Telegram'a bağlanamadı: ...")
"""
import re
import time

import config
from utils.log import log


# v22.8 — Admin'e DM göndermek için ortak yardımcı.
# SORUN: Kullanıcı client'ı ile ADMIN_ID'ye (kendi user ID'in) mesaj atınca
# Telegram bunu "Kaydedilenler/Saved Messages"a koyuyor — kendine mesaj olduğu için.
# ÇÖZÜM: Bot client'ı varsa ONUNLA gönder → normal bot→kullanıcı DM'i olur.
# Bot client yoksa son çare kullanıcı client'ı (Saved Messages'a düşer ama
# hiç gitmemesinden iyidir).
_bot_client_ref = None   # main.py başlangıçta set eder


def bot_client_ayarla(bot_client) -> None:
    """main.py bot client'ı başlattığında çağırır."""
    global _bot_client_ref
    _bot_client_ref = bot_client


async def admin_dm(mesaj: str, parse_mode: str = "html",
                   yedek_client=None) -> bool:
    """Admin'e DM gönder. Bot client öncelikli (Saved Messages'a düşmesin).
    Döner: gönderildiyse True."""
    if not config.ADMIN_ID:
        return False
    try:
        admin_id = int(config.ADMIN_ID)
    except (ValueError, TypeError):
        log("UYARI", "admin_dm: ADMIN_ID geçersiz")
        return False
    # 1. Öncelik: bot client (gerçek DM, Saved Messages değil)
    if _bot_client_ref is not None:
        try:
            await _bot_client_ref.send_message(admin_id, mesaj, parse_mode=parse_mode)
            return True
        except Exception as e:
            log("UYARI", f"admin_dm bot client hata: {e}")
    # 2. Son çare: verilen kullanıcı client'ı (Saved Messages'a düşer)
    if yedek_client is not None:
        try:
            await yedek_client.send_message(admin_id, mesaj, parse_mode=parse_mode)
            return True
        except Exception as e:
            log("UYARI", f"admin_dm yedek client hata: {e}")
    return False


# Son N dakikada aynı hatayı tekrar atma
_son_uyarilar: dict[str, float] = {}
_TEKRAR_BEKLEME = 600   # 10 dk


# Sansürlenecek desenler
_SECRET_KALIPLARI = [
    (re.compile(r"API_HASH=[a-f0-9]{20,}", re.I), "API_HASH=***"),
    (re.compile(r"\d{1,3}:[A-Za-z0-9_-]{30,}"),    "<BOT_TOKEN>"),
    (re.compile(r"[a-zA-Z0-9+/]{150,}"),            "<SESSION_STRING>"),
]


def sansurle(metin: str) -> str:
    """Olası secret değerleri maskeler."""
    if not metin:
        return metin
    for kalip, yedek in _SECRET_KALIPLARI:
        metin = kalip.sub(yedek, metin)
    return metin


async def kritik_uyari(tg_client, mesaj: str) -> None:
    """Admin'e kritik hata bildirimi. Spam'i önlemek için dedupe."""
    if not config.ADMIN_ID:
        return
    mesaj = sansurle(mesaj)

    # Aynı uyarı 10 dakika içinde tekrar gönderilmez
    anahtar = mesaj[:100]
    simdi = time.time()
    if anahtar in _son_uyarilar and simdi - _son_uyarilar[anahtar] < _TEKRAR_BEKLEME:
        return
    _son_uyarilar[anahtar] = simdi

    # Memory limit
    if len(_son_uyarilar) > 100:
        # En eski 50'yi sil
        sirali = sorted(_son_uyarilar.items(), key=lambda x: x[1])
        for k, _ in sirali[:50]:
            del _son_uyarilar[k]

    try:
        # v22.8 — bot client öncelikli (Saved Messages'a düşmesin)
        gonderildi = await admin_dm(
            f"🚨 <b>Kritik Uyarı</b>\n\n<code>{mesaj[:3500]}</code>",
            yedek_client=tg_client,
        )
        if not gonderildi:
            log("UYARI", "Kritik uyarı gönderilemedi")
    except Exception as e:
        log("UYARI", f"Kritik uyarı gönderilemedi: {e}")
