"""Database models for shopping agent."""

from sqlalchemy import String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from enum import Enum
from app.database import Base


class CartType(str, Enum):
    """Cart type enumeration for platforms with multiple cart systems."""
    REGULAR = "regular"
    FRESH = "fresh"  # Amazon Fresh, grocery carts


class RefundStatus(str, Enum):
    """Refund status for cancelled orders."""
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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
    cart_type: Mapped[str] = mapped_column(String(20), default=CartType.REGULAR.value)  # regular, fresh

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

    # Relationship to snapshots
    snapshots: Mapped[list["CartSnapshot"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


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

    # Cancellation details (populated when status='cancelled')
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # customer, seller, system
    refund_status: Mapped[str] = mapped_column(String(20), default=RefundStatus.NOT_APPLICABLE.value)
    refund_amount: Mapped[float | None] = mapped_column(nullable=True)
    refund_method: Mapped[str | None] = mapped_column(String(100), nullable=True)  # original_payment, gift_card, bank
    refund_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Payment details
    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # paid, failed, refunded

    # Timestamps
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CartSnapshot(Base):
    """Model for tracking cart history over time (indefinite retention)."""

    __tablename__ = "cart_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    platform: Mapped[str] = mapped_column(String(50))
    cart_type: Mapped[str] = mapped_column(String(20), default=CartType.REGULAR.value)

    # Snapshot data
    items: Mapped[dict] = mapped_column(JSON)  # Full cart items at snapshot time
    total_amount: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    item_count: Mapped[int] = mapped_column(default=0)

    # Change tracking (what changed since last snapshot)
    items_added: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Items new since last snapshot
    items_removed: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Items removed since last
    items_quantity_changed: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Quantity changes

    # Snapshot timestamp
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    cart: Mapped["Cart"] = relationship(back_populates="snapshots")
