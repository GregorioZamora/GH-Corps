from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Commission(Base):
    """A custom work order: the client requests something and the team
    iterates with prototypes until a final solution is reached."""

    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=True)
    client_email: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="en_proceso")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="commissions")
    messages = relationship(
        "CommissionMessage", back_populates="commission", cascade="all, delete-orphan"
    )


class CommissionMessage(Base):
    """A message within a commission thread, possibly with an attachment
    (a prototype file uploaded by the customer or the team)."""

    __tablename__ = "commission_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commission_id: Mapped[int] = mapped_column(ForeignKey("commissions.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    attachment_path: Mapped[str] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    commission = relationship("Commission", back_populates="messages")
