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
from core.kalshi_ingestion import ingest_kalshi_markets
from core.database import Database

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# IN-MEMORY STORE + DB BACKING
# =============================================================================

class DataStore:
    """Data store backed by SQLite with in-memory cache."""

    def __init__(self):
        self.markets: List[Market] = []
        self.opportunities: List[EdgeOpportunity] = []
        self.predictions: List[Prediction] = []
        self.last_updated: Optional[datetime] = None
        self.is_loading: bool = False
        self.db: Optional[Database] = None

store = DataStore()
orchestrator = AgentOrchestrator()


def set_db(db: Database):
    """Set the database instance (called from main.py)."""
    store.db = db
    orchestrator.db = db
    # Load existing data from DB on startup
    try:
        store.markets = db.get_markets(limit=200)
        store.opportunities = db.get_opportunities(limit=200)
        store.predictions = db.get_predictions(limit=200)
        if store.markets:
            store.last_updated = datetime.now()
            logger.info(f"Loaded {len(store.markets)} markets from database")
    except Exception as e:
        logger.warning(f"Could not load data from DB: {e}")


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(exchange: Optional[str] = None):
    """Get summary statistics for the dashboard."""
    if store.db:
        stats = store.db.get_stats(exchange=exchange)
        return DashboardStats(
            total_markets=stats["total_markets"],
            total_opportunities=stats["total_opportunities"],
            high_confidence_opps=stats["high_confidence_opps"],
            total_predictions=stats["total_predictions"],
            markets_by_category=stats["markets_by_category"],
            last_updated=store.last_updated
        )

    # Fallback to in-memory
    category_counts = {}
    for market in store.markets:
        cat = market.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1

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
    offset: int = Query(0, ge=0),
    exchange: Optional[str] = None,
):
    """Get markets with optional filtering, sorting, and search."""
    if store.db:
        cat_val = category.value if category else None
        return store.db.get_markets(
            category=cat_val, min_score=min_score, min_volume=min_volume,
            sort_by=sort_by, search=search, limit=limit, offset=offset,
            exchange=exchange,
        )

    # Fallback to in-memory
    markets = store.markets
    if category:
        markets = [m for m in markets if m.category == category]
    if min_score > 0:
        markets = [m for m in markets if m.edge_score >= min_score]
    if min_volume > 0:
        markets = [m for m in markets if m.volume_24h >= min_volume]
    if search:
        q = search.lower()
        markets = [m for m in markets if q in m.question.lower()]
    if sort_by in SORT_FIELDS:
        reverse = sort_by != "spread_pct"
        markets = sorted(markets, key=lambda m: getattr(m, sort_by, 0), reverse=reverse)
    return markets[offset:offset + limit]


@router.get("/markets/{market_id}", response_model=Market)
async def get_market(market_id: str):
    """Get a specific market by ID."""
    if store.db:
        m = store.db.get_market(market_id)
        if m:
            return m
        raise HTTPException(status_code=404, detail="Market not found")

    for market in store.markets:
        if market.market_id == market_id:
            return market
    raise HTTPException(status_code=404, detail="Market not found")


@router.get("/markets/{market_id}/edges")
async def get_market_edges(market_id: str):
    """Get opportunities and predictions for a specific market."""
    if store.db:
        opps = store.db.get_market_opportunities(market_id)
        preds = store.db.get_market_predictions(market_id)
        return {"opportunities": opps, "predictions": preds}

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
    limit: int = Query(50, ge=1, le=200),
    exchange: Optional[str] = None,
):
    """Get detected edge opportunities."""
    if store.db:
        return store.db.get_opportunities(
            edge_type=edge_type, min_confidence=min_confidence,
            risk_level=risk_level, limit=limit, exchange=exchange,
        )

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
    limit: int = Query(50, ge=1, le=200),
    exchange: Optional[str] = None,
):
    """Get research agent predictions."""
    if store.db:
        return store.db.get_predictions(
            direction=direction, min_edge=min_edge, limit=limit,
            exchange=exchange,
        )

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
    """Background task to refresh all data from both exchanges."""
    store.is_loading = True

    try:
        # 1. Ingest Polymarket markets
        logger.info("Ingesting Polymarket markets...")
        poly_markets = ingest_markets(
            max_markets=max_markets,
            min_volume=min_volume,
            fetch_orderbooks=fetch_orderbooks
        )

        # 2. Ingest Kalshi markets
        logger.info("Ingesting Kalshi markets...")
        try:
            kalshi_markets = ingest_kalshi_markets(
                max_markets=max_markets,
                min_volume=min_volume
            )
            logger.info(f"Ingested {len(kalshi_markets)} Kalshi markets")
        except Exception as e:
            logger.warning(f"Kalshi ingestion failed (non-fatal): {e}")
            kalshi_markets = []

        # Combine all markets
        store.markets = poly_markets + kalshi_markets

        # 3. Run research agents (on Polymarket markets — Kalshi markets get edge detection only)
        logger.info("Running research agents...")
        poly_predictions = orchestrator.research_markets(
            poly_markets[:50],
            min_edge=0.0
        )
        store.predictions = poly_predictions

        # 4. Detect edges for Polymarket
        logger.info("Detecting edges for Polymarket...")
        poly_opps = detect_all_edges(
            poly_markets,
            predictions=poly_predictions,
            data_sources=True
        )

        # 5. Detect edges for Kalshi
        logger.info("Detecting edges for Kalshi...")
        kalshi_opps = detect_all_edges(
            kalshi_markets,
            predictions=[],
            data_sources=True
        ) if kalshi_markets else []

        store.opportunities = poly_opps + kalshi_opps

        store.last_updated = datetime.now()
        logger.info(f"Refresh complete: {len(poly_markets)} Polymarket + {len(kalshi_markets)} Kalshi markets, {len(store.opportunities)} opportunities")

        # 6. Persist to database (scoped by exchange to avoid cross-wipe)
        if store.db:
            store.db.upsert_markets(store.markets)
            store.db.save_opportunities(poly_opps, exchange="polymarket")
            store.db.save_opportunities(kalshi_opps, exchange="kalshi")
            store.db.save_predictions(poly_predictions, exchange="polymarket")
            logger.info("Data persisted to database")

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
    """Trigger a data refresh (runs in background)."""
    if store.is_loading:
        raise HTTPException(status_code=409, detail="Refresh already in progress")

    background_tasks.add_task(
        _refresh_data_task,
        max_markets,
        min_volume,
        fetch_orderbooks
    )

    return {"message": "Refresh started", "max_markets": max_markets}
