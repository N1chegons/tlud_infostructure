from fastapi import FastAPI, Request

from src.logger_config import setup_logger
from src.payments.models import PaymentStatus
from src.payments.repository import PaymentRepository
from src.telegram_bot.meneger_sending import send_notification_telegram
from src.telegram_bot.repository import ConsultationRepository

app = FastAPI()


logger = setup_logger('webhook', 'payment_webhook', 'webhook_payment.log')

@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    logger.info("Поступил запрос")
    data = await request.json()
    metadata = data["object"]["metadata"]
    user_id = int(metadata["user_id"])
    service_id = int(metadata["service_id"])
    consultation_id = int(metadata["consultation_id"])
    payment_id = data["object"]["id"]

    if data.get("event") == "payment.succeeded":
        logger.info(f"Платеж для пользователя ID {user_id} прошел успешно")

        await PaymentRepository.update_payment_status(payment_id, PaymentStatus.succeeded)
        await ConsultationRepository.update_status(consultation_id, payment_id)

        await send_notification_telegram(user_id, "✅ Платеж успешно прошел")

    else:
        logger.info(f"Платеж для пользователя ID {user_id} прошел не успешною")

        await PaymentRepository.update_payment_status(payment_id, PaymentStatus.cancelled)

        await send_notification_telegram(user_id, "❌ Платеж не прошел")


    return {"status": "ok"}