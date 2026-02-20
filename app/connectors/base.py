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
    id: str | None = None  # e.g. "addr_01"
    name: str
    address_line1: str  # House number and street name
    address_line2: str | None = None  # Apartment, suite, unit
    city: str
    state: str
    pincode: str
    country: str = "India"
    phone: str | None = None
    is_default: bool = False

    @classmethod
    def load_from_datalake(cls, address_id: str | None = None) -> list["AddressInfo"] | "AddressInfo":
        """Load addresses from datalake. Returns single address if id given, else all."""
        import json
        from pathlib import Path
        data_path = Path.home() / "Programs/datalake/data/personal/addresses.json"
        with open(data_path) as f:
            data = json.load(f)
        addresses = [cls(**addr) for addr in data["addresses"]]
        if address_id:
            return next(a for a in addresses if a.id == address_id)
        return addresses


class PurchaseItem(BaseModel):
    """Single item in a purchase."""
    name: str
    specs: str | None = None
    quantity: int = 1
    unit_price: float
    currency: str = "INR"
    category: str | None = None
    purpose: str | None = None


class Purchase(BaseModel):
    """A completed purchase/order record."""
    id: str  # e.g. "purchase_001"
    order_number: str
    date: str  # ISO date
    platform: str
    platform_url: str | None = None
    items: list[PurchaseItem]
    subtotal: float
    shipping: float = 0.0
    convenience_fee: float = 0.0
    total: float
    currency: str = "INR"
    payment_method: str | None = None
    billing_address_id: str | None = None
    shipping_address_id: str | None = None
    status: str = "confirmed"
    research_doc: str | None = None  # Path to related research

    @classmethod
    def load_from_datalake(cls) -> list["Purchase"]:
        """Load all purchases from datalake."""
        import json
        from pathlib import Path
        data_path = Path.home() / "Programs/datalake/data/personal/purchases.json"
        with open(data_path) as f:
            data = json.load(f)
        return [cls(**p) for p in data["purchases"]]


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
