"""
Market Ingestion
================
Fetches and scores markets from Polymarket APIs.
Simplified version focused on clarity.
"""

import requests
import time
import re
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging

from .models import Market, Token, MarketCategory

logger = logging.getLogger(__name__)


# =============================================================================
# API CLIENT
# =============================================================================

class PolymarketClient:
    """
    Simple client for Polymarket APIs.
    Handles rate limiting and browser-like headers.
    """
    
    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self.last_request = 0
    
    def _request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make a rate-limited request."""
        # Rate limit: 2 requests/second
        elapsed = time.time() - self.last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self.last_request = time.time()
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Request failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Request error: {e}")
        return None
    
    def get_markets(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Fetch active markets sorted by volume."""
        url = f"{self.GAMMA_BASE}/markets"
        params = {
            "closed": "false",
            "limit": limit,
            "offset": offset,
            "order": "volume24hr",
            "ascending": "false"
        }
        return self._request(url, params) or []
    
    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """Fetch order book for a token."""
        url = f"{self.CLOB_BASE}/book"
        return self._request(url, {"token_id": token_id})


# =============================================================================
# CATEGORY DETECTION
# =============================================================================

CATEGORY_KEYWORDS = {
    MarketCategory.POLITICS: [
        "election", "president", "congress", "senate", "trump", "biden",
        "republican", "democrat", "governor", "vote", "poll"
    ],
    MarketCategory.SPORTS: [
        "nfl", "nba", "mlb", "nhl", "super bowl", "championship", "playoffs",
        "finals", "game", "match", "win", "score"
    ],
    MarketCategory.CRYPTO: [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "token"
    ],
    MarketCategory.ECONOMICS: [
        "fed", "interest rate", "inflation", "gdp", "unemployment", "recession"
    ],
    MarketCategory.ENTERTAINMENT: [
        "movie", "oscar", "grammy", "emmy", "album", "netflix", "box office"
    ],
    MarketCategory.SCIENCE: [
        "space", "nasa", "spacex", "climate", "vaccine", "fda"
    ],
}


def detect_category(question: str, description: str = "") -> MarketCategory:
    """Detect market category from text."""
    text = f"{question} {description}".lower()
    
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return MarketCategory.OTHER


# =============================================================================
# MARKET SCORING
# =============================================================================

def score_liquidity(liquidity: float) -> float:
    """Score liquidity (0-100). Higher = better for trading."""
    MIN_LIQ = 1000
    IDEAL_LIQ = 50000
    
    if liquidity < MIN_LIQ:
        return 0
    if liquidity >= IDEAL_LIQ:
        return 100
    return ((liquidity - MIN_LIQ) / (IDEAL_LIQ - MIN_LIQ)) * 100


def score_inefficiency(spread_pct: float) -> float:
    """Score market inefficiency (0-100). Higher = more edge potential."""
    if spread_pct > 10:
        return 20  # Too illiquid
    if spread_pct < 0.5:
        return 30  # Very efficient
    if 1 <= spread_pct <= 5:
        return 100  # Sweet spot
    if spread_pct < 1:
        return 30 + (spread_pct * 70)
    return 100 - ((spread_pct - 5) * 16)


def score_researchability(category: MarketCategory) -> float:
    """Score how researchable a market is (0-100)."""
    scores = {
        MarketCategory.SPORTS: 95,
        MarketCategory.POLITICS: 90,
        MarketCategory.ECONOMICS: 90,
        MarketCategory.CRYPTO: 85,
        MarketCategory.LEGAL: 75,
        MarketCategory.SCIENCE: 70,
        MarketCategory.ENTERTAINMENT: 60,
        MarketCategory.OTHER: 40,
    }
    return scores.get(category, 40)


def score_timing(days: Optional[int]) -> float:
    """Score time horizon (0-100). Best = 3-14 days out."""
    if days is None:
        return 50
    if days < 1:
        return 20
    if days < 3:
        return 50
    if days <= 14:
        return 90
    if days <= 30:
        return 85
    if days <= 90:
        return 70
    return 40


def calculate_edge_score(market: Market) -> float:
    """Calculate overall edge score (0-100) using weighted factors."""
    weights = {
        "liquidity": 0.25,
        "inefficiency": 0.30,
        "researchability": 0.25,
        "timing": 0.20
    }
    
    liq_score = score_liquidity(market.liquidity)
    eff_score = score_inefficiency(market.spread_pct)
    res_score = score_researchability(market.category)
    time_score = score_timing(market.days_until_resolution)
    
    # Store individual scores
    market.liquidity_score = liq_score
    market.efficiency_score = eff_score
    market.researchability_score = res_score
    
    # Weighted average
    return (
        liq_score * weights["liquidity"] +
        eff_score * weights["inefficiency"] +
        res_score * weights["researchability"] +
        time_score * weights["timing"]
    )


# =============================================================================
# MARKET PROCESSING
# =============================================================================

def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse datetime string."""
    if not dt_str:
        return None
    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def process_market(raw: Dict, client: PolymarketClient = None) -> Market:
    """Convert raw API data to Market model."""
    
    # Parse dates
    end_date = parse_datetime(raw.get("endDate"))
    days_until = None
    if end_date:
        delta = end_date - datetime.now(timezone.utc)
        days_until = max(0, delta.days)
    
    # Detect category
    question = raw.get("question", "")
    description = raw.get("description", "")
    category = detect_category(question, description)
    
    # Parse tokens
    outcomes = raw.get("outcomes", ["Yes", "No"])
    prices = raw.get("outcomePrices", [])
    token_ids = raw.get("clobTokenIds", [])
    
    tokens = []
    for i, outcome in enumerate(outcomes):
        tokens.append(Token(
            token_id=token_ids[i] if i < len(token_ids) else "",
            outcome=outcome,
            price=float(prices[i]) if i < len(prices) else 0.5
        ))
    
    # Calculate spread if we have order book data
    spread_pct = 0.0
    if client and tokens and tokens[0].token_id:
        orderbook = client.get_orderbook(tokens[0].token_id)
        if orderbook:
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            if bids and asks:
                best_bid = float(bids[0].get("price", 0))
                best_ask = float(asks[0].get("price", 0))
                midpoint = (best_bid + best_ask) / 2
                if midpoint > 0:
                    spread_pct = ((best_ask - best_bid) / midpoint) * 100
                tokens[0].best_bid = best_bid
                tokens[0].best_ask = best_ask
    
    # Build URL
    slug = raw.get("slug", "")
    url = f"https://polymarket.com/event/{slug}" if slug else ""
    
    market = Market(
        market_id=raw.get("id", ""),
        condition_id=raw.get("conditionId", ""),
        question=question,
        description=description[:500],
        category=category,
        tags=raw.get("tags", []) or [],
        current_price=tokens[0].price if tokens else 0.5,
        spread_pct=spread_pct,
        volume_24h=float(raw.get("volume24hr", 0) or 0),
        liquidity=float(raw.get("liquidity", 0) or 0),
        end_date=str(end_date) if end_date else None,
        days_until_resolution=days_until,
        tokens=tokens,
        polymarket_url=url
    )
    
    # Calculate edge score
    market.edge_score = calculate_edge_score(market)
    
    return market


# =============================================================================
# MAIN INGESTION FUNCTION
# =============================================================================

def ingest_markets(
    max_markets: int = 100,
    min_volume: float = 500,
    fetch_orderbooks: bool = True
) -> List[Market]:
    """
    Fetch and process markets from Polymarket.
    
    Args:
        max_markets: Maximum number of markets to fetch
        min_volume: Minimum 24h volume filter
        fetch_orderbooks: Whether to fetch order book data (slower but more accurate)
    
    Returns:
        List of Market objects sorted by edge score
    """
    client = PolymarketClient()
    
    logger.info(f"Fetching markets (max={max_markets}, min_vol=${min_volume})")
    
    # Fetch raw markets
    all_raw = []
    offset = 0
    while len(all_raw) < max_markets:
        batch = client.get_markets(limit=100, offset=offset)
        if not batch:
            break
        all_raw.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    
    logger.info(f"Fetched {len(all_raw)} raw markets")
    
    # Filter by volume
    filtered = [m for m in all_raw if float(m.get("volume24hr", 0) or 0) >= min_volume]
    logger.info(f"After volume filter: {len(filtered)} markets")
    
    # Process markets
    markets = []
    for i, raw in enumerate(filtered[:max_markets]):
        if i % 20 == 0:
            logger.info(f"Processing {i}/{len(filtered[:max_markets])}...")
        
        try:
            market = process_market(raw, client if fetch_orderbooks else None)
            markets.append(market)
        except Exception as e:
            logger.error(f"Error processing market: {e}")
    
    # Sort by edge score
    markets.sort(key=lambda m: m.edge_score, reverse=True)
    
    logger.info(f"Processed {len(markets)} markets")
    return markets
