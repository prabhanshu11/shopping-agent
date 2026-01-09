# Shopping Agent - AI Navigation Skills & Observations

## Purpose
This document captures learnings, challenges, and patterns observed by the AI agent while navigating e-commerce websites. These observations inform future improvements and help build a robust, adaptive agent system.

---

## Key Challenges Encountered

### 1. Address Selection Inconsistency (Amazon)
**Issue**: Even when the default address is set correctly in account settings, Amazon uses a "session-selected" address for cart operations. This can lead to items being added to cart with the wrong delivery address.

**Observation Date**: 2026-01-09

**Solution Approach**:
- Before adding any item, verify the delivery address shown on the product page
- Click on the address link in the buybox to trigger address selection popup
- Select the correct address from the popup list
- Verify the address changed before proceeding with "Add to Cart"

**Implementation Note**: Need to implement address verification protocol that checks address BEFORE and AFTER each cart operation.

---

### 2. Warranty/Protection Plan Modal Interference
**Issue**: When clicking "Add to Cart" on some products, Amazon shows a modal offering extended warranty/protection plans. This modal intercepts the cart add flow.

**Observation Date**: 2026-01-09

**Products Affected**: Small appliances, electronics, items with warranty options

**Critical Discovery**: The add-to-cart action is **queued** behind the warranty modal. Clicking "Add to Cart" registers the intent, but the item only appears in cart AFTER dismissing the modal. This means:
- The add-to-cart button click "succeeds" but item isn't in cart yet
- Dismissing via "No thanks" or X button releases the queued action
- Cart verification must happen AFTER modal dismissal, not immediately after button click

**Solution Approach**:
- After clicking "Add to Cart", immediately check for warranty modal
- Look for selectors: `#attachSiNoCov498-announce`, `#siNoCov498-announce`, `.a-button-close`
- Click "No thanks" or X to dismiss
- Wait 1-2 seconds for queued action to complete
- THEN verify cart count increased

---

### 3. Silent Cart Add Failures
**Issue**: Clicking "Add to Cart" button succeeds (selector found, click executed) but item doesn't appear in cart. No visible error message.

**Observation Date**: 2026-01-09

**Products Affected**: Zippo Fluid (B002GGW2BQ) - lighter fluid

**Possible Causes**:
- Product may have age/identity verification requirements (flammable materials)
- Regional restrictions on certain product categories
- JavaScript form submission being blocked
- Session/CSRF token expiration

**Attempted Solutions**:
1. Direct JavaScript click on button - Failed
2. Form submission via URL parameters - Failed
3. Scroll to button then click - Failed
4. Multiple retry attempts - Failed

**Recommended Action**: Flag products that fail cart add after 3 attempts for manual review

---

### 4. Browser Session Expiration
**Issue**: Browser sessions expire during long operations, requiring re-authentication.

**Observation Date**: 2026-01-09

**Solution Approach**:
- Detect sign-in redirect URLs
- Implement passkey/FIDO2 authentication flow with terminal PIN input
- Persist browser context between sessions when possible

---

### 5. DOM Selector Fragility
**Issue**: E-commerce sites frequently change their HTML structure, breaking hardcoded selectors.

**Examples Encountered**:
- Cart item count: Multiple possible selectors (`#nav-cart-count`, `#sc-subtotal-label-activecart`)
- Add to cart button: `#add-to-cart-button` vs `#nav-assist-add-to-cart`
- Delivery address: `#glow-ingress-line2` vs `#contextualIngressPtLabel_deliveryShortLine`

**Solution Approach**:
- Use multiple fallback selectors
- Prefer semantic selectors (aria labels, data attributes)
- Consider AI-based element identification for resilience

---

## Successful Patterns

### 1. Product Page Navigation
**Working Pattern**: Direct navigation to `/dp/{ASIN}` URLs works reliably
```
https://www.amazon.in/dp/B08HNB2FSH
```

### 2. Address Change Flow
**Working Pattern**:
1. Click on `#contextualIngressPtLink` in product buybox
2. Wait for address popup to appear
3. Click on first list item for default address
4. Wait 3 seconds for address update to propagate

### 3. Cart Verification
**Working Pattern**:
```javascript
Array.from(document.querySelectorAll("#sc-active-cart .sc-list-item-content"))
  .map(el => el.innerText.split("\n")[0])
  .filter(x => x.length > 10)
```

---

## Metrics to Track

### Cart Operations
- `cart_add_attempts` - Number of attempts to add item
- `cart_add_success` - Whether item was successfully added
- `cart_add_duration_ms` - Time from click to confirmed in cart
- `warranty_modal_encountered` - Boolean
- `address_verification_needed` - Boolean
- `address_change_performed` - Boolean

### Session Health
- `session_start_time` - When browser session started
- `login_required_count` - Times re-login was needed
- `browser_error_count` - Chrome error pages encountered

### Product Issues
- `product_asin` - Product identifier
- `add_to_cart_failed_reason` - Categorized failure reason
- `retry_count` - Number of retries before success/failure
- `manual_intervention_needed` - Boolean

---

## Future Improvements

### 1. Claude Agent SDK Integration

**Status**: IMPLEMENTED (2026-01-09)

**Installation**:
```bash
pip install claude-agent-sdk
# Or for this project:
pip install -e ".[ai]"
```

**Implementation**: `app/agent/shopping_agent.py`

The ShoppingAgent class provides:
1. **Deterministic API wrappers** - Direct calls to UI-Agent endpoints
2. **AI-powered fallback** - Uses Claude when deterministic approaches fail

**Key Features Used**:
- `ClaudeSDKClient` for interactive conversations
- `@tool` decorator for custom MCP tools
- `create_sdk_mcp_server()` for in-process tool servers

**Custom Tools Created**:
```python
@tool("navigate_to_product", "Navigate to product page", {"asin": str})
@tool("click_element", "Click an element", {"selector": str})
@tool("get_page_text", "Get page content", {})
@tool("verify_cart_item", "Check if item is in cart", {"asin": str})
@tool("dismiss_popup", "Dismiss any visible popup", {})
```

**Usage**:
```python
from app.agent import ShoppingAgent, ShoppingAgentConfig

async with ShoppingAgent() as agent:
    result = await agent.add_items_to_cart(
        items=[{"asin": "B08HNB2FSH", "name": "Smart Plug"}],
        expected_pincode="560043",
        use_ai_fallback=True,  # Enable Claude for error recovery
    )
```

**Benefits**:
- Self-healing: AI interprets page semantically, not via brittle selectors
- Adaptive: Can try alternative approaches when blocked
- Graceful degradation: Works without SDK, just loses AI fallback

**Sources**:
- [Claude Agent SDK GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [PyPI Package](https://pypi.org/project/claude-agent-sdk/)

### 2. Passkey Authentication Flow

**Status**: IMPLEMENTED (2026-01-09)

**Implementation**: UI-Agent `src/auth/passkey.py`

**API Endpoints**:
- `POST /auth/passkey/start` - Start passkey flow (enters email, clicks passkey button)
- `POST /auth/passkey/pin` - Submit PIN (types via ydotool, shows touch notification)
- `GET /auth/passkey/status` - Check current passkey flow state

**How It Works**:
1. Browser navigates to login page, enters email
2. Clicks "Sign in with passkey" button
3. API returns "waiting_for_pin" status
4. User/client provides PIN via `/auth/passkey/pin`
5. ydotool types PIN into browser's security dialog
6. Desktop notification prompts user to touch YubiKey

**Site Patterns Supported**:
- Amazon (email, continue, passkey button)
- Google (email, passkey button)
- GitHub (login, passkey button)

**Usage**:
```bash
# Start passkey flow
curl -X POST http://localhost:8000/auth/passkey/start \
  -H "Content-Type: application/json" \
  -d '{"url": "https://amazon.in/ap/signin", "email": "user@example.com", "site": "amazon"}'

# Provide PIN when prompted
curl -X POST http://localhost:8000/auth/passkey/pin \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
```

### 3. Comprehensive Logging Infrastructure
Build logging system that captures:
- Every navigation action with timestamps
- Screenshots at key decision points
- Success/failure outcomes with context
- Queryable database for analytics

### 4. Multi-Cart Type Handling (Amazon)
Amazon has multiple cart types:
- Regular cart
- Fresh cart (groceries)
- Saved for Later
- Subscribe & Save

Each needs specific handling and verification.

---

## Architecture Decision: AI Agent vs Deterministic Scripts

### Current Approach (Deterministic)
- Hardcoded CSS selectors
- Fixed navigation flows
- Brittle to site changes
- Fast when working, broken when site changes

### Recommended Approach (AI-Powered Agent)
Use Claude Agent SDK to create adaptive agents that:
1. **Interpret pages visually** - Understand page structure through multimodal LLM
2. **Navigate semantically** - "Find the add to cart button" vs `#add-to-cart-button`
3. **Self-correct** - Detect failures and try alternative approaches
4. **Learn from failures** - Log issues for continuous improvement

### Hybrid Implementation
- Use deterministic scripts for known, stable flows
- Fall back to AI agent for recovery and edge cases
- Collect training data from AI agent decisions
- Periodically update deterministic scripts based on learnings

---

## Session Log: 2026-01-09

### Task: Re-add 6 cancelled order items to cart

**Items to add**:
1. Wipro 10A smart plug (B08HNB2FSH) - SUCCESS
2. MYNEX 16GB DDR4 RAM (B0G38ZKQPY) - SUCCESS
3. EliteMotion Liquid Chalk (B0FR5C6MCD) - SUCCESS
4. Supply6 Electrolyte Mix (B0DN9FQDKK) - SUCCESS
5. EVEN Sharpening Stone (B0BKY7MFLY) - SUCCESS
6. Zippo Fluid (B002GGW2BQ) - SUCCESS (manual modal dismiss released queued action)

**Address Issue**: Initial adds went to Goa address (Chicalim 403710) instead of Bangalore (babusapalya 560043). Required mid-session address change.

**Total Time**: ~20 minutes for 6 items (should be <5 minutes)

**Bottlenecks**:
- Service restart required (UI-Agent not running new code)
- Address change workflow discovery
- Zippo Fluid repeated failures
