"""Shopping Agent - Multi-platform shopping assistant."""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.api import connectors, products, carts, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Multi-platform shopping assistant for Amazon, Swiggy, Blinkit, and more",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = Path(__file__).parent / "templates"
templates_path.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=templates_path)

# Include API routers
app.include_router(connectors.router)
app.include_router(products.router)
app.include_router(carts.router)
app.include_router(orders.router)


@app.get("/")
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "Shopping Agent"},
    )


@app.get("/connectors")
async def connectors_page(request: Request):
    """Connector setup page."""
    return templates.TemplateResponse(
        "connectors.html",
        {"request": request, "title": "Platform Connectors"},
    )


@app.get("/carts")
async def carts_page(request: Request):
    """Cart management page."""
    return templates.TemplateResponse(
        "carts.html",
        {"request": request, "title": "Shopping Carts"},
    )


@app.get("/orders")
async def orders_page(request: Request):
    """Order tracking page."""
    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "title": "Order Tracking"},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


def main():
    """Run the application."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
