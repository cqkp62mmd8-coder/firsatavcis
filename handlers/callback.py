"""
Bot callback handler: 🔥 / ❌ inline buton tıklamalarını işler.
Oy gelince butonlar canlı oy sayılarıyla güncellenir (sosyal kanıt).
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

            if data == b"vote_good":
                oy_turu = "good"
            elif data == b"vote_fake":
                oy_turu = "fake"

            if not oy_turu:
                await event.answer("İşlem alındı.", alert=False)
                return

            kullanici_id = event.sender_id
            mesaj_id = event.message_id if hasattr(event, "message_id") else None

            # Oyu kaydet (çift oy engellenir / değiştirilir)
            yeni_oy = False
            try:
                from utils import segment
                yeni_oy = segment.tikla_kaydet(kullanici_id, mesaj_id, oy_turu)
            except Exception as e:
                log("UYARI", f"Tıklama segment kaydı: {e}")

            # v22.7 — Sistem 8: A/B test oyunu işle (hangi şablon stili daha iyi)
            if yeni_oy and mesaj_id:
                try:
                    from utils import ab_test
                    ab_test.oy_kaydet(mesaj_id, oy_turu == "good")
                except Exception:
                    pass
                # Kara kutuya oy olayını kaydet
                try:
                    from utils import karakutu
                    karakutu.kaydet("mesaj", f"Oy: {oy_turu} (msg {mesaj_id})")
                except Exception:
                    pass

            # Kullanıcıya geri bildirim
            if not yeni_oy:
                await event.answer("Zaten oy verdin 👍", alert=False)
                return
            yanit = ("Teşekkürler! 🔥" if oy_turu == "good"
                     else "Bildirimin alındı, incelenecek 🔍")
            await event.answer(yanit, alert=False)

            # Butonları canlı oy sayılarıyla güncelle (sosyal kanıt)
            if mesaj_id:
                try:
                    await _butonlari_guncelle(event, mesaj_id)
                except Exception as e:
                    log("UYARI", f"Buton güncelleme: {e}")

        except Exception as e:
            log("HATA", f"Callback: {e}")

    async def _butonlari_guncelle(event, mesaj_id: int) -> None:
        """Mesajın oylama butonlarını güncel sayılarla yeniden çiz."""
        from utils import segment
        from telethon.tl.types import (
            KeyboardButtonUrl, KeyboardButtonCallback,
            KeyboardButtonRow, ReplyInlineMarkup,
        )
        iyi, sahte = segment.oy_sayilari(mesaj_id)

        # Mevcut mesajı al — URL butonlarını koru, oy butonlarını güncelle
        mesaj = await event.get_message()
        if not mesaj or not mesaj.reply_markup:
            return

        yeni_satirlar = []
        for satir in mesaj.reply_markup.rows:
            yeni_butonlar = []
            oy_satiri = False
            for btn in satir.buttons:
                if isinstance(btn, KeyboardButtonCallback):
                    oy_satiri = True
                    if btn.data == b"vote_good":
                        etiket = f"🔥 Kaçmaz ({iyi})" if iyi else "🔥 Kaçmaz Fırsat"
                        yeni_butonlar.append(KeyboardButtonCallback(text=etiket, data=b"vote_good"))
                    elif btn.data == b"vote_fake":
                        etiket = f"❌ Sahte ({sahte})" if sahte else "❌ Sahte İndirim"
                        yeni_butonlar.append(KeyboardButtonCallback(text=etiket, data=b"vote_fake"))
                    else:
                        yeni_butonlar.append(btn)
                else:
                    yeni_butonlar.append(btn)
            yeni_satirlar.append(KeyboardButtonRow(buttons=yeni_butonlar))

        try:
            await event.edit(buttons=ReplyInlineMarkup(rows=yeni_satirlar))
        except Exception:
            pass   # MessageNotModified vb. — sorun değil
