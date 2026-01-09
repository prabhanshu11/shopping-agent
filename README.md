# Shopping Agent

Multi-platform shopping assistant that helps manage carts, track orders, and research products across Amazon, Swiggy, Blinkit, and Uber Eats.

## Features

- **Platform Connectors**: Connect to multiple shopping platforms
- **Cart Management**: Add items, verify delivery addresses
- **Order Tracking**: Monitor order status and delivery
- **Product Search**: Search across platforms (integration in progress)

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy (async)
- **Database**: SQLite with aiosqlite
- **Frontend**: Jinja2 templates + vanilla JS
- **Browser Automation**: Integrates with UI-Agent for headless browser control

## Setup

```bash
# Install dependencies
uv sync

# Run the server
uv run python main.py
```

Visit `http://localhost:8080` to access the web interface.

## Project Structure

```
shopping-agent/
├── app/
│   ├── api/            # FastAPI routes
│   ├── connectors/     # Platform connectors (Amazon, Swiggy, etc.)
│   ├── config.py       # Settings
│   ├── database.py     # SQLAlchemy setup
│   └── models.py       # Database models
├── templates/          # Jinja2 HTML templates
├── static/             # CSS and JS
└── main.py             # Application entry point
```

## API Endpoints

- `GET /api/connectors/` - List configured connectors
- `POST /api/connectors/` - Add/update connector
- `POST /api/products/search` - Search products
- `POST /api/carts/add` - Add item to cart
- `GET /api/carts/{platform}` - Get cart contents
- `POST /api/carts/{platform}/verify-address` - Verify delivery address
- `GET /api/orders/` - Get all orders

## Integration with UI-Agent

The Shopping Agent uses the UI-Agent for browser automation since most platforms don't provide buyer-side APIs. The UI-Agent handles:

- Browser navigation and interaction
- Cart manipulation via headless browser
- Address verification on checkout pages

## Status

- [x] Backend API structure
- [x] Web UI templates
- [x] Database models
- [ ] UI-Agent integration for Amazon
- [ ] Swiggy connector implementation
- [ ] Blinkit connector implementation
- [ ] Uber Eats connector implementation
