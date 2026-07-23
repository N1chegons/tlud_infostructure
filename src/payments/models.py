import datetime
import enum

from sqlalchemy import BigInteger, text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

class PaymentStatus(enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    cancelled = "cancelled"
    failed = "failed"

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[str] = mapped_column(unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))

    amount: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(default=PaymentStatus.pending)

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
    paid_at: Mapped[datetime.datetime] = mapped_column(nullable=True)