import asyncio
import telebot
from aiohttp import web

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from telebot.async_telebot import AsyncTeleBot

from src.config import settings
from src.logger_config import setup_logger
from src.telegram_bot.repository import TelegramBotRepository, ConsultationRepository, Validation

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
WEBHOOK_PATH = settings.WEBHOOK_PATH
WEBHOOK_URL = settings.WEBHOOK_URL_PATH

app = web.Application()
bot = AsyncTeleBot(BOT_TOKEN)
logger = setup_logger('telegram_bot', 'bot', 'bot.log')

# start
@bot.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    user = await TelegramBotRepository.get_user(user_id)
    logger.info(f"Пользователь {user_id} запустил бота")

    kb = InlineKeyboardMarkup()

    if user.has_free_consultation:
        logger.info(f"Пользователь зарегестрирован. Запись на бесплатную консультацию уже была произведена")

        await bot.send_message(chat_id=message.chat.id, text="Привет! Ты уже зареегестрирован. Тут сообщение будет какое-то")

    else:
        if not user:
            logger.info(f"Пользователь не зарегестрирован. Первод на мини-регистрацию")

            kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="register"))

        else:
            logger.info(f"Пользователь зарегестрирован. Запись на бесплатную консультацию")

            kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="submit_request"))

        await bot.send_message(
            chat_id=message.chat.id,
            text="Привет! 🙌\n"
            "Я цифровой психолог. Моя задача — показать, что твоя дата рождения — это не просто цифры в паспорте. Это твой личный код, подпись Вселенной и ключ к счастливой жизни.\n\n"
            "Готов узнать, что в тебе зашифровано? 👇",
            reply_markup=kb
        )

# logic
registration_data = {}

@bot.callback_query_handler(func=lambda call: call.data == "submit_request")
async def recording_consultation(call: CallbackQuery):
    user_id = call.from_user.id
    user = await TelegramBotRepository.get_user(user_id)

    try:
        logger.info(f"Пользователь TG_ID {user_id} записывается на консультацию")

        if not user:
            logger.warning(f"Пользователь не зарегестрирован")
            await bot.edit_message_text(
                text=f"❌ Видимо вы не зарегестрированы, отправить в чат для регистрации - /start",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
            return


        await ConsultationRepository.create_consultation(user.id)
        await TelegramBotRepository.update_free_consultation_status(user_id)

        await bot.edit_message_text(
            text=f"✅ {user.username}, вы успешно записались на консультацию! Ожидайте...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    except Exception as e:
        logger.error(f"Произошла неизвестная оишбка при записи у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.send_message(
            chat_id=call.message.chat.id,
            text="❌ Произошла неизвестная оишбка",
        )

@bot.callback_query_handler(func=lambda call: call.data == "register")
async def register(call: CallbackQuery):
    user_id = call.from_user.id

    registration_data[user_id] = {"step": "name"}

    await bot.send_message(chat_id=call.message.chat.id, text="Ты еще не зарегестрирован, давай пройдем небольшую регистрацию!")
    await bot.send_message(chat_id=call.message.chat.id, text="Для начала, как тебя зовут?(Введите имя используя латиницу, пример: Ivan)")

@bot.callback_query_handler(func=lambda call: call.data == "confirm")
async def confirm(call: CallbackQuery):
    user_id = call.from_user.id
    data = registration_data.get(user_id)

    if not data:
        logger.warning(f"Пользователь не зарегестрирован")
        await bot.edit_message_text(
            text=f"❌ Видимо вы не зарегестрированы, отправьте в чат для регистрации - /start",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    try:
        logger.info(f"Регистрация для пользователя TG_ID {user_id}")

        await TelegramBotRepository.register_user(user_id, data["name"], data["birth"], data["phone"])

        del registration_data[user_id]

        await recording_consultation(call)

    except Exception as e:
        logger.error(f"Произошла неизвестная оишбка при регистрации у пользователя ID {user_id}, ошибка: {str(e)}")
        await bot.send_message(
            chat_id=call.message.chat.id,
            text="❌ Произошла неизвестная оишбка",
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
async def cancel(call: CallbackQuery):
    user_id = call.from_user.id

    if user_id in registration_data:
        del registration_data[user_id]

    registration_data[user_id] = {"step": "name"}

    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔄 Давай попробуем ещё раз! Как тебя зовут?"
    )

@bot.message_handler(func=lambda message: True)
async def handle_text(message):
    user_id = message.from_user.id

    if user_id not in registration_data:
        return

    step = registration_data[user_id]["step"]

    if step == "name":
        name = message.text.strip()
        if not Validation.validate_name(name):
            await bot.send_message(chat_id=user_id,
                                   text="❌ Имя должно быть на латинице, без пробелов. Пример: Ivan")
            return

        registration_data[user_id]["name"] = message.text
        registration_data[user_id]["step"] = "birth"
        await bot.send_message(chat_id=user_id, text="Теперь дату рождения, в формате ДД.ММ.ГГГГ (Пример: 31.01.2000):")

    elif step == "birth":
        birth = message.text.strip()

        if not Validation.validate_date(birth):
            await bot.send_message(
                chat_id=user_id,
                text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (Пример: 31.01.2000):"
            )
            return

        registration_data[user_id]["birth"] = message.text
        registration_data[user_id]["step"] = "phone"

        contact_button = KeyboardButton(
            text="📱 Поделиться номером",
            request_contact=True
        )
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(contact_button)

        await bot.send_message(
            chat_id=user_id,
            text="Поделись своим номером чтобы с тобой связались.",
            reply_markup=keyboard
        )

@bot.message_handler(content_types=['contact'])
async def handle_contact(message):
    contact = message.contact
    user_id = message.from_user.id

    if user_id not in registration_data:
        return

    phone = contact.phone_number
    registration_data[user_id]["phone"] = phone

    data = registration_data[user_id]

    text = f"""
        📋 Проверьте данные:
        Имя: {data['name']}
        Дата рождения: {data['birth']}
        Телефон: {phone}
        
        Всё верно?
    """
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Да", callback_data="confirm"),
        InlineKeyboardButton("❌ Нет", callback_data="cancel")
    )

    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=kb
    )

# connections
async def handle_webhook(request):
    try:
        body = await request.json()
        logger.info(f"Webhook received: {body}")
        update = telebot.types.Update.de_json(body)
        try:
            await bot.process_new_updates([update])
        except Exception as e:
            logger.error(f"process_new_updates error: {e}", exc_info=True)
        return web.Response(status=200, text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return web.Response(status=200, text="OK")

app.router.add_post(WEBHOOK_PATH, handle_webhook)

async def main():
    await bot.delete_webhook()
    await bot.set_webhook(url=WEBHOOK_URL)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='127.0.0.1', port=8080)
    await site.start()
    print(f"Бот запущен на http://127.0.0.1:8080{WEBHOOK_PATH}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())