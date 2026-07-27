from fastapi import FastAPI, Request
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.logger_config import setup_logger
from src.payments.models import PaymentStatus
from src.payments.repository import PaymentRepository
from src.telegram_bot.meneger_sending import send_notification_telegram, notify_admins
from src.telegram_bot.models import ConsultationType
from src.telegram_bot.repository import ConsultationRepository, TelegramBotRepository, ServiceRepository

app = FastAPI()


logger = setup_logger('webhook', 'payment_webhook', 'webhook_payment.log')

@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    data = await request.json()
    metadata = data["object"]["metadata"]
    user_id = int(metadata["user_id"])
    service_id = int(metadata["service_id"])
    yookassa_payment_id = data["object"]["id"]

    user = await TelegramBotRepository.get_user(user_id)
    service = await ServiceRepository.get_service_by_id(service_id)
    payment = await PaymentRepository.get_by_yookassa_id(yookassa_payment_id)

    if data.get("event") == "payment.succeeded":
        if not payment:
            logger.error(f"Платёж {yookassa_payment_id} не найден в БД")
            return {"status": "error", "message": "Payment not found"}

        await ConsultationRepository.create_consultation(
            user_id=user.id,
            service_id=service_id,
            pay_id=payment.id,
            service_name=service.name,
            type=ConsultationType.PAID,
        )

        await PaymentRepository.update_status_by_yookassa_id(yookassa_payment_id, PaymentStatus.succeeded)

        await send_notification_telegram(user_id, "✅ Платеж успешно прошел.")
        await notify_admins(f"Новая запись на платную консультацию. Клиент {user.username}.\n\nПерейти к записям 👇")

        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("📋 Мои консультации", callback_data="my_consultations"))

        await bot.send_message(
            chat_id=user_id,
            text="📋 Пока вы можете посмотреть свои консультации. Ожидайте ответа с вами скоро свяжутся...",
            reply_markup=kb
        )

    else:
        logger.info(f"Платеж для пользователя ID {user_id} прошел не успешною")

        await PaymentRepository.update_status_by_yookassa_id(yookassa_payment_id, PaymentStatus.cancelled)

        await send_notification_telegram(user_id, "❌ Платеж не прошел. Попробуйте снова")

        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("📋 Мои консультации", callback_data="my_consultations"))

        await bot.send_message(
            chat_id=user_id,
            text="📋 Пока вы можете посмотреть свои консультации. Ожидайте ответа с вами скоро свяжутся...",
            reply_markup=kb
        )
    return {"status": "ok"}

from src.telegram_bot.bot import bot
