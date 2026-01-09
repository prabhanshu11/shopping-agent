"""API routes for order tracking."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_session
from app.models import Connector, Order
from app.connectors import get_connector
from app.connectors.base import OrderInfo


router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderResponse(BaseModel):
    """Response model for order information."""
    id: int
    platform: str
    order_id: str
    items: dict
    total_amount: float
    currency: str
    status: str
    tracking_info: dict | None
    ordered_at: str
    estimated_delivery: str | None
    delivered_at: str | None


@router.get("/{platform}", response_model=list[OrderInfo])
async def get_platform_orders(
    platform: str,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    """
    Get recent orders from a specific platform.

    Args:
        platform: Platform name
        limit: Maximum number of orders to fetch

    Returns:
        List of recent orders
    """
    # Get connector
    result = await session.execute(
        select(Connector).where(Connector.platform == platform)
    )
    connector_model = result.scalar_one_or_none()

    if not connector_model:
        raise HTTPException(status_code=404, detail="Connector not configured")

    connector = get_connector(
        platform,
        api_key=connector_model.api_key,
        access_token=connector_model.access_token,
    )

    # Fetch orders
    try:
        orders = await connector.get_orders(limit)
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")


@router.get("/{platform}/{order_id}", response_model=OrderInfo)
async def get_order_details(
    platform: str,
    order_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed information about a specific order.

    Args:
        platform: Platform name
        order_id: Order ID

    Returns:
        Detailed order information with tracking
    """
    # Get connector
    result = await session.execute(
        select(Connector).where(Connector.platform == platform)
    )
    connector_model = result.scalar_one_or_none()

    if not connector_model:
        raise HTTPException(status_code=404, detail="Connector not configured")

    connector = get_connector(
        platform,
        api_key=connector_model.api_key,
        access_token=connector_model.access_token,
    )

    # Get order details
    try:
        order = await connector.get_order_status(order_id)
        return order
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get order details: {str(e)}",
        )


@router.get("/")
async def get_all_orders(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    """
    Get recent orders from all platforms.

    Args:
        limit: Maximum orders per platform

    Returns:
        Aggregated orders from all platforms
    """
    # Get all connected platforms
    result = await session.execute(
        select(Connector).where(Connector.is_connected == True)
    )
    connectors = result.scalars().all()

    all_orders = []

    for connector_model in connectors:
        try:
            connector = get_connector(
                connector_model.platform,
                api_key=connector_model.api_key,
                access_token=connector_model.access_token,
            )
            orders = await connector.get_orders(limit)
            all_orders.extend(orders)
        except Exception as e:
            # Log error but continue with other platforms
            continue

    # Sort by order date (most recent first)
    # all_orders.sort(key=lambda x: x.get("ordered_at", ""), reverse=True)

    return {
        "total_orders": len(all_orders),
        "orders": all_orders,
    }
