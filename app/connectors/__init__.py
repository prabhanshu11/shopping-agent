"""Platform connectors for shopping agent."""

from app.connectors.base import BaseConnector, ProductSearchResult, CartItem, AddressInfo, OrderInfo
from app.connectors.amazon import AmazonConnector
from app.connectors.swiggy import SwiggyConnector
from app.connectors.blinkit import BlinKitConnector
from app.connectors.ubereats import UberEatsConnector


# Registry of available connectors
CONNECTORS = {
    "amazon": AmazonConnector,
    "swiggy": SwiggyConnector,
    "blinkit": BlinKitConnector,
    "ubereats": UberEatsConnector,
}


def get_connector(platform: str, **kwargs) -> BaseConnector:
    """
    Factory function to get a connector instance.

    Args:
        platform: Platform name (amazon, swiggy, blinkit, ubereats)
        **kwargs: Authentication credentials (api_key, access_token, etc.)

    Returns:
        Initialized connector instance
    """
    connector_class = CONNECTORS.get(platform.lower())
    if not connector_class:
        raise ValueError(f"Unknown platform: {platform}")
    return connector_class(**kwargs)


__all__ = [
    "BaseConnector",
    "ProductSearchResult",
    "CartItem",
    "AddressInfo",
    "OrderInfo",
    "AmazonConnector",
    "SwiggyConnector",
    "BlinKitConnector",
    "UberEatsConnector",
    "CONNECTORS",
    "get_connector",
]
