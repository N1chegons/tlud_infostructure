from sqlalchemy import insert, select

from src.db import async_session
from src.logger_config import setup_logger
from src.telegram_bot.models import User

logger = setup_logger('repository', 'telegram', 'repository.log')

class TelegramRepository:
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
