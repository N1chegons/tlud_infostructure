from datetime import datetime
import re

from sqlalchemy import insert, select, update

from src.db import async_session
from src.logger_config import setup_logger
from src.telegram_bot.models import User, Consultation, ConsultationType

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
            ).returning(User.id)

            result = await session.execute(stmt)
            await session.commit()

            user_id = result.scalar_one()
            return user_id

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
    async def get_consultation_list(cls):
        async with async_session() as session:
            query = select(
                User.id,
                User.username,
                User.phone_number,
                User.date_of_birth,
                Consultation.id.label("consultation_id"),
                Consultation.is_viewed,
                Consultation.created_at,
            ).join(Consultation, User.id == Consultation.user_id).order_by(Consultation.is_viewed.asc(), Consultation.created_at.desc()).limit(10)

            result = await session.execute(query)
            rows = result.all()

            return rows

    @classmethod
    async def get_consultation_list_by_user(cls, user_id: int):
        async with async_session() as session:
            query = select(
                Consultation.id.label("consultation_id"),
                Consultation.created_at,
                Consultation.service_name,
                Consultation.is_viewed,
            ).where(Consultation.user_id == user_id).order_by(Consultation.is_viewed.asc(), Consultation.created_at.desc()).limit(10)

            result = await session.execute(query)
            rows = result.all()

            return rows

    @classmethod
    async def get_unviewed_consultation_list(cls):
        async with async_session() as session:
            query = select(
                User.id,
                User.username,
                User.phone_number,
                User.date_of_birth,
                Consultation.id.label("consultation_id"),
                Consultation.is_viewed,
                Consultation.created_at,
            ).join(Consultation, User.id == Consultation.user_id).order_by(Consultation.is_viewed.asc(),Consultation.created_at.desc()).where(Consultation.is_viewed == False).limit(10)

            result = await session.execute(query)
            rows = result.all()

            return rows

    @classmethod
    async def mark_as_viewed(cls, consultation_id: int):
        async with async_session() as session:
            await session.execute(
                update(Consultation).where(Consultation.id == consultation_id).values(is_viewed=True)
            )
            await session.commit()

    @classmethod
    async def create_consultation(cls, user_id: int, service_name: str, type: ConsultationType = ConsultationType.FREE):
        async with async_session() as session:
            logger.debug(f"Запись на консультацию для пользователя ID {user_id}")

            stmt = insert(Consultation).values(user_id=user_id, service_name=service_name, type=type)
            await session.execute(stmt)
            await session.commit()

            logger.debug(f"Пользователь успешно записался")

class AdminRepository:
    ADMIN_IDS=[677239271, 8177043133]

    @classmethod
    async def is_admin(cls, admin_id: int):
        return admin_id in cls.ADMIN_IDS

    @classmethod
    async def get_admin_ids(cls) -> list[int]:
        return cls.ADMIN_IDS

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

    @classmethod
    def validate_phone(cls, phone: str) -> bool:
        return bool(re.fullmatch(r"\+7\d{10}", phone))

