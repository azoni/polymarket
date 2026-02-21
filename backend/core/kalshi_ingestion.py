"""
Kalshi Market Ingestion
=======================
Fetches markets from Kalshi's public API and converts them to our Market model
for edge detection and trading. Reuses scoring from ingestion.py.
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

from .models import Market, Token, MarketCategory
from .ingestion import detect_category, calculate_edge_score, parse_datetime

logger = logging.getLogger(__name__)

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 15


def _fetch_kalshi(endpoint: str, params: dict = None) -> Optional[dict]:
    """Fetch JSON from Kalshi API."""
    url = f"{KALSHI_BASE}{endpoint}"
    headers = {"User-Agent": "PolymarketEdgeFinder/2.0"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Kalshi API returned {resp.status_code} for {endpoint}")
    except Exception as e:
        logger.error(f"Kalshi API error: {e}")
    return None


def _parse_kalshi_market(market: dict, event_title: str = "") -> Market:
    """Convert a Kalshi market dict to our Market model."""
    ticker = market.get("ticker", "")
    title = market.get("title", "") or market.get("subtitle", "") or event_title

    # Parse prices (Kalshi uses cents or _dollars fields)
    def _to_float(val, fallback=0):
        try:
            return float(val) if val else fallback
        except (ValueError, TypeError):
            return fallback

    yes_bid = _to_float(market.get("yes_bid_dollars"))
    yes_ask = _to_float(market.get("yes_ask_dollars"))
    last_price = _to_float(market.get("last_price_dollars"))

    # Fallback to cents fields
    if not yes_bid and not yes_ask:
        yes_bid = _to_float(market.get("yes_bid")) / 100
        yes_ask = _to_float(market.get("yes_ask")) / 100
    if not last_price:
        last_price = _to_float(market.get("last_price")) / 100

    yes_price = round((yes_bid + yes_ask) / 2, 4) if yes_bid and yes_ask else last_price
    no_price = round(1 - yes_price, 4) if yes_price else 0.5

    # Spread
    spread_pct = 0.0
    if yes_bid and yes_ask:
        mid = (yes_bid + yes_ask) / 2
        if mid > 0:
            spread_pct = ((yes_ask - yes_bid) / mid) * 100

    # Parse end date
    close_time = market.get("close_time", "") or market.get("expiration_time", "")
    end_date = parse_datetime(close_time)
    days_until = None
    if end_date:
        delta = end_date - datetime.now(timezone.utc)
        days_until = max(0, delta.days)

    # Category
    category = detect_category(title, event_title)

    # Volume / liquidity
    volume_24h = float(market.get("volume_24h", 0) or 0)
    volume = float(market.get("volume", 0) or 0)
    open_interest = float(market.get("open_interest", 0) or 0)

    # Tokens: Yes and No mapped to Kalshi ticker
    tokens = [
        Token(token_id=ticker, outcome="Yes", price=yes_price,
              best_bid=round(yes_bid, 4), best_ask=round(yes_ask, 4)),
        Token(token_id=ticker, outcome="No", price=no_price),
    ]

    market_obj = Market(
        market_id=f"kalshi:{ticker}",
        condition_id=ticker,
        question=title,
        description=event_title[:500] if event_title != title else "",
        category=category,
        current_price=yes_price or 0.5,
        spread_pct=spread_pct,
        volume_24h=volume_24h if volume_24h else volume,
        liquidity=open_interest,
        end_date=str(end_date) if end_date else None,
        days_until_resolution=days_until,
        tokens=tokens,
        polymarket_url=f"https://kalshi.com/markets/{ticker}" if ticker else "",
    )

    market_obj.edge_score = calculate_edge_score(market_obj)
    return market_obj


def ingest_kalshi_markets(
    max_markets: int = 100,
    min_volume: float = 0,
) -> List[Market]:
    """
    Fetch and process markets from Kalshi's public API.

    Returns:
        List of Market objects sorted by edge score
    """
    logger.info(f"Fetching Kalshi markets (max={max_markets})")

    # Fetch events with nested markets
    data = _fetch_kalshi("/events", params={
        "status": "open",
        "with_nested_markets": "true",
        "limit": 200,
    })

    if not data or "events" not in data:
        logger.warning("No events returned from Kalshi API")
        return []

    # Extract all markets from events
    markets = []
    for event in data["events"]:
        event_title = event.get("title", "")
        for mkt in event.get("markets", []):
            status = mkt.get("status", "")
            if status not in ("open", "active"):
                continue

            try:
                market = _parse_kalshi_market(mkt, event_title)

                # Volume filter
                if market.volume_24h < min_volume and market.liquidity < min_volume:
                    continue

                markets.append(market)
            except Exception as e:
                logger.debug(f"Error parsing Kalshi market: {e}")

            if len(markets) >= max_markets:
                break
        if len(markets) >= max_markets:
            break

    # Sort by edge score
    markets.sort(key=lambda m: m.edge_score, reverse=True)
    logger.info(f"Ingested {len(markets)} Kalshi markets")
    return markets
