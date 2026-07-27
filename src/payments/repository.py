from datetime import datetime

from sqlalchemy import insert, update, select
from yookassa import Payment, Configuration

from src.config import settings
from src.db import async_session
from src.logger_config import setup_logger
from src.payments.models import Payment as PaymentModel, PaymentStatus

logger = setup_logger('repository', 'payment', 'payment_repository.log')

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SEKRET_KEY

class PaymentRepository:
    @classmethod
    async def save_payment(cls, amount: float,  user_id: int, service_id: int, payment_id: int):
        async with async_session() as session:
            logger.debug(f"Платеж сохранен для пользователя ID {user_id}, консультация ID {service_id}, цена {amount}")
            stmt = insert(PaymentModel).values(amount=amount, user_id=user_id, service_id=service_id, payment_id=payment_id)
            await session.execute(stmt)
            await session.commit()

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
                "return_url": "https://t.me/psylogic_cifr_bot"
            },
            "capture": True,
            "description": desc,
            "metadata": {
                "user_id": str(user_id),
                "service_id": str(service_id)
            }
        })

        logger.debug(f"Ссылка для пользователя ID {user_id} создана, конслуьтация ID {service_id}")
        return {
            "payment_id": payment.payment_method.id,
            "payment_link": payment.confirmation.confirmation_url
        }

    @classmethod
    async def update_payment_status(cls, payment_id: int, status_payment: PaymentStatus):
        async with async_session() as session:
            logger.debug(f"Изменение статуса платежа ID {payment_id}, статус платежа: {status_payment}")
            paid_at = datetime.now()

            stmt = update(PaymentModel).values(status=status_payment, paid_at=paid_at)
            await session.execute(stmt)
            await session.commit()

    @classmethod
    async def get_by_yookassa_id(cls, yookassa_payment_id: str):
        async with async_session() as session:
            result = await session.execute(
                select(PaymentModel).where(PaymentModel.payment_id == yookassa_payment_id)
            )
            return result.scalar_one_or_none()

    @classmethod
    async def update_status_by_yookassa_id(cls, yookassa_payment_id: str, status: str):
        async with async_session() as session:
            await session.execute(
                update(PaymentModel)
                .where(PaymentModel.payment_id == yookassa_payment_id)
                .values(status=status)
            )
            await session.commit()