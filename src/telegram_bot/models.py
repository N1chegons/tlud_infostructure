import datetime
from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[str] = mapped_column(nullable=False)
    date_of_birth: Mapped[str] = mapped_column(nullable=False)
    phone_number: Mapped[str] = mapped_column(unique=True,  index=True)

    has_free_consultation: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
