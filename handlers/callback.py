"""
Bot callback handler: 🔥 / ❌ inline buton tıklamalarını işler.
"""
from telethon import TelegramClient, events
from utils.log import log


def kaydet(bot_client: TelegramClient) -> None:
    """Callback handler'ı bot_client'a bağlar. main.py'den bir kez çağrılır."""

    @bot_client.on(events.CallbackQuery())
    async def _callback(event):
        try:
            yanit = {
                b"vote_good": "Teşekkürler! Bu fırsat kaçmaz olarak işaretlendi. 🔥",
                b"vote_fake": "Bildiriminiz için teşekkürler! İncelenecek. 🔍",
            }.get(event.data, "İşlem alındı.")
            await event.answer(yanit, alert=False)
        except Exception as e:
            log("HATA", f"Callback: {e}")
