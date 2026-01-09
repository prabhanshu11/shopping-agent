"""API routes for product search and research."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_session
from app.models import Connector
from app.connectors import get_connector
from app.connectors.base import ProductSearchResult


router = APIRouter(prefix="/api/products", tags=["products"])


class ProductSearchRequest(BaseModel):
    """Request model for product search."""
    query: str
    platform: str
    limit: int = 10


@router.post("/search", response_model=list[ProductSearchResult])
async def search_products(
    request: ProductSearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Search for products on a specific platform.

    Args:
        request: Search parameters (query, platform, limit)

    Returns:
        List of product search results
    """
    # Get connector configuration
    result = await session.execute(
        select(Connector).where(Connector.platform == request.platform)
    )
    connector_model = result.scalar_one_or_none()

    if not connector_model:
        raise HTTPException(
            status_code=404,
            detail=f"Connector for {request.platform} not configured. Please set it up first.",
        )

    # Initialize connector
    connector = get_connector(
        request.platform,
        api_key=connector_model.api_key,
        access_token=connector_model.access_token,
    )

    # Search products
    try:
        products = await connector.search_products(request.query, request.limit)
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/research")
async def research_product(
    query: str = Query(..., description="Product to research"),
    platforms: str = Query("amazon", description="Comma-separated platforms to search"),
):
    """
    Research a product across multiple platforms.

    This endpoint searches multiple platforms and compares prices,
    availability, and delivery options.

    Args:
        query: Product name or description
        platforms: Comma-separated list of platforms (default: amazon)

    Returns:
        Aggregated search results from all platforms
    """
    # TODO: Implement multi-platform search and comparison
    # This will:
    # 1. Search on all specified platforms in parallel
    # 2. Aggregate results
    # 3. Sort by price/relevance
    # 4. Show comparison table

    platform_list = [p.strip() for p in platforms.split(",")]

    return {
        "query": query,
        "platforms_searched": platform_list,
        "results": [],
        "message": "Multi-platform research not yet implemented",
    }
