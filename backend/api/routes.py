"""
API Routes
==========
FastAPI endpoints for the edge finder.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
import logging

from core import (
    Market, EdgeOpportunity, Prediction, DashboardStats,
    MarketCategory, ingest_markets, detect_all_edges, AgentOrchestrator
)

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# IN-MEMORY STORE
# =============================================================================
# Simple in-memory storage. In production, use Redis or a database.

class DataStore:
    """Simple in-memory data store."""
    
    def __init__(self):
        self.markets: List[Market] = []
        self.opportunities: List[EdgeOpportunity] = []
        self.predictions: List[Prediction] = []
        self.last_updated: Optional[datetime] = None
        self.is_loading: bool = False

store = DataStore()
orchestrator = AgentOrchestrator()


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get summary statistics for the dashboard."""
    
    # Count markets by category
    category_counts = {}
    for market in store.markets:
        cat = market.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Count high-confidence opportunities (>70%)
    high_conf = sum(1 for o in store.opportunities if o.confidence >= 70)
    
    return DashboardStats(
        total_markets=len(store.markets),
        total_opportunities=len(store.opportunities),
        high_confidence_opps=high_conf,
        total_predictions=len(store.predictions),
        markets_by_category=category_counts,
        last_updated=store.last_updated
    )


@router.get("/status")
async def get_status():
    """Get current loading status."""
    return {
        "is_loading": store.is_loading,
        "markets_loaded": len(store.markets),
        "last_updated": store.last_updated
    }


# =============================================================================
# MARKETS
# =============================================================================

@router.get("/markets", response_model=List[Market])
async def get_markets(
    category: Optional[MarketCategory] = None,
    min_score: float = Query(0, ge=0, le=100),
    min_volume: float = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get markets with optional filtering.
    
    - **category**: Filter by category
    - **min_score**: Minimum edge score (0-100)
    - **min_volume**: Minimum 24h volume
    - **limit**: Max results (default 50)
    - **offset**: Pagination offset
    """
    markets = store.markets
    
    # Apply filters
    if category:
        markets = [m for m in markets if m.category == category]
    if min_score > 0:
        markets = [m for m in markets if m.edge_score >= min_score]
    if min_volume > 0:
        markets = [m for m in markets if m.volume_24h >= min_volume]
    
    # Paginate
    return markets[offset:offset + limit]


@router.get("/markets/{market_id}", response_model=Market)
async def get_market(market_id: str):
    """Get a specific market by ID."""
    for market in store.markets:
        if market.market_id == market_id:
            return market
    raise HTTPException(status_code=404, detail="Market not found")


# =============================================================================
# OPPORTUNITIES
# =============================================================================

@router.get("/opportunities", response_model=List[EdgeOpportunity])
async def get_opportunities(
    edge_type: Optional[str] = None,
    min_confidence: float = Query(0, ge=0, le=100),
    risk_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get detected edge opportunities.
    
    - **edge_type**: Filter by type (arbitrage, mispricing, etc.)
    - **min_confidence**: Minimum confidence (0-100)
    - **risk_level**: Filter by risk (low, medium, high)
    - **limit**: Max results
    """
    opps = store.opportunities
    
    if edge_type:
        opps = [o for o in opps if o.edge_type.value == edge_type]
    if min_confidence > 0:
        opps = [o for o in opps if o.confidence >= min_confidence]
    if risk_level:
        opps = [o for o in opps if o.risk_level == risk_level]
    
    return opps[:limit]


# =============================================================================
# PREDICTIONS
# =============================================================================

@router.get("/predictions", response_model=List[Prediction])
async def get_predictions(
    direction: Optional[str] = None,
    min_edge: float = Query(0, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get research agent predictions.
    
    - **direction**: Filter by direction (buy_yes, buy_no, hold)
    - **min_edge**: Minimum absolute edge
    - **limit**: Max results
    """
    preds = store.predictions
    
    if direction:
        preds = [p for p in preds if p.direction == direction]
    if min_edge > 0:
        preds = [p for p in preds if abs(p.edge) >= min_edge]
    
    return preds[:limit]


# =============================================================================
# DATA REFRESH
# =============================================================================

def _refresh_data_task(max_markets: int, min_volume: float, fetch_orderbooks: bool):
    """Background task to refresh all data."""
    store.is_loading = True
    
    try:
        # 1. Ingest markets
        logger.info("Ingesting markets...")
        store.markets = ingest_markets(
            max_markets=max_markets,
            min_volume=min_volume,
            fetch_orderbooks=fetch_orderbooks
        )
        
        # 2. Detect edges
        logger.info("Detecting edges...")
        store.opportunities = detect_all_edges(store.markets)
        
        # 3. Run research agents
        logger.info("Running research agents...")
        store.predictions = orchestrator.research_markets(
            store.markets[:50],  # Top 50 by edge score
            min_edge=0.0
        )
        
        store.last_updated = datetime.now()
        logger.info(f"Refresh complete: {len(store.markets)} markets, {len(store.opportunities)} opportunities")
        
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
    finally:
        store.is_loading = False


@router.post("/refresh")
async def refresh_data(
    background_tasks: BackgroundTasks,
    max_markets: int = Query(100, ge=10, le=500),
    min_volume: float = Query(500, ge=0),
    fetch_orderbooks: bool = Query(True)
):
    """
    Trigger a data refresh (runs in background).
    
    - **max_markets**: Maximum markets to fetch
    - **min_volume**: Minimum 24h volume filter
    - **fetch_orderbooks**: Fetch order book data (slower but more accurate)
    """
    if store.is_loading:
        raise HTTPException(status_code=409, detail="Refresh already in progress")
    
    background_tasks.add_task(
        _refresh_data_task,
        max_markets,
        min_volume,
        fetch_orderbooks
    )
    
    return {"message": "Refresh started", "max_markets": max_markets}


# =============================================================================
# DEMO DATA (for testing without API access)
# =============================================================================

@router.post("/load-demo")
async def load_demo_data():
    """Load demo data for testing the UI without hitting Polymarket APIs."""
    
    from core.models import Token
    
    store.markets = [
        Market(
            market_id="demo-1",
            question="Will Bitcoin reach $100,000 by March 2025?",
            description="Resolves YES if BTC reaches $100k on any major exchange",
            category=MarketCategory.CRYPTO,
            current_price=0.42,
            spread_pct=2.5,
            volume_24h=125000,
            liquidity=450000,
            days_until_resolution=45,
            edge_score=78,
            liquidity_score=85,
            efficiency_score=75,
            researchability_score=80,
            tokens=[
                Token(token_id="t1", outcome="Yes", price=0.42, best_bid=0.41, best_ask=0.43),
                Token(token_id="t2", outcome="No", price=0.55, best_bid=0.54, best_ask=0.56)
            ],
            polymarket_url="https://polymarket.com/event/btc-100k"
        ),
        Market(
            market_id="demo-2",
            question="Will the Fed cut rates in January 2025?",
            description="Resolves based on FOMC decision",
            category=MarketCategory.ECONOMICS,
            current_price=0.15,
            spread_pct=1.8,
            volume_24h=89000,
            liquidity=320000,
            days_until_resolution=10,
            edge_score=82,
            liquidity_score=80,
            efficiency_score=90,
            researchability_score=90,
            tokens=[
                Token(token_id="t3", outcome="Yes", price=0.15, best_bid=0.14, best_ask=0.16),
                Token(token_id="t4", outcome="No", price=0.84, best_bid=0.83, best_ask=0.85)
            ],
            polymarket_url="https://polymarket.com/event/fed-jan"
        ),
        Market(
            market_id="demo-3",
            question="Who will win Super Bowl LIX?",
            description="NFL Championship Game",
            category=MarketCategory.SPORTS,
            current_price=0.22,
            spread_pct=4.2,
            volume_24h=520000,
            liquidity=1200000,
            days_until_resolution=30,
            edge_score=71,
            liquidity_score=100,
            efficiency_score=65,
            researchability_score=95,
            tokens=[
                Token(token_id="t5", outcome="Chiefs", price=0.22),
                Token(token_id="t6", outcome="Lions", price=0.18),
                Token(token_id="t7", outcome="Eagles", price=0.15),
                Token(token_id="t8", outcome="Bills", price=0.12),
                Token(token_id="t9", outcome="Other", price=0.28)
            ],
            polymarket_url="https://polymarket.com/event/super-bowl"
        ),
        Market(
            market_id="demo-4",
            question="Will Trump be inaugurated on January 20, 2025?",
            description="Resolves YES if inauguration occurs as scheduled",
            category=MarketCategory.POLITICS,
            current_price=0.95,
            spread_pct=0.8,
            volume_24h=45000,
            liquidity=890000,
            days_until_resolution=4,
            edge_score=55,
            liquidity_score=90,
            efficiency_score=30,
            researchability_score=90,
            tokens=[
                Token(token_id="t10", outcome="Yes", price=0.95),
                Token(token_id="t11", outcome="No", price=0.04)
            ],
            polymarket_url="https://polymarket.com/event/inauguration"
        ),
        Market(
            market_id="demo-5",
            question="Will Ethereum reach $5,000 by June 2025?",
            description="Resolves YES if ETH reaches $5k",
            category=MarketCategory.CRYPTO,
            current_price=0.28,
            spread_pct=3.1,
            volume_24h=67000,
            liquidity=280000,
            days_until_resolution=150,
            edge_score=62,
            liquidity_score=70,
            efficiency_score=70,
            researchability_score=85,
            tokens=[
                Token(token_id="t12", outcome="Yes", price=0.28),
                Token(token_id="t13", outcome="No", price=0.70)
            ],
            polymarket_url="https://polymarket.com/event/eth-5k"
        ),
    ]
    
    # Generate opportunities
    store.opportunities = [
        EdgeOpportunity(
            id="opp-1",
            edge_type="arbitrage",
            description="Binary underpricing: YES + NO = 97%",
            confidence=90,
            expected_return=3.1,
            risk_level="low",
            market_id="demo-1",
            market_question="Will Bitcoin reach $100,000 by March 2025?",
            suggested_action="Buy both YES at 42% and NO at 55%",
            reasoning="Combined price 97% < 100% means guaranteed profit"
        ),
        EdgeOpportunity(
            id="opp-2",
            edge_type="volume_signal",
            description="Volume spike: 5.2x liquidity",
            confidence=60,
            expected_return=0,
            risk_level="high",
            market_id="demo-3",
            market_question="Who will win Super Bowl LIX?",
            suggested_action="Research why volume is elevated",
            reasoning="Unusual activity may indicate informed trading"
        ),
        EdgeOpportunity(
            id="opp-3",
            edge_type="liquidity_gap",
            description="Wide spread: 4.2%",
            confidence=65,
            expected_return=2.1,
            risk_level="medium",
            market_id="demo-3",
            market_question="Who will win Super Bowl LIX?",
            suggested_action="Provide liquidity at tighter spread",
            reasoning="High volume with wide spread = market making opportunity"
        ),
    ]
    
    # Generate predictions
    store.predictions = [
        Prediction(
            market_id="demo-1",
            market_question="Will Bitcoin reach $100,000 by March 2025?",
            predicted_probability=0.48,
            current_price=0.42,
            edge=0.06,
            confidence=55,
            confidence_low=0.35,
            confidence_high=0.60,
            direction="buy_yes",
            strength="moderate",
            reasoning="Technical indicators and halving cycle suggest upside potential",
            key_risks=["Regulatory news", "Macro downturn", "Exchange issues"],
            catalysts=["ETF inflows", "Halving effects", "Institutional adoption"],
            agent_name="CryptoAgent"
        ),
        Prediction(
            market_id="demo-2",
            market_question="Will the Fed cut rates in January 2025?",
            predicted_probability=0.12,
            current_price=0.15,
            edge=-0.03,
            confidence=70,
            confidence_low=0.08,
            confidence_high=0.18,
            direction="buy_no",
            strength="weak",
            reasoning="Fed communications suggest holding rates steady",
            key_risks=["Surprise inflation data", "Market turmoil"],
            catalysts=["CPI release", "FOMC statement"],
            agent_name="EconomicsAgent"
        ),
    ]
    
    store.last_updated = datetime.now()
    
    return {
        "message": "Demo data loaded",
        "markets": len(store.markets),
        "opportunities": len(store.opportunities),
        "predictions": len(store.predictions)
    }
