"""Base connector interface for all platforms."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ProductSearchResult(BaseModel):
    """Standard product search result."""
    product_id: str
    title: str
    price: float
    currency: str = "INR"
    image_url: str | None = None
    availability: bool = True
    url: str | None = None
    platform: str


class CartItem(BaseModel):
    """Standard cart item."""
    product_id: str
    title: str
    quantity: int
    price: float
    currency: str = "INR"


class AddressInfo(BaseModel):
    """Standard address information."""
    name: str
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str
    pincode: str
    phone: str | None = None
    is_default: bool = False


class OrderInfo(BaseModel):
    """Standard order information."""
    order_id: str
    platform: str
    status: str
    items: list[CartItem]
    total_amount: float
    currency: str = "INR"
    tracking_url: str | None = None
    estimated_delivery: str | None = None


class BaseConnector(ABC):
    """Base class that all platform connectors must implement."""

    def __init__(self, api_key: str | None = None, access_token: str | None = None):
        """Initialize connector with authentication credentials."""
        self.api_key = api_key
        self.access_token = access_token

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'amazon', 'swiggy')."""
        pass

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the platform.
        Returns True if authentication is successful.
        """
        pass

    @abstractmethod
    async def search_products(self, query: str, limit: int = 10) -> list[ProductSearchResult]:
        """
        Search for products on the platform.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of product search results
        """
        pass

    @abstractmethod
    async def add_to_cart(self, product_id: str, quantity: int = 1) -> dict[str, Any]:
        """
        Add a product to the cart.

        Args:
            product_id: Platform-specific product identifier
            quantity: Quantity to add

        Returns:
            Cart information after adding the item
        """
        pass

    @abstractmethod
    async def get_cart(self) -> dict[str, Any]:
        """
        Get current cart contents.

        Returns:
            Cart information with items
        """
        pass

    @abstractmethod
    async def get_addresses(self) -> list[AddressInfo]:
        """
        Get saved addresses for the account.

        Returns:
            List of saved addresses
        """
        pass

    @abstractmethod
    async def verify_address_for_cart(self) -> dict[str, Any]:
        """
        Verify that the selected/default address can be used for current cart items.

        Returns:
            Address verification status with details
        """
        pass

    @abstractmethod
    async def get_orders(self, limit: int = 10) -> list[OrderInfo]:
        """
        Get recent orders.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of order information
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderInfo:
        """
        Get detailed status of a specific order.

        Args:
            order_id: Platform-specific order identifier

        Returns:
            Order information with tracking details
        """
        pass
