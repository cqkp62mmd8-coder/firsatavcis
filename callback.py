"""
Bot callback handler: 🔥 / ❌ inline buton tıklamalarını işler.
Tıklamalar 'utils/segment.py' tarafından kaydedilir (kullanıcı segmentasyon için).
"""
from telethon import TelegramClient, events
from utils.log import log


def kaydet(bot_client: TelegramClient) -> None:
    """Callback handler'ı bot_client'a bağlar. main.py'den bir kez çağrılır."""

    @bot_client.on(events.CallbackQuery())
    async def _callback(event):
        try:
            data = event.data
            oy_turu = None
            yanit = "İşlem alındı."

            if data == b"vote_good":
                oy_turu = "good"
                yanit = "Teşekkürler! Bu fırsat kaçmaz olarak işaretlendi. 🔥"
            elif data == b"vote_fake":
                oy_turu = "fake"
                yanit = "Bildiriminiz için teşekkürler! İncelenecek. 🔍"

            # Segmentasyon kaydı (sessiz hata)
            if oy_turu:
                try:
                    from utils import segment
                    kullanici_id = event.sender_id
                    mesaj_id = event.message_id if hasattr(event, "message_id") else None
                    segment.tikla_kaydet(kullanici_id, mesaj_id, oy_turu)
                except Exception as e:
                    log("UYARI", f"Tıklama segment kaydı: {e}")

            await event.answer(yanit, alert=False)
        except Exception as e:
            log("HATA", f"Callback: {e}")
