"""
Research Agents
===============
Category-specific agents that analyze markets and produce predictions.
Each agent:
  1. Fetches external data (CoinGecko, ESPN, FRED, etc.)
  2. Sends market question + data to Claude for probability estimation
  3. Falls back to heuristics if ANTHROPIC_API_KEY not set
"""

import time
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

from .models import Market, Prediction, MarketCategory
from .data_sources import (
    politics_source, sports_source, crypto_source, economics_source, kalshi_source
)
from . import llm_client

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIDENCE TIERS — calibrated caps based on data quality
# =============================================================================

CONFIDENCE_CAP_LLM_WITH_DATA = 80      # LLM + real external data
CONFIDENCE_CAP_LLM_NO_DATA = 60        # LLM but no external data
CONFIDENCE_CAP_HEURISTIC_WITH_DATA = 45 # No LLM, but has external data
CONFIDENCE_CAP_HEURISTIC_NO_DATA = 35   # No LLM, no external data


# =============================================================================
# BASE AGENT
# =============================================================================

class ResearchAgent(ABC):
    """Base class for research agents."""

    def __init__(self, name: str, categories: List[MarketCategory]):
        self.name = name
        self.categories = categories

    @abstractmethod
    def can_analyze(self, market: Market) -> bool:
        pass

    @abstractmethod
    def gather_data(self, market: Market) -> tuple:
        """Gather external data. Returns (external_data_dict, sources_used_list)."""
        pass

    @abstractmethod
    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        """Fallback heuristic analysis when LLM is unavailable."""
        pass

    def _fetch_kalshi_data(self, market: Market, external_data: Dict, sources: List[str]):
        """Cross-reference with Kalshi if a matching market exists."""
        try:
            kalshi_matches = kalshi_source.search_markets(market.question, limit=1)
            if kalshi_matches:
                best = kalshi_matches[0]
                # Only use if match quality is good (>= 50% keyword match) and has a price
                if best.get("yes_price") and best.get("match_ratio", 0) >= 0.5:
                    external_data["kalshi"] = best
                    sources.append("Kalshi")
                    logger.info(f"Kalshi match: '{best.get('market_title', '')[:60]}' "
                                f"({best['match_ratio']:.0%} match, price={best['yes_price']:.0%})")
        except Exception as e:
            logger.debug(f"Kalshi lookup failed: {e}")

    def _has_real_data(self, external_data: Dict) -> bool:
        """Check if we have meaningful external data (not just kalshi cross-ref)."""
        for key, value in external_data.items():
            if key != "kalshi" and value:
                return True
        return False

    def analyze(self, market: Market) -> Prediction:
        """Full analysis: gather data → Kalshi cross-ref → LLM (primary) → fallback to heuristic."""
        external_data, sources = self.gather_data(market)

        # Cross-reference with Kalshi
        self._fetch_kalshi_data(market, external_data, sources)

        has_data = self._has_real_data(external_data)
        used_llm = False

        # LLM is the PRIMARY analysis path when available
        if llm_client.is_available():
            llm_result = llm_client.analyze_market(
                question=market.question,
                category=market.category.value if hasattr(market.category, 'value') else str(market.category),
                current_price=market.current_price,
                external_data=external_data,
            )
            if llm_result:
                sources.append("Claude")
                prediction = self._llm_to_prediction(market, llm_result, sources)
                used_llm = True

                # Apply confidence cap based on data quality
                cap = CONFIDENCE_CAP_LLM_WITH_DATA if has_data else CONFIDENCE_CAP_LLM_NO_DATA
                prediction.confidence = min(prediction.confidence, cap)

                # Apply Kalshi divergence adjustment (if present)
                self._apply_kalshi_adjustment(prediction, external_data, market)
                return prediction

        # Fallback to heuristic — mark honestly
        prediction = self.heuristic_analyze(market, external_data, sources)

        # Apply heuristic confidence caps
        cap = CONFIDENCE_CAP_HEURISTIC_WITH_DATA if has_data else CONFIDENCE_CAP_HEURISTIC_NO_DATA
        prediction.confidence = min(prediction.confidence, cap)

        # Apply Kalshi divergence adjustment
        self._apply_kalshi_adjustment(prediction, external_data, market)

        return prediction

    def _apply_kalshi_adjustment(self, prediction: Prediction, external_data: Dict, market: Market):
        """Adjust prediction based on Kalshi cross-platform divergence."""
        kalshi = external_data.get("kalshi")
        if not kalshi or not kalshi.get("yes_price"):
            return

        kalshi_price = kalshi["yes_price"]
        poly_price = market.current_price
        divergence = abs(kalshi_price - poly_price)

        if divergence > 0.05:
            prediction.reasoning += (
                f" Kalshi prices this at {kalshi_price:.0%} vs Polymarket {poly_price:.0%} "
                f"({divergence:.0%} divergence)."
            )
            # Small confidence bump when cross-platform data exists (max +10)
            prediction.confidence = min(
                prediction.confidence + min(10, int(divergence * 50)),
                CONFIDENCE_CAP_LLM_WITH_DATA  # never exceed max cap
            )

    def _llm_to_prediction(self, market: Market, llm: Dict, sources: List[str]) -> Prediction:
        """Convert LLM result dict to a Prediction model."""
        predicted = llm["probability"]
        edge = predicted - market.current_price

        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=round(predicted, 4),
            current_price=market.current_price,
            edge=round(edge, 4),
            confidence=llm.get("confidence", 50),
            confidence_low=max(0, predicted - 0.10),
            confidence_high=min(1, predicted + 0.10),
            direction=llm.get("direction", "hold"),
            strength=llm.get("strength", "moderate"),
            reasoning=llm.get("reasoning", ""),
            key_risks=llm.get("key_risks", []),
            catalysts=llm.get("catalysts", []),
            data_sources=sources,
        )

    def research(self, market: Market) -> Optional[Prediction]:
        """Full research pipeline."""
        if not self.can_analyze(market):
            return None
        prediction = self.analyze(market)
        # Mark agent name — append (heuristic) if LLM was not used
        used_llm = "Claude" in (prediction.data_sources or [])
        prediction.agent_name = self.name if used_llm else f"{self.name} (heuristic)"
        prediction.polymarket_url = getattr(market, "polymarket_url", "")
        return prediction


# =============================================================================
# POLITICS AGENT
# =============================================================================

class PoliticsAgent(ResearchAgent):
    """Political markets. Data: NewsAPI."""

    KEYWORDS = ["election", "president", "senate", "congress", "trump", "biden",
                "republican", "democrat", "governor", "vote", "primary", "nominee"]

    def __init__(self):
        super().__init__("PoliticsAgent", [MarketCategory.POLITICS])

    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.POLITICS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)

    def gather_data(self, market: Market) -> tuple:
        sources = []
        data = {}
        sentiment_data = politics_source.get_news_sentiment(market.question)
        if sentiment_data:
            sources.append(sentiment_data.get("source", "News"))
            data["news_sentiment"] = sentiment_data
        return data, sources

    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        current = market.current_price
        reasoning_parts = []

        sentiment_data = external_data.get("news_sentiment")
        if sentiment_data and sentiment_data.get("source") == "NewsAPI":
            sentiment = sentiment_data.get("sentiment", 0.0)
            article_count = sentiment_data.get("articles", 0)
            adjustment = sentiment * 0.08
            predicted = max(0.02, min(0.98, current + adjustment))
            # Confidence based on data quality tier, not made-up formulas
            confidence = CONFIDENCE_CAP_HEURISTIC_WITH_DATA

            headlines = sentiment_data.get("headlines", [])
            reasoning_parts.append(
                f"Based on {article_count} recent news articles (sentiment: {sentiment:+.2f}). "
                + (f"Top headline: \"{headlines[0][:80]}\"" if headlines else "")
            )
        else:
            # No real data — be honest about it
            predicted = current + (0.03 * (0.5 - current))
            confidence = CONFIDENCE_CAP_HEURISTIC_NO_DATA
            reasoning_parts.append("No external data available. Using mean-reversion heuristic.")

        edge = predicted - current
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction, strength = "buy_yes", "strong" if edge > 0.08 else "moderate"
        else:
            direction, strength = "buy_no", "strong" if edge < -0.08 else "moderate"

        return Prediction(
            market_id=market.market_id, market_question=market.question,
            predicted_probability=round(predicted, 4), current_price=current,
            edge=round(edge, 4), confidence=round(confidence),
            confidence_low=max(0, predicted - 0.12), confidence_high=min(1, predicted + 0.12),
            direction=direction, strength=strength,
            reasoning=" ".join(reasoning_parts),
            key_risks=["Polling error", "Late-breaking news", "Turnout uncertainty"],
            catalysts=["Debates", "Major endorsements", "News events"],
            data_sources=sources,
        )


# =============================================================================
# SPORTS AGENT
# =============================================================================

class SportsAgent(ResearchAgent):
    """Sports markets. Data: Odds API or ESPN."""

    KEYWORDS = ["nfl", "nba", "mlb", "nhl", "super bowl", "championship",
                "playoffs", "finals", "game", "match", "win", "ufc", "fight"]

    def __init__(self):
        super().__init__("SportsAgent", [MarketCategory.SPORTS])

    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.SPORTS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)

    def gather_data(self, market: Market) -> tuple:
        sources = []
        data = {}
        sport, _ = sports_source.parse_sport_from_question(market.question)
        data["sport"] = sport

        if sport != "unknown":
            odds_data = sports_source.get_odds(sport)
            if odds_data:
                sources.append(odds_data.get("source", "Sports"))
                data["odds"] = odds_data
        return data, sources

    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        current = market.current_price
        reasoning_parts = []
        odds_data = external_data.get("odds")

        if odds_data:
            events = odds_data.get("events", [])
            source = odds_data.get("source", "")

            if events and source == "OddsAPI":
                best_match = self._match_event(market.question, events)
                if best_match and best_match.get("odds"):
                    odds = best_match["odds"]
                    implied_probs = {}
                    for team, american_odds in odds.items():
                        implied_probs[team] = self._american_to_prob(american_odds)
                    if implied_probs:
                        max_team = max(implied_probs, key=implied_probs.get)
                        vegas_prob = implied_probs[max_team]
                        q = market.question.lower()
                        predicted = vegas_prob if max_team.lower() in q else 1 - vegas_prob
                        predicted = max(0.02, min(0.98, predicted))
                        reasoning_parts.append(
                            f"Vegas odds imply {max_team} at {vegas_prob:.0%}. "
                            f"Polymarket at {current:.0%}."
                        )
                        confidence = CONFIDENCE_CAP_HEURISTIC_WITH_DATA
                    else:
                        predicted, confidence = current, 30
                        reasoning_parts.append("Odds data found but could not extract implied probabilities.")
                else:
                    predicted, confidence = current, 30
                    reasoning_parts.append(f"Found {len(events)} events but no close match.")
            elif events and source == "ESPN":
                event = events[0]
                reasoning_parts.append(
                    f"ESPN: {event['home']} ({event.get('home_record', '')}) vs {event['away']} ({event.get('away_record', '')}). "
                )
                predicted = current + (0.02 * (0.5 - current))
                confidence = 35
            else:
                predicted, confidence = current, 30
                reasoning_parts.append("No upcoming events found.")
        else:
            # No data at all — be honest
            predicted, confidence = current, 25
            reasoning_parts.append("Could not identify sport or fetch odds data. No prediction possible.")

        edge = predicted - current
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction, strength = "buy_yes", "strong" if edge > 0.08 else "moderate"
        else:
            direction, strength = "buy_no", "strong" if edge < -0.08 else "moderate"

        return Prediction(
            market_id=market.market_id, market_question=market.question,
            predicted_probability=round(predicted, 4), current_price=current,
            edge=round(edge, 4), confidence=round(confidence),
            confidence_low=max(0, predicted - 0.15), confidence_high=min(1, predicted + 0.15),
            direction=direction, strength=strength,
            reasoning=" ".join(reasoning_parts),
            key_risks=["Injuries", "Weather", "Unexpected lineup changes"],
            catalysts=["Injury updates", "Lineup announcements", "Recent form"],
            data_sources=sources,
        )

    def _match_event(self, question: str, events: list) -> Optional[dict]:
        q = question.lower()
        for event in events:
            home = event.get("home", "").lower()
            away = event.get("away", "").lower()
            if (home and home in q) or (away and away in q):
                return event
        return events[0] if events else None

    def _american_to_prob(self, odds: int) -> float:
        try:
            odds = int(odds)
            return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)
        except (ValueError, ZeroDivisionError):
            return 0.5


# =============================================================================
# CRYPTO AGENT
# =============================================================================

class CryptoAgent(ResearchAgent):
    """Crypto markets. Data: CoinGecko + Fear & Greed Index."""

    KEYWORDS = ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana",
                "sol", "token", "halving", "xrp", "dogecoin", "doge"]

    def __init__(self):
        super().__init__("CryptoAgent", [MarketCategory.CRYPTO])

    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.CRYPTO:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)

    def gather_data(self, market: Market) -> tuple:
        sources = []
        data = {}
        asset = crypto_source.extract_crypto_asset(market.question)
        data["asset"] = asset

        if asset:
            price_data = crypto_source.get_price_data(asset, days=30)
            if price_data:
                sources.append("CoinGecko")
                data["price"] = price_data

            fng = crypto_source.get_fear_greed_index()
            if fng:
                sources.append("Fear & Greed Index")
                data["fear_greed"] = fng

            target = crypto_source.parse_price_target(market.question)
            if target:
                data["price_target"] = target

        return data, sources

    def _is_dip_question(self, question: str) -> bool:
        """Detect if the question asks about a price DROP (vs a price rise)."""
        q = question.lower()
        dip_words = ["dip", "drop", "fall", "crash", "below", "under", "sink", "decline", "plunge"]
        return any(w in q for w in dip_words)

    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        current = market.current_price
        reasoning_parts = []
        asset = external_data.get("asset")
        price_data = external_data.get("price")
        fng = external_data.get("fear_greed")
        target = external_data.get("price_target")

        if asset and price_data:
            change_7d = price_data.get("change_7d_pct", 0)
            change_30d = price_data.get("change_30d_pct", 0)
            current_crypto_price = price_data.get("current_price", 0)
            reasoning_parts.append(
                f"{asset.capitalize()} at ${current_crypto_price:,.0f}. "
                f"7d: {change_7d:+.1f}%, 30d: {change_30d:+.1f}%."
            )

            if target and current_crypto_price > 0:
                is_dip = self._is_dip_question(market.question)
                distance_pct = (target - current_crypto_price) / current_crypto_price * 100

                if is_dip:
                    if distance_pct >= 0:
                        predicted = max(0.7, min(0.95, 0.85))
                        reasoning_parts.append(f"Already below target ${target:,.0f}. Dip has occurred.")
                    elif abs(distance_pct) < 15:
                        momentum_factor = max(-0.1, min(0.1, change_7d / 100))
                        predicted = max(0.2, min(0.6, 0.4 + momentum_factor))
                        reasoning_parts.append(f"Only {abs(distance_pct):.0f}% above dip target ${target:,.0f}.")
                    elif abs(distance_pct) < 40:
                        predicted = max(0.05, min(0.25, 0.15 - change_30d / 500))
                        reasoning_parts.append(f"Needs {abs(distance_pct):.0f}% drop to reach ${target:,.0f}. Unlikely in short term.")
                    else:
                        predicted = max(0.02, min(0.1, 0.05))
                        reasoning_parts.append(f"Would need {abs(distance_pct):.0f}% crash to ${target:,.0f}. Extremely unlikely.")
                else:
                    if distance_pct <= 0:
                        predicted = max(0.7, min(0.95, current + 0.1))
                        reasoning_parts.append(f"Already above target ${target:,.0f}.")
                    elif distance_pct < 10:
                        predicted = max(0.4, min(0.85, 0.6 + change_7d / 100))
                        reasoning_parts.append(f"Within {distance_pct:.0f}% of target ${target:,.0f}.")
                    elif distance_pct < 30:
                        predicted = max(0.15, min(0.6, 0.35 + change_30d / 200))
                        reasoning_parts.append(f"{distance_pct:.0f}% below target ${target:,.0f}.")
                    else:
                        predicted = max(0.05, min(0.3, 0.15 + change_30d / 300))
                        reasoning_parts.append(f"Significant distance ({distance_pct:.0f}%) to target ${target:,.0f}.")
                # Has price target + price data = decent heuristic
                confidence = CONFIDENCE_CAP_HEURISTIC_WITH_DATA
            else:
                # Momentum-only prediction — cap lower
                momentum = (change_7d + change_30d / 2) / 100
                predicted = max(0.05, min(0.95, current + momentum * 0.15))
                confidence = min(40, 30 + abs(change_7d) * 0.3)
                reasoning_parts.append("Using momentum-based prediction (no price target found).")
        else:
            predicted, confidence = current, 25
            reasoning_parts.append("Could not identify crypto asset or fetch price data.")

        if fng:
            fng_value = fng.get("value", 50)
            fng_class = fng.get("classification", "Neutral")
            reasoning_parts.append(f"Fear & Greed: {fng_value} ({fng_class}).")
            if fng_value < 25:
                predicted = min(0.95, predicted + 0.03)
            elif fng_value > 75:
                predicted = max(0.05, predicted - 0.03)

        predicted = max(0.02, min(0.98, predicted))
        edge = predicted - current
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction, strength = "buy_yes", "strong" if edge > 0.08 else "moderate"
        else:
            direction, strength = "buy_no", "strong" if edge < -0.08 else "moderate"

        return Prediction(
            market_id=market.market_id, market_question=market.question,
            predicted_probability=round(predicted, 4), current_price=current,
            edge=round(edge, 4), confidence=round(confidence),
            confidence_low=max(0, predicted - 0.18), confidence_high=min(1, predicted + 0.18),
            direction=direction, strength=strength,
            reasoning=" ".join(reasoning_parts),
            key_risks=["Volatility", "Regulatory news", "Market manipulation"],
            catalysts=["ETF decisions", "Protocol upgrades", "Macro events"],
            data_sources=sources,
        )


# =============================================================================
# ECONOMICS AGENT
# =============================================================================

class EconomicsAgent(ResearchAgent):
    """Economics markets. Data: FRED API or Treasury.gov."""

    KEYWORDS = ["fed", "interest rate", "inflation", "gdp", "unemployment",
                "recession", "cpi", "fomc", "treasury", "rate cut", "rate hike"]

    def __init__(self):
        super().__init__("EconomicsAgent", [MarketCategory.ECONOMICS])

    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.ECONOMICS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)

    def gather_data(self, market: Market) -> tuple:
        sources = []
        data = {}
        indicator = economics_source.identify_indicator(market.question)
        data["indicator"] = indicator

        if indicator:
            fred_data = economics_source.get_fred_series(indicator)
            if fred_data:
                sources.append("FRED")
                data["fred"] = fred_data

        treasury = economics_source.get_treasury_rates()
        if treasury:
            sources.append("Treasury.gov")
            data["treasury"] = treasury

        return data, sources

    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        current = market.current_price
        reasoning_parts = []
        indicator = external_data.get("indicator")
        fred_data = external_data.get("fred")
        treasury = external_data.get("treasury")

        if fred_data:
            latest = fred_data.get("latest_value")
            prev = fred_data.get("previous_value")
            trend = fred_data.get("trend", "stable")
            change = fred_data.get("change", 0)
            reasoning_parts.append(
                f"FRED {indicator}: latest {latest}, previous {prev} ({trend}, change: {change:+.3f})."
            )
            q_lower = market.question.lower()
            if "cut" in q_lower or "lower" in q_lower:
                predicted = min(0.95, current + 0.06) if trend == "falling" else max(0.05, current - 0.04)
                reasoning_parts.append("Trend supports this direction." if trend == "falling" else "Trend is against.")
            elif "hike" in q_lower or "raise" in q_lower or "higher" in q_lower:
                predicted = min(0.95, current + 0.06) if trend == "rising" else max(0.05, current - 0.04)
                reasoning_parts.append("Trend supports this direction." if trend == "rising" else "Trend is against.")
            else:
                momentum = 0.04 if trend == "rising" else -0.04 if trend == "falling" else 0
                predicted = max(0.05, min(0.95, current + momentum))
            confidence = CONFIDENCE_CAP_HEURISTIC_WITH_DATA
        else:
            predicted, confidence = current, 30
            if indicator:
                reasoning_parts.append(f"No FRED data available for {indicator}. Set FRED_API_KEY for better analysis.")

        if treasury:
            rates = treasury.get("rates", {})
            if rates:
                rate_info = ", ".join([f"{k}: {v:.2f}%" for k, v in list(rates.items())[:3]])
                reasoning_parts.append(f"Treasury rates: {rate_info}.")

        if not sources:
            predicted, confidence = current, CONFIDENCE_CAP_HEURISTIC_NO_DATA
            reasoning_parts.append("No external economic data available.")

        predicted = max(0.02, min(0.98, predicted))
        edge = predicted - current
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction, strength = "buy_yes", "strong" if edge > 0.08 else "moderate"
        else:
            direction, strength = "buy_no", "strong" if edge < -0.08 else "moderate"

        return Prediction(
            market_id=market.market_id, market_question=market.question,
            predicted_probability=round(predicted, 4), current_price=current,
            edge=round(edge, 4), confidence=round(confidence),
            confidence_low=max(0, predicted - 0.08), confidence_high=min(1, predicted + 0.08),
            direction=direction, strength=strength,
            reasoning=" ".join(reasoning_parts),
            key_risks=["Data revisions", "Fed pivot", "External shocks"],
            catalysts=["FOMC meetings", "CPI releases", "Jobs reports"],
            data_sources=sources,
        )


# =============================================================================
# GENERAL AGENT
# =============================================================================

class GeneralAgent(ResearchAgent):
    """Fallback agent. Relies on LLM when available, otherwise minimal heuristic."""

    def __init__(self):
        super().__init__("GeneralAgent", [MarketCategory.OTHER])

    def can_analyze(self, market: Market) -> bool:
        return True

    def gather_data(self, market: Market) -> tuple:
        # No reliable external data source for general markets
        return {}, []

    def heuristic_analyze(self, market: Market, external_data: Dict, sources: List[str]) -> Prediction:
        current = market.current_price

        # Honest: we have no data, just apply minimal mean-reversion
        predicted = current + (0.02 * (0.5 - current))
        confidence = 25

        edge = predicted - current
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction, strength = "buy_yes", "weak"
        else:
            direction, strength = "buy_no", "weak"

        return Prediction(
            market_id=market.market_id, market_question=market.question,
            predicted_probability=round(predicted, 4), current_price=current,
            edge=round(edge, 4), confidence=round(confidence),
            confidence_low=max(0, predicted - 0.25), confidence_high=min(1, predicted + 0.25),
            direction=direction, strength=strength,
            reasoning="No specialized data source for this market. Requires manual research or LLM analysis.",
            key_risks=["Unknown factors"], catalysts=["Varies"],
            data_sources=sources,
        )


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class AgentOrchestrator:
    """Coordinates research agents and logs activity."""

    def __init__(self):
        self.agents = [
            PoliticsAgent(),
            SportsAgent(),
            CryptoAgent(),
            EconomicsAgent(),
            GeneralAgent()
        ]
        self.db = None

    def find_agent(self, market: Market) -> ResearchAgent:
        for agent in self.agents:
            if agent.can_analyze(market):
                return agent
        return self.agents[-1]

    def research_market(self, market: Market) -> Prediction:
        agent = self.find_agent(market)
        start = time.time()
        prediction = agent.research(market)
        duration_ms = (time.time() - start) * 1000

        if self.db and prediction:
            try:
                self.db.log_agent_activity(
                    agent_name=agent.name,
                    market_id=market.market_id,
                    market_question=market.question[:100],
                    action="analyze",
                    data_source=", ".join(prediction.data_sources) if prediction.data_sources else "",
                    success=True,
                    duration_ms=round(duration_ms, 1),
                )
            except Exception as e:
                logger.warning(f"Failed to log agent activity: {e}")

        return prediction

    def research_markets(
        self, markets: List[Market], min_edge: float = 0.0
    ) -> List[Prediction]:
        predictions = []
        llm_mode = "LLM" if llm_client.is_available() else "heuristic"
        logger.info(f"Researching {len(markets)} markets (mode: {llm_mode})")

        for market in markets:
            try:
                pred = self.research_market(market)
                if pred and abs(pred.edge) >= min_edge:
                    predictions.append(pred)
            except Exception as e:
                logger.error(f"Agent error for {market.market_id}: {e}")
                if self.db:
                    agent = self.find_agent(market)
                    self.db.log_agent_activity(
                        agent_name=agent.name,
                        market_id=market.market_id,
                        market_question=market.question[:100],
                        action="analyze",
                        success=False,
                        details=str(e),
                    )

        predictions.sort(key=lambda p: abs(p.edge), reverse=True)
        logger.info(f"Generated {len(predictions)} predictions ({llm_mode})")
        return predictions

    def get_agent_health(self) -> List[dict]:
        result = []
        for agent in self.agents:
            status = "online"
            if self.db:
                stats = self.db.get_agent_activity(agent_name=agent.name, limit=10)
                if not stats:
                    status = "idle"
                else:
                    recent_failures = sum(1 for s in stats if not s.get("success", True))
                    if recent_failures > len(stats) * 0.5:
                        status = "degraded"
            result.append({
                "name": agent.name,
                "status": status,
                "categories": [c.value for c in agent.categories],
            })
        return result
