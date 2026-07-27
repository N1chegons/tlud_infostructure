from datetime import datetime
import re

from sqlalchemy import insert, select, update, delete
from sqlalchemy.orm import joinedload
from yookassa import Payment, Webhook, Configuration

from src.config import settings
from src.db import async_session
from src.logger_config import setup_logger
from src.telegram_bot.models import User, Consultation, ConsultationType, Service

logger = setup_logger('repository', 'payment', 'payment_repository.log')

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SEKRET_KEY

class PaymentRepository:
    @classmethod
    async def create_payment_link(cls, amount: float, desc: str, user_id: int, service_id: int):
        payment = Payment.create({
            "amount": {
                "value": f"{amount}",
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "sbp"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/your_bot"
            },
            "capture": True,
            "description": desc,
            "metadata": {
                "user_id": str(user_id),
                "service_id": str(service_id)
            }
        })

        return {
            "payment_id": payment.payment_method.id,
            "payment_link": payment.confirmation.confirmation_url
        }

