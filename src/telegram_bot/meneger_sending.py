import logging

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.telegram_bot.repository import AdminRepository


async def send_notification_telegram(user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=text)
        logging.info(f"✅ Уведомление отправлено пользователю {user_id}")
    except Exception as e:
        logging.error(f"❌ Не удалось отправить уведомление {user_id}: {e}")

async def notify_admins(text: str):
    admin_ids = await AdminRepository.get_admin_ids()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📋 Посмотреть записи", callback_data="admin_view_consultations"))

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

from src.telegram_bot.bot import bot