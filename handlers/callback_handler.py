"""
Bot callback handler: inline buton basımlarını işler.
"""
from telethon import events
from utils.logger import log


def register_callback_handler(bot_client):
    @bot_client.on(events.CallbackQuery())
    async def buton_basildi(event):
        try:
            data = event.data
            if data == b'vote_good':
                await event.answer('Teşekkürler! Bu fırsat kaçmaz olarak işaretlendi.', alert=False)
            elif data == b'vote_fake':
                await event.answer('Bildiriminiz için teşekkürler! İncelenecek.', alert=False)
            else:
                await event.answer('İşlem alındı.', alert=False)
        except Exception as e:
            log('HATA', f'Callback: {e}')
