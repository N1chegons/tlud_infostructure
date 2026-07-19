from datetime import datetime
import re

from sqlalchemy import insert, select, update

from src.db import async_session
from src.logger_config import setup_logger
from src.telegram_bot.models import User, Consultation

logger = setup_logger('repository', 'telegram', 'repository.log')

class TelegramBotRepository:
    @classmethod
    async def get_user(cls, telegram_id: int):
        async with async_session() as session:
            logger.debug(f"Получение пользователя, входные данные: {telegram_id}")

            query = select(User).filter_by(telegram_id=telegram_id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Пользователь получен, данные: {user.id}, {user.phone_number}")

            else:
                logger.warning(f"Пользователя с TG_ID {telegram_id} не удалось получить")

            return user

    @classmethod
    async def register_user(cls, telegram_id: int, username: str, date_of_birth: str, phone_number: str):
        async with async_session() as session:
            logger.debug(f"Регситрация пользователя с TG_ID {telegram_id}")

            stmt = insert(User).values(
                telegram_id=telegram_id,
                username=username,
                date_of_birth=date_of_birth,
                phone_number=phone_number
            )
            await session.execute(stmt)
            await session.commit()

    @classmethod
    async def update_free_consultation_status(cls, telegram_id: int):
        async with async_session() as session:
            logger.debug(f"Изменение статуса has_free_consultation для пользователя TG_ID {telegram_id}")

            stmt = update(User).values(has_free_consultation=True).filter_by(telegram_id=telegram_id)
            await session.execute(stmt)
            await session.commit()

            logger.debug(f"Статус для пользователя TG_ID {telegram_id} успешно изменен")

class ConsultationRepository:
    @classmethod
    async def create_consultation(cls, user_id: int):
        async with async_session() as session:
            logger.debug(f"Запись на консультацию для пользователя ID {user_id}")

            stmt = insert(Consultation).values(user_id=user_id)
            await session.execute(stmt)
            await session.commit()

            logger.debug(f"Пользователь успешно записался")

class Validation:
    @classmethod
    def validate_name(cls, name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]+", name))

    @classmethod
    def validate_date(cls, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%d.%m.%Y")
            return True
        except ValueError:
            return False