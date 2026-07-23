import datetime
import enum

from sqlalchemy import BigInteger, text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base

class ConsultationType(enum.Enum):
    PAID = "paid"
    FREE = "free"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[str] = mapped_column(nullable=False)
    date_of_birth: Mapped[str] = mapped_column(nullable=False)
    phone_number: Mapped[str] = mapped_column(unique=True)

    has_free_consultation: Mapped[bool] = mapped_column(default=False)
    registration_step: Mapped[str] = mapped_column(default="none")

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )

    consultations: Mapped[list["Consultation"]] = relationship(back_populates="user")

class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=True)

    service_name: Mapped[str] = mapped_column(nullable=True)
    type: Mapped[ConsultationType] = mapped_column(default=ConsultationType.FREE)
    is_viewed: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )

    user: Mapped["User"] = relationship(back_populates="consultations")

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    price: Mapped[float] = mapped_column(nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )