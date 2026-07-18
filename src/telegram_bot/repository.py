from sqlalchemy import insert, select

from src.db import async_session
from src.logger_config import setup_logger
from src.telegram_bot.models import User

logger = setup_logger('repository', 'telegram', 'repository.log')

class TelegramRepository:
    @classmethod
    async def get_user(cls, user_id: int):
        try:
            logger.info(f"get_user: starting for {user_id}")
            async with async_session() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                logger.info(f"get_user: found {user}")
                return user
        except Exception as e:
            logger.error(f"get_user: error {e}", exc_info=True)
            return None

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
