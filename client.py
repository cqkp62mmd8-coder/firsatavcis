"""
Telegram client nesnelerini başlatır ve dışa açar.
Her modül buradan import eder; client tekrar oluşturulmaz.
"""
from telethon import TelegramClient
from telethon.sessions import StringSession

import config

# ── Kullanıcı client'ı (mesaj okuma / gönderme) ─────────────────
client = TelegramClient(
    StringSession(config.SESSION_STRING),
    config.API_ID,
    config.API_HASH,
)

# ── Bot client'ı (inline butonlar için, opsiyonel) ───────────────
# main.py içinde start() çağrısından sonra atanır.
bot_client: TelegramClient | None = None
