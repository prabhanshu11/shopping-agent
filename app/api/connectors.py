"""API routes for managing platform connectors."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_session
from app.models import Connector
from app.connectors import get_connector, CONNECTORS


router = APIRouter(prefix="/api/connectors", tags=["connectors"])


class ConnectorCreate(BaseModel):
    """Request model for creating/updating a connector."""
    platform: str
    api_key: str | None = None
    access_token: str | None = None
    config: dict | None = None


class ConnectorResponse(BaseModel):
    """Response model for connector information."""
    id: int
    platform: str
    display_name: str
    is_connected: bool
    has_api_key: bool
    has_access_token: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ConnectorResponse])
async def list_connectors(session: AsyncSession = Depends(get_session)):
    """Get list of all configured connectors."""
    result = await session.execute(select(Connector))
    connectors = result.scalars().all()

    # Convert to response format
    return [
        ConnectorResponse(
            id=c.id,
            platform=c.platform,
            display_name=c.display_name,
            is_connected=c.is_connected,
            has_api_key=bool(c.api_key),
            has_access_token=bool(c.access_token),
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in connectors
    ]


@router.get("/available")
async def list_available_platforms():
    """Get list of all available platforms (not necessarily configured)."""
    return {
        "platforms": [
            {
                "platform": "amazon",
                "display_name": "Amazon",
                "description": "E-commerce shopping",
                "requires": ["browser_automation"],  # No public buyer API
            },
            {
                "platform": "swiggy",
                "display_name": "Swiggy",
                "description": "Food delivery",
                "requires": ["api_key_or_browser"],  # TBD
            },
            {
                "platform": "blinkit",
                "display_name": "Blinkit",
                "description": "Quick commerce / Grocery",
                "requires": ["api_key_or_browser"],  # TBD
            },
            {
                "platform": "ubereats",
                "display_name": "Uber Eats",
                "description": "Food delivery",
                "requires": ["api_key_or_browser"],  # TBD
            },
        ]
    }


@router.post("/", response_model=ConnectorResponse)
async def create_or_update_connector(
    data: ConnectorCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create or update a platform connector."""
    # Validate platform
    if data.platform not in CONNECTORS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {data.platform}")

    # Check if connector already exists
    result = await session.execute(
        select(Connector).where(Connector.platform == data.platform)
    )
    connector = result.scalar_one_or_none()

    if connector:
        # Update existing
        if data.api_key:
            connector.api_key = data.api_key
        if data.access_token:
            connector.access_token = data.access_token
        if data.config:
            connector.config = data.config
    else:
        # Create new
        connector = Connector(
            platform=data.platform,
            display_name=data.platform.title(),
            api_key=data.api_key,
            access_token=data.access_token,
            config=data.config or {},
        )
        session.add(connector)

    # Test connection
    try:
        connector_instance = get_connector(
            data.platform,
            api_key=data.api_key,
            access_token=data.access_token,
        )
        is_connected = await connector_instance.authenticate()
        connector.is_connected = is_connected
    except Exception as e:
        connector.is_connected = False
        # Don't fail the request, just mark as not connected

    await session.commit()
    await session.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        platform=connector.platform,
        display_name=connector.display_name,
        is_connected=connector.is_connected,
        has_api_key=bool(connector.api_key),
        has_access_token=bool(connector.access_token),
        created_at=connector.created_at.isoformat(),
        updated_at=connector.updated_at.isoformat(),
    )


@router.delete("/{platform}")
async def delete_connector(
    platform: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a connector configuration."""
    result = await session.execute(
        select(Connector).where(Connector.platform == platform)
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    await session.delete(connector)
    await session.commit()

    return {"message": f"Connector {platform} deleted"}


@router.post("/{platform}/test")
async def test_connector(
    platform: str,
    session: AsyncSession = Depends(get_session),
):
    """Test if a connector is working."""
    result = await session.execute(
        select(Connector).where(Connector.platform == platform)
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    try:
        connector_instance = get_connector(
            platform,
            api_key=connector.api_key,
            access_token=connector.access_token,
        )
        is_working = await connector_instance.authenticate()

        return {
            "platform": platform,
            "is_working": is_working,
            "message": "Connected successfully" if is_working else "Connection failed",
        }
    except Exception as e:
        return {
            "platform": platform,
            "is_working": False,
            "message": str(e),
        }
