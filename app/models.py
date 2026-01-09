"""Database models for shopping agent."""

from sqlalchemy import String, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class Connector(Base):
    """Model for storing platform connector configurations."""

    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), unique=True)  # amazon, swiggy, blinkit, ubereats
    display_name: Mapped[str] = mapped_column(String(100))

    # Authentication
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Additional config (JSON field for flexibility)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Cart(Base):
    """Model for tracking carts across platforms."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50))
    cart_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Platform-specific cart ID

    # Cart details
    items: Mapped[dict] = mapped_column(JSON)  # List of items with details
    total_amount: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")

    # Address
    shipping_address: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, ordered, abandoned

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    """Model for tracking orders across platforms."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50))
    order_id: Mapped[str] = mapped_column(String(200))  # Platform-specific order ID

    # Order details
    items: Mapped[dict] = mapped_column(JSON)
    total_amount: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(10), default="INR")

    # Status tracking
    status: Mapped[str] = mapped_column(String(50))  # pending, confirmed, shipped, delivered, cancelled
    tracking_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
