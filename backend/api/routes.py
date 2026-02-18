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

SORT_FIELDS = {"edge_score", "volume_24h", "liquidity", "spread_pct"}

@router.get("/markets", response_model=List[Market])
async def get_markets(
    category: Optional[MarketCategory] = None,
    min_score: float = Query(0, ge=0, le=100),
    min_volume: float = Query(0, ge=0),
    sort_by: str = Query("edge_score"),
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get markets with optional filtering, sorting, and search.
    """
    markets = store.markets

    # Apply filters
    if category:
        markets = [m for m in markets if m.category == category]
    if min_score > 0:
        markets = [m for m in markets if m.edge_score >= min_score]
    if min_volume > 0:
        markets = [m for m in markets if m.volume_24h >= min_volume]
    if search:
        q = search.lower()
        markets = [m for m in markets if q in m.question.lower()]

    # Sort
    if sort_by in SORT_FIELDS:
        reverse = sort_by != "spread_pct"  # lower spread is better
        markets = sorted(markets, key=lambda m: getattr(m, sort_by, 0), reverse=reverse)

    # Paginate
    return markets[offset:offset + limit]


@router.get("/markets/{market_id}", response_model=Market)
async def get_market(market_id: str):
    """Get a specific market by ID."""
    for market in store.markets:
        if market.market_id == market_id:
            return market
    raise HTTPException(status_code=404, detail="Market not found")


@router.get("/markets/{market_id}/edges")
async def get_market_edges(market_id: str):
    """Get opportunities and predictions for a specific market."""
    opps = [o for o in store.opportunities if o.market_id == market_id]
    preds = [p for p in store.predictions if p.market_id == market_id]
    return {"opportunities": opps, "predictions": preds}


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
