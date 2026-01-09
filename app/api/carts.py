"""API routes for cart management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.database import get_session
from app.models import Connector, Cart
from app.connectors import get_connector


router = APIRouter(prefix="/api/carts", tags=["carts"])


class AddToCartRequest(BaseModel):
    """Request model for adding items to cart."""
    platform: str
    product_id: str
    quantity: int = 1


class CartResponse(BaseModel):
    """Response model for cart information."""
    id: int
    platform: str
    cart_id: str | None
    items: dict
    total_amount: float | None
    currency: str
    status: str
    created_at: str
    updated_at: str


@router.post("/add")
async def add_to_cart(
    request: AddToCartRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Add a product to cart on specified platform.

    Args:
        request: Product details and platform

    Returns:
        Cart update confirmation
    """
    # Get connector
    result = await session.execute(
        select(Connector).where(Connector.platform == request.platform)
    )
    connector_model = result.scalar_one_or_none()

    if not connector_model:
        raise HTTPException(status_code=404, detail="Connector not configured")

    connector = get_connector(
        request.platform,
        api_key=connector_model.api_key,
        access_token=connector_model.access_token,
    )

    # Add to cart via connector
    try:
        result = await connector.add_to_cart(request.product_id, request.quantity)

        # Update or create cart record in database
        cart_result = await session.execute(
            select(Cart).where(
                Cart.platform == request.platform,
                Cart.status == "active",
            )
        )
        cart = cart_result.scalar_one_or_none()

        if not cart:
            cart = Cart(
                platform=request.platform,
                items={"products": []},
                status="active",
            )
            session.add(cart)

        # Add item to cart items
        cart.items.setdefault("products", []).append({
            "product_id": request.product_id,
            "quantity": request.quantity,
            "added_at": datetime.utcnow().isoformat(),
        })

        await session.commit()

        return {
            "success": True,
            "message": f"Added {request.quantity}x {request.product_id} to {request.platform} cart",
            "cart_info": result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to cart: {str(e)}")


@router.get("/{platform}", response_model=CartResponse | None)
async def get_cart(
    platform: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Get current cart for a platform.

    Args:
        platform: Platform name

    Returns:
        Cart contents
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

    # Get cart from platform
    try:
        cart_data = await connector.get_cart()

        # Also get from database
        db_result = await session.execute(
            select(Cart).where(
                Cart.platform == platform,
                Cart.status == "active",
            )
        )
        cart = db_result.scalar_one_or_none()

        if cart:
            return CartResponse(
                id=cart.id,
                platform=cart.platform,
                cart_id=cart.cart_id,
                items=cart.items,
                total_amount=cart.total_amount,
                currency=cart.currency,
                status=cart.status,
                created_at=cart.created_at.isoformat(),
                updated_at=cart.updated_at.isoformat(),
            )

        return None

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cart: {str(e)}")


@router.post("/{platform}/verify-address")
async def verify_cart_address(
    platform: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Verify that the selected address works for all cart items.

    Args:
        platform: Platform name

    Returns:
        Address verification status
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

    # Verify address
    try:
        verification = await connector.verify_address_for_cart()
        return verification
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify address: {str(e)}",
        )


@router.get("/")
async def list_all_carts(session: AsyncSession = Depends(get_session)):
    """Get all active carts across all platforms."""
    result = await session.execute(
        select(Cart).where(Cart.status == "active")
    )
    carts = result.scalars().all()

    return [
        CartResponse(
            id=cart.id,
            platform=cart.platform,
            cart_id=cart.cart_id,
            items=cart.items,
            total_amount=cart.total_amount,
            currency=cart.currency,
            status=cart.status,
            created_at=cart.created_at.isoformat(),
            updated_at=cart.updated_at.isoformat(),
        )
        for cart in carts
    ]
