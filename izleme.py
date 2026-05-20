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
        await tg_client.send_message(
            int(config.ADMIN_ID),
            f"🚨 <b>Kritik Uyarı</b>\n\n<code>{mesaj[:3500]}</code>",
            parse_mode="html",
        )
    except Exception as e:
        log("UYARI", f"Kritik uyarı gönderilemedi: {e}")
