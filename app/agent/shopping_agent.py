"""Shopping Agent using Claude Agent SDK for adaptive navigation.

This agent uses Claude to intelligently navigate e-commerce sites,
handling edge cases that deterministic scripts can't handle.

Architecture:
    Shopping Agent (this module)
        |
        v
    Claude Agent SDK (claude-agent-sdk)
        |
        v
    Custom Tools (MCP server in-process)
        |
        v
    UI-Agent API (http://localhost:8000)

Usage:
    agent = ShoppingAgent(ui_agent_url="http://localhost:8000")
    result = await agent.add_items_to_cart(
        items=[{"asin": "B08HNB2FSH", "name": "Smart Plug"}],
        expected_pincode="560043",
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ShoppingAgentConfig:
    """Configuration for the shopping agent."""
    ui_agent_url: str = "http://localhost:8000"
    platform: str = "amazon"
    region: str = "in"  # amazon.in
    max_retries: int = 3
    timeout_seconds: int = 60
    # Claude Agent SDK options
    model: str = "claude-sonnet-4-20250514"
    max_turns: int = 10


@dataclass
class CartItem:
    """An item to add to cart."""
    asin: str
    name: str = ""
    quantity: int = 1


@dataclass
class CartResult:
    """Result of a cart operation."""
    success: bool
    items_added: list[str] = field(default_factory=list)
    items_failed: list[dict] = field(default_factory=list)
    address_verified: bool = False
    message: str = ""


class ShoppingAgent:
    """AI-powered shopping agent using Claude Agent SDK.

    This agent wraps the UI-Agent API calls and uses Claude for
    intelligent decision-making when things go wrong.
    """

    def __init__(self, config: ShoppingAgentConfig | None = None):
        """Initialize the shopping agent.

        Args:
            config: Agent configuration
        """
        self.config = config or ShoppingAgentConfig()
        self.http_client = httpx.AsyncClient(
            base_url=self.config.ui_agent_url,
            timeout=self.config.timeout_seconds,
        )
        self._claude_client = None

    async def close(self):
        """Close the agent and release resources."""
        await self.http_client.aclose()
        if self._claude_client:
            await self._claude_client.__aexit__(None, None, None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # Direct UI-Agent API Wrappers (deterministic)
    # =========================================================================

    async def add_to_cart_simple(self, asin: str, quantity: int = 1) -> dict:
        """Add item to cart using simple API (no verification)."""
        response = await self.http_client.post(
            "/amazon/add-to-cart",
            json={"product_id": asin, "quantity": quantity},
        )
        return response.json()

    async def add_to_cart_verified(
        self,
        asin: str,
        quantity: int = 1,
        expected_pincode: str | None = None,
    ) -> dict:
        """Add item to cart with address verification and modal handling."""
        response = await self.http_client.post(
            "/amazon/add-to-cart-verified",
            json={
                "product_id": asin,
                "quantity": quantity,
                "expected_pincode": expected_pincode,
            },
        )
        return response.json()

    async def change_address(
        self,
        expected_pincode: str,
        product_id: str | None = None,
    ) -> dict:
        """Change delivery address."""
        response = await self.http_client.post(
            "/amazon/change-address",
            json={
                "expected_pincode": expected_pincode,
                "product_id": product_id,
            },
        )
        return response.json()

    async def get_cart(self) -> dict:
        """Get current cart contents."""
        response = await self.http_client.get("/amazon/cart")
        return response.json()

    async def verify_address(self) -> dict:
        """Verify delivery address in cart."""
        response = await self.http_client.post("/amazon/verify-address")
        return response.json()

    async def take_screenshot(self, path: str | None = None) -> bytes | None:
        """Take a screenshot of current browser state."""
        try:
            params = {"path": path} if path else {}
            response = await self.http_client.get("/browser/screenshot", params=params)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            logger.warning("Failed to take screenshot: %s", e)
        return None

    # =========================================================================
    # AI-Powered Operations (using Claude Agent SDK)
    # =========================================================================

    async def add_items_to_cart(
        self,
        items: list[CartItem | dict],
        expected_pincode: str | None = None,
        use_ai_fallback: bool = True,
    ) -> CartResult:
        """Add multiple items to cart with intelligent error handling.

        This method first tries the deterministic approach. If it fails
        and use_ai_fallback is True, it uses Claude to adaptively
        navigate and solve the problem.

        Args:
            items: List of items to add
            expected_pincode: Expected delivery pincode
            use_ai_fallback: Use Claude for error recovery

        Returns:
            CartResult with success/failure details
        """
        result = CartResult(success=False)

        # Normalize items
        cart_items = [
            CartItem(**item) if isinstance(item, dict) else item
            for item in items
        ]

        for item in cart_items:
            logger.info("Adding to cart: %s (%s)", item.name or item.asin, item.asin)

            # Try deterministic approach first
            for attempt in range(self.config.max_retries):
                try:
                    response = await self.add_to_cart_verified(
                        asin=item.asin,
                        quantity=item.quantity,
                        expected_pincode=expected_pincode,
                    )

                    if response.get("success"):
                        result.items_added.append(item.asin)
                        result.address_verified = response.get("address_verified", False)
                        logger.info("Successfully added: %s", item.asin)
                        break
                    else:
                        logger.warning(
                            "Attempt %d failed for %s: %s",
                            attempt + 1, item.asin, response.get("message")
                        )

                except Exception as e:
                    logger.warning(
                        "Attempt %d error for %s: %s",
                        attempt + 1, item.asin, str(e)
                    )

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2)  # Brief pause before retry

            else:
                # All retries failed
                if use_ai_fallback:
                    logger.info("Trying AI fallback for %s", item.asin)
                    ai_result = await self._ai_add_to_cart(item, expected_pincode)
                    if ai_result.get("success"):
                        result.items_added.append(item.asin)
                        logger.info("AI fallback succeeded for: %s", item.asin)
                    else:
                        result.items_failed.append({
                            "asin": item.asin,
                            "name": item.name,
                            "error": ai_result.get("error", "AI fallback failed"),
                        })
                else:
                    result.items_failed.append({
                        "asin": item.asin,
                        "name": item.name,
                        "error": "Max retries exceeded",
                    })

        result.success = len(result.items_failed) == 0
        result.message = (
            f"Added {len(result.items_added)}/{len(cart_items)} items"
            + (f", {len(result.items_failed)} failed" if result.items_failed else "")
        )

        return result

    async def _ai_add_to_cart(
        self,
        item: CartItem,
        expected_pincode: str | None = None,
    ) -> dict:
        """Use Claude Agent SDK to add item to cart adaptively.

        This method is called when deterministic approaches fail.
        Claude will analyze the situation and try alternative strategies.
        """
        try:
            # Check if claude-agent-sdk is available
            from claude_agent_sdk import (
                ClaudeAgentOptions,
                ClaudeSDKClient,
                tool,
                create_sdk_mcp_server,
            )
        except ImportError:
            logger.warning("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")
            return {"success": False, "error": "claude-agent-sdk not installed"}

        # Create custom tools for shopping operations
        @tool("navigate_to_product", "Navigate to a product page on Amazon", {"asin": str})
        async def navigate_to_product(args):
            url = f"https://www.amazon.{self.config.region}/dp/{args['asin']}"
            response = await self.http_client.post(
                "/browser/navigate",
                json={"url": url, "wait_until": "networkidle"},
            )
            return {"content": [{"type": "text", "text": f"Navigated to {url}"}]}

        @tool("click_element", "Click an element on the page", {"selector": str})
        async def click_element(args):
            response = await self.http_client.post(
                "/browser/click",
                json={"selector": args["selector"]},
            )
            result = response.json()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Clicked: {args['selector']} - {'success' if result.get('success') else 'failed'}"
                }]
            }

        @tool("get_page_text", "Get visible text from the current page", {})
        async def get_page_text(args):
            response = await self.http_client.get("/browser/content")
            content = response.json()
            # Extract just the page title and some context
            return {
                "content": [{
                    "type": "text",
                    "text": f"Page: {content.get('title', 'Unknown')}\nURL: {content.get('url', '')}"
                }]
            }

        @tool("verify_cart_item", "Check if an item is in the cart", {"asin": str})
        async def verify_cart_item(args):
            cart = await self.get_cart()
            items = cart.get("regular_cart", {}).get("items", [])
            found = any(i.get("asin") == args["asin"] for i in items)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Item {args['asin']} in cart: {found}"
                }]
            }

        @tool("dismiss_popup", "Try to dismiss any visible popup", {})
        async def dismiss_popup(args):
            # Try various dismiss methods
            selectors = [
                "#attachSiNoCov498-announce",
                ".a-button-close",
                "[data-action='a-popover-close']",
            ]
            for selector in selectors:
                try:
                    response = await self.http_client.post(
                        "/browser/click",
                        json={"selector": selector},
                    )
                    if response.json().get("success"):
                        return {"content": [{"type": "text", "text": f"Dismissed popup using: {selector}"}]}
                except Exception:
                    continue
            return {"content": [{"type": "text", "text": "No popup found to dismiss"}]}

        # Create SDK MCP server with our tools
        server = create_sdk_mcp_server(
            name="shopping-tools",
            version="1.0.0",
            tools=[
                navigate_to_product,
                click_element,
                get_page_text,
                verify_cart_item,
                dismiss_popup,
            ],
        )

        # Configure Claude Agent
        options = ClaudeAgentOptions(
            system_prompt=f"""You are a shopping assistant navigating Amazon.{self.config.region}.
Your goal is to add items to cart reliably.

Current task: Add product {item.asin} ({item.name}) to cart.
{"Expected delivery pincode: " + expected_pincode if expected_pincode else ""}

Available strategies:
1. Navigate to product page
2. Click "Add to Cart" button
3. Dismiss any popups (warranty offers, etc.)
4. Verify item was added to cart

If the standard approach fails, try:
- Refreshing the page
- Clicking different selectors (#add-to-cart-button, #nav-assist-add-to-cart)
- Dismissing popups before clicking
- Waiting and retrying

Always verify the item is in cart at the end.
""",
            mcp_servers={"shopping": server},
            allowed_tools=[
                "mcp__shopping__navigate_to_product",
                "mcp__shopping__click_element",
                "mcp__shopping__get_page_text",
                "mcp__shopping__verify_cart_item",
                "mcp__shopping__dismiss_popup",
            ],
            max_turns=self.config.max_turns,
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(
                    f"Add product {item.asin} to cart. "
                    f"Navigate to the product, click Add to Cart, handle any popups, "
                    f"and verify the item is in cart."
                )

                # Process responses
                final_message = None
                async for msg in client.receive_response():
                    logger.debug("Claude response: %s", msg)
                    final_message = msg

                # Verify item was added
                cart = await self.get_cart()
                items = cart.get("regular_cart", {}).get("items", [])
                if any(i.get("asin") == item.asin for i in items):
                    return {"success": True}
                else:
                    return {"success": False, "error": "Item not found in cart after AI attempt"}

        except Exception as e:
            logger.error("AI fallback error: %s", e)
            return {"success": False, "error": str(e)}


# Convenience function for one-off operations
async def quick_add_to_cart(
    asin: str,
    expected_pincode: str | None = None,
    ui_agent_url: str = "http://localhost:8000",
) -> dict:
    """Quick add-to-cart without creating a full agent instance."""
    async with ShoppingAgent(ShoppingAgentConfig(ui_agent_url=ui_agent_url)) as agent:
        result = await agent.add_to_cart_verified(
            asin=asin,
            expected_pincode=expected_pincode,
        )
        return result
