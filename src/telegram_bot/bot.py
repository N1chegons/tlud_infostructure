import asyncio
import telebot
from aiohttp import web

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, \
    KeyboardButton
from telebot.async_telebot import AsyncTeleBot

from src.config import settings
from src.logger_config import setup_logger
from src.telegram_bot.repository import TelegramRepository

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
WEBHOOK_PATH = settings.WEBHOOK_PATH
WEBHOOK_URL = settings.WEBHOOK_URL_PATH

app = web.Application()
bot = AsyncTeleBot(BOT_TOKEN)
logger = setup_logger('telegram_bot', 'bot', 'bot.log')

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    user = await TelegramRepository.get_user(user_id)
    logger.info(f"START: Пользователь {user_id} запустил бота")
    logger.info(f"Пользователь {user_id} запустил бота")

    kb = InlineKeyboardMarkup()

    if not user:
        logger.info(f"Пользователь не зарегестрирован. Первод на мини-регистрацию")

        kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="submit_request"))

    elif user.has_free_consultation:
        logger.info(f"Пользователь зарегестрирован. Запись на бесплатную консультацию уже была произведена")

        kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="already_has_free_consultation"))

    else:
        logger.info(f"Пользователь зарегестрирован. Запись на бесплатную консультацию")

        kb.add(InlineKeyboardButton(text="Записаться на бесплатную консультацию", callback_data="register"))

    await bot.send_message(
        chat_id=message.chat.id,
        text="Привет! 🙌\n"
        "Я цифровой психолог. Моя задача — показать, что твоя дата рождения — это не просто цифры в паспорте. Это твой личный код, подпись Вселенной и ключ к счастливой жизни.\n\n"
        "Готов узнать, что в тебе зашифровано? 👇",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "submit_request")
async def recording_consultation(call: CallbackQuery):
    await bot.send_message(call.message.chat.id, "Вы записаны на консультацию! Ожидайте...")

@bot.callback_query_handler(func=lambda call: call.data == "register")
async def register(call: CallbackQuery):
    await bot.send_message(call.message.chat.id, "Начинаем регистрацию! Как тебя зовут?")


async def handle_webhook(request):
    try:
        body = await request.json()
        logger.info(f"Webhook received: {body}")
        update = telebot.types.Update.de_json(body)
        await bot.process_new_updates([update])
        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Webhook error: {e}")
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