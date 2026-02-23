"""
External Data Sources
=====================
Centralized API clients for research agents.
All APIs work without keys (keyless), with optional API keys for richer data.

Keyless: CoinGecko, ESPN, Wikipedia, Fear & Greed Index, Treasury.gov
Optional keys: NewsAPI (NEWS_API_KEY), The Odds API (ODDS_API_KEY), FRED (FRED_API_KEY)
"""

import os
import re
import time
import logging
import requests
from typing import Optional, Any, List, Dict

logger = logging.getLogger(__name__)

TIMEOUT = 10  # seconds


# =============================================================================
# CACHE
# =============================================================================

class APICache:
    """Simple TTL-based in-memory cache."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: Dict[str, tuple] = {}  # key -> (value, expires_at)

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        self._store[key] = (value, time.time() + (ttl or self.default_ttl))

    def clear(self):
        self._store.clear()


_cache = APICache(default_ttl=300)


def _fetch(url: str, params: dict = None, headers: dict = None,
           cache_key: str = None, cache_ttl: int = 300) -> Optional[Any]:
    """Fetch JSON from URL with caching and error handling."""
    if cache_key:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    default_headers = {"User-Agent": "PolymarketEdgeFinder/2.0 (research bot)"}
    if headers:
        default_headers.update(headers)
    try:
        resp = requests.get(url, params=params, headers=default_headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if cache_key:
            _cache.set(cache_key, data, cache_ttl)
        return data
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching {url}: {e}")
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
    return None


# =============================================================================
# POLITICS DATA SOURCE
# =============================================================================

class PoliticsDataSource:
    """Fetch news and context for political markets."""

    def __init__(self):
        key = os.environ.get("NEWS_API_KEY", "").strip()
        self.news_api_key = key if key and not key.startswith("#") else ""

    def get_news_sentiment(self, query: str) -> Optional[dict]:
        """
        Get news headlines and basic sentiment for a query.
        Uses NewsAPI if key available. Returns None if no API key
        (agents should handle missing data honestly, not fake it with Wikipedia).
        """
        if self.news_api_key:
            return self._newsapi_sentiment(query)
        return None

    def _newsapi_sentiment(self, query: str) -> Optional[dict]:
        """Fetch headlines from NewsAPI and score sentiment."""
        # Extract key terms (first 3 meaningful words)
        terms = self._extract_search_terms(query)
        data = _fetch(
            "https://newsapi.org/v2/everything",
            params={
                "q": terms,
                "sortBy": "publishedAt",
                "pageSize": 10,
                "language": "en",
                "apiKey": self.news_api_key,
            },
            cache_key=f"newsapi:{terms}",
            cache_ttl=600,
        )
        if not data or data.get("status") != "ok":
            return self._wikipedia_context(query)

        articles = data.get("articles", [])
        if not articles:
            return {"source": "NewsAPI", "articles": 0, "sentiment": 0.0, "headlines": [], "relevance": 0.0}

        # Keyword sentiment with relevance weighting
        positive = ["win", "lead", "ahead", "surge", "gain", "rise", "strong",
                    "success", "victory", "approve", "support", "favor", "likely"]
        negative = ["lose", "trail", "behind", "drop", "fall", "weak", "fail",
                    "defeat", "decline", "reject", "unlikely", "oppose", "crisis"]

        # Extract key terms from the original query for relevance scoring
        query_terms = set(self._extract_search_terms(query).lower().split())

        sentiment_score = 0.0
        relevance_total = 0.0
        headlines = []
        for a in articles[:10]:
            title = (a.get("title") or "").lower()
            headlines.append(a.get("title", ""))

            # Check how relevant this article is to the actual question
            title_words = set(title.split())
            relevance = len(query_terms & title_words) / max(len(query_terms), 1)
            relevance_total += relevance

            # Weight sentiment by relevance (irrelevant articles count less)
            weight = 0.3 + (relevance * 0.7)  # min weight 0.3, max 1.0
            for word in positive:
                if word in title:
                    sentiment_score += weight
            for word in negative:
                if word in title:
                    sentiment_score -= weight

        # Normalize to -1 to +1
        if articles:
            sentiment_score = max(-1, min(1, sentiment_score / len(articles)))

        avg_relevance = relevance_total / len(articles) if articles else 0.0

        return {
            "source": "NewsAPI",
            "articles": len(articles),
            "sentiment": round(sentiment_score, 3),
            "relevance": round(avg_relevance, 3),
            "headlines": headlines[:5],
        }

    def _wikipedia_context(self, query: str) -> Optional[dict]:
        """Fetch Wikipedia summary for context."""
        terms = self._extract_search_terms(query)
        data = _fetch(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": terms,
                "srlimit": 3,
                "format": "json",
            },
            cache_key=f"wiki:{terms}",
            cache_ttl=900,
        )
        if not data:
            return None

        results = data.get("query", {}).get("search", [])
        snippets = [r.get("snippet", "") for r in results]
        # Clean HTML from snippets
        clean = [re.sub(r"<[^>]+>", "", s) for s in snippets]

        return {
            "source": "Wikipedia",
            "articles": len(results),
            "sentiment": 0.0,
            "context": clean,
        }

    def _extract_search_terms(self, query: str) -> str:
        """Extract meaningful search terms from a market question."""
        stop = {"will", "the", "be", "by", "in", "to", "a", "an", "of", "is", "at", "on", "for", "and", "or", "?"}
        words = [w.strip("?.,!") for w in query.lower().split() if w.strip("?.,!") not in stop]
        return " ".join(words[:5])


# =============================================================================
# SPORTS DATA SOURCE
# =============================================================================

class SportsDataSource:
    """Fetch sports odds and statistics."""

    SPORT_MAP = {
        "nfl": "americanfootball_nfl",
        "nba": "basketball_nba",
        "mlb": "baseball_mlb",
        "nhl": "icehockey_nhl",
        "soccer": "soccer_epl",
        "mma": "mma_mixed_martial_arts",
        "ufc": "mma_mixed_martial_arts",
    }

    ESPN_SPORT_MAP = {
        "nfl": ("football", "nfl"),
        "nba": ("basketball", "nba"),
        "mlb": ("baseball", "mlb"),
        "nhl": ("hockey", "nhl"),
        "soccer": ("soccer", "eng.1"),
    }

    def __init__(self):
        key = os.environ.get("ODDS_API_KEY", "").strip()
        self.odds_api_key = key if key and not key.startswith("#") else ""

    def get_odds(self, sport: str, team: str = None) -> Optional[dict]:
        """Get betting odds. Uses The Odds API if key, else ESPN."""
        sport_lower = sport.lower()
        if self.odds_api_key:
            odds = self._odds_api(sport_lower, team)
            if odds:
                return odds
        return self._espn_odds(sport_lower, team)

    def _odds_api(self, sport: str, team: str = None) -> Optional[dict]:
        """Fetch from The Odds API (free tier: 500 req/month)."""
        sport_key = self.SPORT_MAP.get(sport)
        if not sport_key:
            return None

        data = _fetch(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
            params={
                "apiKey": self.odds_api_key,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
            },
            cache_key=f"odds:{sport_key}",
            cache_ttl=600,
        )
        if not data:
            return None

        events = []
        for game in data[:5]:
            event = {
                "home": game.get("home_team", ""),
                "away": game.get("away_team", ""),
                "commence": game.get("commence_time", ""),
                "odds": {},
            }
            for bookmaker in game.get("bookmakers", [])[:1]:
                for market in bookmaker.get("markets", []):
                    if market.get("key") == "h2h":
                        for outcome in market.get("outcomes", []):
                            event["odds"][outcome["name"]] = outcome["price"]
            events.append(event)

            # Filter to team if specified
            if team and team.lower() not in event["home"].lower() and team.lower() not in event["away"].lower():
                continue

        return {"source": "OddsAPI", "sport": sport, "events": events[:5]}

    def _espn_odds(self, sport: str, team: str = None) -> Optional[dict]:
        """Fetch from ESPN public API (no key needed)."""
        mapping = self.ESPN_SPORT_MAP.get(sport)
        if not mapping:
            return None

        sport_path, league = mapping
        data = _fetch(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/scoreboard",
            cache_key=f"espn:{sport}:scoreboard",
            cache_ttl=300,
        )
        if not data:
            return None

        events = []
        for event in data.get("events", [])[:5]:
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            if len(competitors) >= 2:
                home = competitors[0]
                away = competitors[1]
                events.append({
                    "home": home.get("team", {}).get("displayName", ""),
                    "away": away.get("team", {}).get("displayName", ""),
                    "home_record": home.get("records", [{}])[0].get("summary", "") if home.get("records") else "",
                    "away_record": away.get("records", [{}])[0].get("summary", "") if away.get("records") else "",
                    "status": event.get("status", {}).get("type", {}).get("description", ""),
                })

        return {"source": "ESPN", "sport": sport, "events": events}

    def get_team_stats(self, sport: str, team: str) -> Optional[dict]:
        """Get team statistics from ESPN."""
        mapping = self.ESPN_SPORT_MAP.get(sport.lower())
        if not mapping:
            return None

        sport_path, league = mapping
        data = _fetch(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/teams",
            cache_key=f"espn:{sport}:teams",
            cache_ttl=900,
        )
        if not data:
            return None

        for t in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team_data = t.get("team", {})
            if team.lower() in team_data.get("displayName", "").lower():
                return {
                    "source": "ESPN",
                    "name": team_data.get("displayName", ""),
                    "abbreviation": team_data.get("abbreviation", ""),
                    "record": team_data.get("record", {}).get("items", [{}])[0].get("summary", "")
                    if team_data.get("record", {}).get("items") else "",
                    "standing": team_data.get("standingSummary", ""),
                }
        return None

    def parse_sport_from_question(self, question: str) -> tuple:
        """Extract sport and team names from a market question."""
        q = question.lower()
        sport = None
        for key in self.SPORT_MAP:
            if key in q:
                sport = key
                break

        # Also check for common league/sport terms
        if not sport:
            sport_hints = {
                "super bowl": "nfl", "touchdown": "nfl", "quarterback": "nfl",
                "world series": "mlb", "home run": "mlb",
                "stanley cup": "nhl",
                "premier league": "soccer", "champions league": "soccer",
            }
            for hint, s in sport_hints.items():
                if hint in q:
                    sport = s
                    break

        return sport or "unknown", ""


# =============================================================================
# CRYPTO DATA SOURCE
# =============================================================================

class CryptoDataSource:
    """Fetch crypto price data and sentiment."""

    # Common crypto names to CoinGecko IDs
    COIN_MAP = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "bnb": "binancecoin",
        "xrp": "ripple",
        "ada": "cardano", "cardano": "cardano",
        "doge": "dogecoin", "dogecoin": "dogecoin",
        "avax": "avalanche-2",
        "matic": "matic-network", "polygon": "matic-network",
        "dot": "polkadot", "polkadot": "polkadot",
        "link": "chainlink",
        "atom": "cosmos",
        "uni": "uniswap",
        "shib": "shiba-inu",
    }

    def get_price_data(self, coin_id: str, days: int = 30) -> Optional[dict]:
        """Get historical price data from CoinGecko."""
        cg_id = self.COIN_MAP.get(coin_id.lower(), coin_id.lower())

        data = _fetch(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            cache_key=f"cg:chart:{cg_id}:{days}",
            cache_ttl=300,
        )
        if not data or "prices" not in data:
            return None

        prices = data["prices"]
        if not prices:
            return None

        current = prices[-1][1]
        price_7d_ago = prices[-min(7 * 24, len(prices))][1] if len(prices) > 7 else prices[0][1]
        price_30d_ago = prices[0][1]

        return {
            "source": "CoinGecko",
            "coin": cg_id,
            "current_price": current,
            "price_7d_ago": price_7d_ago,
            "price_30d_ago": price_30d_ago,
            "change_7d_pct": round((current - price_7d_ago) / price_7d_ago * 100, 2) if price_7d_ago else 0,
            "change_30d_pct": round((current - price_30d_ago) / price_30d_ago * 100, 2) if price_30d_ago else 0,
            "high_30d": max(p[1] for p in prices),
            "low_30d": min(p[1] for p in prices),
        }

    def get_market_data(self, coin_id: str) -> Optional[dict]:
        """Get current market data from CoinGecko."""
        cg_id = self.COIN_MAP.get(coin_id.lower(), coin_id.lower())

        data = _fetch(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}",
            params={"localization": "false", "tickers": "false",
                    "community_data": "false", "developer_data": "false"},
            cache_key=f"cg:coin:{cg_id}",
            cache_ttl=300,
        )
        if not data:
            return None

        market = data.get("market_data", {})
        return {
            "source": "CoinGecko",
            "name": data.get("name", ""),
            "symbol": data.get("symbol", ""),
            "current_price": market.get("current_price", {}).get("usd", 0),
            "market_cap": market.get("market_cap", {}).get("usd", 0),
            "total_volume": market.get("total_volume", {}).get("usd", 0),
            "ath": market.get("ath", {}).get("usd", 0),
            "ath_change_pct": market.get("ath_change_percentage", {}).get("usd", 0),
            "price_change_24h_pct": market.get("price_change_percentage_24h", 0),
            "price_change_7d_pct": market.get("price_change_percentage_7d", 0),
            "price_change_30d_pct": market.get("price_change_percentage_30d", 0),
        }

    def get_fear_greed_index(self) -> Optional[dict]:
        """Get current Fear & Greed Index."""
        data = _fetch(
            "https://api.alternative.me/fng/",
            params={"limit": 1},
            cache_key="fng:latest",
            cache_ttl=600,
        )
        if not data or not data.get("data"):
            return None

        entry = data["data"][0]
        return {
            "source": "Alternative.me",
            "value": int(entry.get("value", 50)),
            "classification": entry.get("value_classification", "Neutral"),
        }

    def extract_crypto_asset(self, question: str) -> Optional[str]:
        """Extract crypto asset name from a market question."""
        q = question.lower()
        # Check direct mentions
        for key, cg_id in self.COIN_MAP.items():
            if key in q:
                return cg_id

        # Check for price target patterns like "$100,000" or "$100k"
        price_match = re.search(r'\$[\d,]+k?', q)
        return None

    def parse_price_target(self, question: str) -> Optional[float]:
        """
        Extract a price target from a question like 'Will BTC reach $100k?'
        Handles: $100k, $100K, $100,000, $1.5M, $1,500,000, 100k, $150000
        """
        q = question

        # Pattern 1: $100k, $1.5k, $100K (k/K suffix = multiply by 1000)
        match = re.search(r'\$?\s*(\d+(?:[.,]\d+)?)\s*[kK]\b', q)
        if match:
            val_str = match.group(1).replace(",", "")
            return float(val_str) * 1000

        # Pattern 2: $1.5M, $1M (M suffix = multiply by 1,000,000)
        match = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*[mM]\b', q)
        if match:
            return float(match.group(1)) * 1_000_000

        # Pattern 3: $100,000 or $1,500,000 (comma-separated)
        match = re.search(r'\$\s*(\d{1,3}(?:,\d{3})+)', q)
        if match:
            return float(match.group(1).replace(",", ""))

        # Pattern 4: $150000, $5000 (plain dollar amount > 100)
        match = re.search(r'\$\s*(\d+(?:\.\d+)?)', q)
        if match:
            val = float(match.group(1))
            if val > 100:  # likely a price target, not a bet amount
                return val

        return None


# =============================================================================
# ECONOMICS DATA SOURCE
# =============================================================================

class EconomicsDataSource:
    """Fetch economic indicators from FRED and Treasury.gov."""

    # Common economic indicators to FRED series IDs
    INDICATOR_MAP = {
        "fed funds": "FEDFUNDS",
        "interest rate": "FEDFUNDS",
        "federal funds": "FEDFUNDS",
        "inflation": "CPIAUCSL",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "gdp": "GDP",
        "recession": "USREC",
        "treasury": "DGS10",
        "10 year": "DGS10",
        "yield": "DGS10",
        "pce": "PCEPI",
        "nonfarm": "PAYEMS",
        "jobs": "PAYEMS",
    }

    def __init__(self):
        key = os.environ.get("FRED_API_KEY", "").strip()
        self.fred_api_key = key if key and not key.startswith("#") else ""

    def get_fred_series(self, series_id: str, limit: int = 10) -> Optional[dict]:
        """Get a FRED data series."""
        if not self.fred_api_key:
            return None

        data = _fetch(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.fred_api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
            cache_key=f"fred:{series_id}",
            cache_ttl=3600,  # 1 hour cache for economic data
        )
        if not data or "observations" not in data:
            return None

        observations = data["observations"]
        values = []
        for obs in observations:
            try:
                values.append({
                    "date": obs["date"],
                    "value": float(obs["value"]) if obs["value"] != "." else None,
                })
            except (ValueError, KeyError):
                continue

        if not values:
            return None

        latest = values[0]["value"]
        prev = values[1]["value"] if len(values) > 1 and values[1]["value"] is not None else latest

        return {
            "source": "FRED",
            "series_id": series_id,
            "latest_value": latest,
            "previous_value": prev,
            "change": round(latest - prev, 4) if latest and prev else 0,
            "trend": "rising" if latest and prev and latest > prev else "falling",
            "observations": values[:5],
        }

    def get_treasury_rates(self) -> Optional[dict]:
        """Get current Treasury rates from Treasury.gov."""
        data = _fetch(
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates",
            params={
                "sort": "-record_date",
                "page[size]": 10,
                "filter": "security_desc:in:(Treasury Bonds,Treasury Notes,Treasury Bills)",
            },
            cache_key="treasury:rates",
            cache_ttl=3600,
        )
        if not data or "data" not in data:
            return None

        rates = {}
        for entry in data["data"][:10]:
            desc = entry.get("security_desc", "")
            rate = entry.get("avg_interest_rate_amt", "0")
            try:
                rates[desc] = float(rate)
            except ValueError:
                continue

        return {
            "source": "Treasury.gov",
            "rates": rates,
        }

    def identify_indicator(self, question: str) -> Optional[str]:
        """Identify which economic indicator a question is about."""
        q = question.lower()
        for keyword, series_id in self.INDICATOR_MAP.items():
            if keyword in q:
                return series_id
        return None


# =============================================================================
# KALSHI DATA SOURCE
# =============================================================================

class KalshiDataSource:
    """Fetch market data from Kalshi's public API for cross-platform comparison."""

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    # Stop words to skip during keyword matching
    STOP_WORDS = {"will", "the", "this", "that", "what", "does", "have", "been",
                  "with", "from", "they", "their", "would", "about", "before", "after",
                  "more", "than", "less", "between", "during", "into", "each", "some"}

    def _parse_market(self, market: dict, event_title: str = "") -> dict:
        """Parse a Kalshi market dict into a standardized format."""
        title = market.get("title", "") or market.get("subtitle", "") or ""
        ticker = market.get("ticker", "")
        def _to_float(val, fallback=0):
            try:
                return float(val) if val else fallback
            except (ValueError, TypeError):
                return fallback

        # Use _dollars fields (already in 0-1 range) with string conversion
        yes_bid = _to_float(market.get("yes_bid_dollars"))
        yes_ask = _to_float(market.get("yes_ask_dollars"))
        last_price = _to_float(market.get("last_price_dollars"))

        # Fallback: convert cents fields if _dollars not available
        if not yes_bid and not yes_ask:
            yes_bid = _to_float(market.get("yes_bid")) / 100
            yes_ask = _to_float(market.get("yes_ask")) / 100
        if not last_price:
            last_price = _to_float(market.get("last_price")) / 100

        yes_price = round((yes_bid + yes_ask) / 2, 4) if yes_bid and yes_ask else last_price

        return {
            "source": "Kalshi",
            "event_title": event_title,
            "market_title": title,
            "ticker": ticker,
            "yes_price": yes_price,
            "yes_bid": round(yes_bid, 4),
            "yes_ask": round(yes_ask, 4),
            "last_price": round(last_price, 4),
            "volume": market.get("volume", 0) or 0,
            "volume_24h": market.get("volume_24h", 0) or 0,
            "open_interest": market.get("open_interest", 0) or 0,
            "status": market.get("status", ""),
            "close_time": market.get("close_time", ""),
            "url": f"https://kalshi.com/markets/{ticker}" if ticker else "",
        }

    def _get_all_events(self) -> Optional[list]:
        """Fetch a broad set of open events (cached)."""
        return _fetch(
            f"{self.BASE_URL}/events",
            params={
                "status": "open",
                "with_nested_markets": "true",
                "limit": 100,
            },
            cache_key="kalshi:all_events",
            cache_ttl=300,
        )

    def search_markets(self, query: str, limit: int = 5) -> Optional[list]:
        """Search Kalshi for markets matching a Polymarket question."""
        data = self._get_all_events()
        if not data or "events" not in data:
            return None

        query_lower = query.lower()
        # Strip dollar amounts and punctuation before extracting keywords
        cleaned = re.sub(r'\$[\d,]+', '', query_lower)
        keywords = [w.strip("?.,!") for w in cleaned.split()
                    if len(w.strip("?.,!")) > 3 and w.strip("?.,!") not in self.STOP_WORDS]
        if len(keywords) < 2:
            # Need at least 2 meaningful keywords for reliable matching
            return None

        results = []
        for event in data.get("events", []):
            event_title = event.get("title", "") or ""
            search_text = event_title.lower()

            for market in event.get("markets", []):
                market_title = (market.get("title", "") or "").lower()
                combined_text = f"{search_text} {market_title}"
                total_matches = sum(1 for kw in keywords if kw in combined_text)
                match_ratio = total_matches / len(keywords) if keywords else 0

                # Require at least 2 keyword matches AND 40% match ratio
                if total_matches < 2 or match_ratio < 0.4:
                    continue

                parsed = self._parse_market(market, event_title)
                parsed["keyword_matches"] = total_matches
                parsed["match_ratio"] = match_ratio
                results.append(parsed)

        # Sort by match quality
        results.sort(key=lambda x: (x["match_ratio"], x["keyword_matches"]), reverse=True)
        return results[:limit] if results else None

    def get_market(self, ticker: str) -> Optional[dict]:
        """Get a specific Kalshi market by ticker."""
        data = _fetch(
            f"{self.BASE_URL}/markets/{ticker}",
            cache_key=f"kalshi:market:{ticker}",
            cache_ttl=120,
        )
        if not data or "market" not in data:
            return None
        return self._parse_market(data["market"])


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

politics_source = PoliticsDataSource()
sports_source = SportsDataSource()
crypto_source = CryptoDataSource()
economics_source = EconomicsDataSource()
kalshi_source = KalshiDataSource()
