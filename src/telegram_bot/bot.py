import asyncio
import telebot
from aiohttp import web

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, \
    KeyboardButton
from telebot.async_telebot import AsyncTeleBot

from src.config import settings


BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
WEBHOOK_PATH = settings.WEBHOOK_PATH
WEBHOOK_URL = settings.WEBHOOK_URL

app = web.Application()
bot = AsyncTeleBot(BOT_TOKEN)


async def handle_webhook(request):
    try:
        body = await request.json()
        update = telebot.types.Update.de_json(body)
        await bot.process_new_updates([update])
        return web.Response(status=200, text="OK")
    except Exception as e:
        print(f"Ошибка: {e}")
        return web.Response(status=200, text="OK")

app.router.add_post(WEBHOOK_PATH, handle_webhook)

async def main():
    await bot.delete_webhook()
    await bot.set_webhook(url=WEBHOOK_URL)
    # Запускаем веб-сервер как асинхронную задачу
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='127.0.0.1', port=8081)
    await site.start()
    print(f"Бот запущен на http://127.0.0.1:8081{WEBHOOK_PATH}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())