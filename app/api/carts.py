"""API routes for cart management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Any

from app.database import get_session
from app.models import Connector, Cart, CartSnapshot, CartType
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
    cart_type: str
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
                cart_type=cart.cart_type,
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
            cart_type=cart.cart_type,
            items=cart.items,
            total_amount=cart.total_amount,
            currency=cart.currency,
            status=cart.status,
            created_at=cart.created_at.isoformat(),
            updated_at=cart.updated_at.isoformat(),
        )
        for cart in carts
    ]


# ============ CART HISTORY / SNAPSHOT ENDPOINTS ============


class CartSnapshotResponse(BaseModel):
    """Response model for cart snapshot."""
    id: int
    cart_id: int
    platform: str
    cart_type: str
    items: dict
    total_amount: float | None
    currency: str
    item_count: int
    items_added: dict | None
    items_removed: dict | None
    items_quantity_changed: dict | None
    snapshot_at: str


def _compute_cart_diff(
    old_items: list[dict],
    new_items: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Compute the difference between two cart states.

    Returns:
        Tuple of (items_added, items_removed, items_quantity_changed)
    """
    old_by_asin = {item.get("asin"): item for item in old_items if item.get("asin")}
    new_by_asin = {item.get("asin"): item for item in new_items if item.get("asin")}

    old_asins = set(old_by_asin.keys())
    new_asins = set(new_by_asin.keys())

    # Items added (in new but not in old)
    added = [new_by_asin[asin] for asin in (new_asins - old_asins)]

    # Items removed (in old but not in new)
    removed = [old_by_asin[asin] for asin in (old_asins - new_asins)]

    # Items with quantity changes
    quantity_changed = []
    for asin in (old_asins & new_asins):
        old_qty = old_by_asin[asin].get("quantity", 1)
        new_qty = new_by_asin[asin].get("quantity", 1)
        if old_qty != new_qty:
            quantity_changed.append({
                **new_by_asin[asin],
                "old_quantity": old_qty,
                "new_quantity": new_qty,
            })

    return added, removed, quantity_changed


@router.post("/{platform}/snapshot")
async def create_cart_snapshot(
    platform: str,
    cart_type: str = "regular",
    session: AsyncSession = Depends(get_session),
):
    """
    Create a snapshot of the current cart state for history tracking.

    This fetches the live cart data and saves it as a snapshot.
    Compares with previous snapshot to track changes.

    Args:
        platform: Platform name (e.g., 'amazon')
        cart_type: Cart type ('regular' or 'fresh')

    Returns:
        The created snapshot with change information
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

    # Get current cart from platform
    try:
        cart_data = await connector.get_cart()

        # For Amazon, select the right cart based on cart_type
        if platform == "amazon":
            if cart_type == "fresh":
                cart_section = cart_data.get("fresh_cart", {})
            else:
                cart_section = cart_data.get("regular_cart", {})
            items = cart_section.get("items", [])
            subtotal_str = cart_section.get("subtotal")
        else:
            items = cart_data.get("items", [])
            subtotal_str = cart_data.get("subtotal")

        # Parse subtotal
        total_amount = None
        if subtotal_str:
            try:
                total_amount = float(subtotal_str.replace("₹", "").replace(",", "").strip())
            except (ValueError, AttributeError):
                pass

        # Get or create Cart record
        cart_result = await session.execute(
            select(Cart).where(
                Cart.platform == platform,
                Cart.cart_type == cart_type,
                Cart.status == "active",
            )
        )
        cart = cart_result.scalar_one_or_none()

        if not cart:
            cart = Cart(
                platform=platform,
                cart_type=cart_type,
                cart_id=f"{platform}-{cart_type}",
                items={"products": items},
                total_amount=total_amount,
                status="active",
            )
            session.add(cart)
            await session.flush()  # Get the ID

        # Get previous snapshot for comparison
        prev_snapshot_result = await session.execute(
            select(CartSnapshot)
            .where(
                CartSnapshot.cart_id == cart.id,
                CartSnapshot.cart_type == cart_type,
            )
            .order_by(desc(CartSnapshot.snapshot_at))
            .limit(1)
        )
        prev_snapshot = prev_snapshot_result.scalar_one_or_none()

        # Compute diff if we have a previous snapshot
        items_added, items_removed, items_qty_changed = [], [], []
        if prev_snapshot:
            prev_items = prev_snapshot.items.get("products", [])
            items_added, items_removed, items_qty_changed = _compute_cart_diff(
                prev_items, items
            )

        # Create new snapshot
        snapshot = CartSnapshot(
            cart_id=cart.id,
            platform=platform,
            cart_type=cart_type,
            items={"products": items},
            total_amount=total_amount,
            currency="INR",
            item_count=len(items),
            items_added={"products": items_added} if items_added else None,
            items_removed={"products": items_removed} if items_removed else None,
            items_quantity_changed={"products": items_qty_changed} if items_qty_changed else None,
        )
        session.add(snapshot)

        # Update cart with latest data
        cart.items = {"products": items}
        cart.total_amount = total_amount
        cart.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(snapshot)

        return {
            "snapshot_id": snapshot.id,
            "cart_id": cart.id,
            "platform": platform,
            "cart_type": cart_type,
            "items": items,
            "item_count": len(items),
            "total_amount": total_amount,
            "snapshot_at": snapshot.snapshot_at.isoformat(),
            "changes": {
                "items_added": items_added,
                "items_removed": items_removed,
                "items_quantity_changed": items_qty_changed,
            },
            "has_changes": bool(items_added or items_removed or items_qty_changed),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create cart snapshot: {str(e)}",
        )


@router.get("/{platform}/history")
async def get_cart_history(
    platform: str,
    cart_type: str = "regular",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """
    Get cart history (snapshots) for a platform.

    Snapshots are retained indefinitely for full history tracking.

    Args:
        platform: Platform name
        cart_type: Cart type ('regular' or 'fresh')
        limit: Max snapshots to return

    Returns:
        List of cart snapshots with change information
    """
    # Get cart
    cart_result = await session.execute(
        select(Cart).where(
            Cart.platform == platform,
            Cart.cart_type == cart_type,
        )
    )
    cart = cart_result.scalar_one_or_none()

    if not cart:
        return {
            "platform": platform,
            "cart_type": cart_type,
            "snapshots": [],
            "count": 0,
        }

    # Get snapshots
    result = await session.execute(
        select(CartSnapshot)
        .where(CartSnapshot.cart_id == cart.id)
        .order_by(desc(CartSnapshot.snapshot_at))
        .limit(limit)
    )
    snapshots = result.scalars().all()

    return {
        "platform": platform,
        "cart_type": cart_type,
        "cart_id": cart.id,
        "snapshots": [
            CartSnapshotResponse(
                id=s.id,
                cart_id=s.cart_id,
                platform=s.platform,
                cart_type=s.cart_type,
                items=s.items,
                total_amount=s.total_amount,
                currency=s.currency,
                item_count=s.item_count,
                items_added=s.items_added,
                items_removed=s.items_removed,
                items_quantity_changed=s.items_quantity_changed,
                snapshot_at=s.snapshot_at.isoformat(),
            )
            for s in snapshots
        ],
        "count": len(snapshots),
    }


@router.get("/{platform}/changes")
async def get_cart_changes(
    platform: str,
    cart_type: str = "regular",
    since_hours: int = 24,
    session: AsyncSession = Depends(get_session),
):
    """
    Get cart changes within a time period.

    Useful for answering "what changed in my cart yesterday?"

    Args:
        platform: Platform name
        cart_type: Cart type
        since_hours: How many hours back to look (default 24)

    Returns:
        Aggregated changes (items added/removed) in the time period
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=since_hours)

    # Get cart
    cart_result = await session.execute(
        select(Cart).where(
            Cart.platform == platform,
            Cart.cart_type == cart_type,
        )
    )
    cart = cart_result.scalar_one_or_none()

    if not cart:
        return {
            "platform": platform,
            "cart_type": cart_type,
            "since_hours": since_hours,
            "changes": {"added": [], "removed": [], "quantity_changed": []},
        }

    # Get snapshots in time range
    result = await session.execute(
        select(CartSnapshot)
        .where(
            CartSnapshot.cart_id == cart.id,
            CartSnapshot.snapshot_at >= cutoff,
        )
        .order_by(CartSnapshot.snapshot_at)
    )
    snapshots = result.scalars().all()

    # Aggregate changes
    all_added = []
    all_removed = []
    all_qty_changed = []

    for s in snapshots:
        if s.items_added:
            all_added.extend(s.items_added.get("products", []))
        if s.items_removed:
            all_removed.extend(s.items_removed.get("products", []))
        if s.items_quantity_changed:
            all_qty_changed.extend(s.items_quantity_changed.get("products", []))

    return {
        "platform": platform,
        "cart_type": cart_type,
        "since_hours": since_hours,
        "since": cutoff.isoformat(),
        "snapshot_count": len(snapshots),
        "changes": {
            "added": all_added,
            "removed": all_removed,
            "quantity_changed": all_qty_changed,
        },
        "summary": {
            "items_added_count": len(all_added),
            "items_removed_count": len(all_removed),
            "quantity_changes_count": len(all_qty_changed),
        },
    }
