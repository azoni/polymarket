"""
Polymarket Edge Finder - API Server
===================================
FastAPI backend for the edge finding dashboard.

Run with:
    uvicorn main:app --reload --port 8000
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from core.database import Database
from api import router
from api.routes import set_db as set_routes_db
from api.trading_routes import trading_router, set_bot
from api.research_routes import research_router, set_research_deps
from trading.bot import TradingBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

_logger = logging.getLogger(__name__)

# Initialize database
db = Database()
db.initialize()

# Create FastAPI app
app = FastAPI(
    title="Polymarket Edge Finder",
    description="Find trading edges in prediction markets",
    version="2.0.0"
)

# CORS - allow frontend to connect
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

if os.environ.get("FRONTEND_URL"):
    ALLOWED_ORIGINS.append(os.environ.get("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api")
app.include_router(trading_router, prefix="/api")
app.include_router(research_router, prefix="/api")

# Wire up database to routes and research
set_routes_db(db)
from api.routes import orchestrator as _orchestrator
set_research_deps(db, _orchestrator)

# ===== Create trading bot instances =====

# Polymarket bot
poly_bot = TradingBot(db=db, exchange="polymarket")
set_bot("polymarket", poly_bot)

if poly_bot.config.has_credentials:
    connected = poly_bot.trader.connect()
    if connected:
        _logger.info("Connected to Polymarket CLOB API")
    else:
        _logger.warning("Failed to connect to Polymarket CLOB — wallet features disabled")

# Kalshi bot
kalshi_bot = TradingBot(db=db, exchange="kalshi")
set_bot("kalshi", kalshi_bot)

if kalshi_bot.config.has_credentials:
    connected = kalshi_bot.trader.connect()
    if connected:
        _logger.info("Connected to Kalshi API")
    else:
        _logger.warning("Failed to connect to Kalshi — running in paper mode")
else:
    _logger.info("Kalshi: no credentials — paper trading mode")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Polymarket Edge Finder API",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}
