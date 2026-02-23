"""
Edge Detection
==============
Identifies trading opportunities in market data.
"""

import re
import uuid
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime
import logging

from .models import Market, EdgeOpportunity, Prediction, EdgeType

logger = logging.getLogger(__name__)


# =============================================================================
# ARBITRAGE DETECTION
# =============================================================================

def detect_binary_mispricing(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Find binary markets where YES + NO != 1.00

    If sum < 0.97: Can buy both sides for guaranteed profit
    If sum > 1.04: One side is overpriced
    """
    opportunities = []

    for market in markets:
        if len(market.tokens) != 2:
            continue

        yes_token = next((t for t in market.tokens if t.outcome == "Yes"), None)
        no_token = next((t for t in market.tokens if t.outcome == "No"), None)

        if not yes_token or not no_token:
            continue

        total = yes_token.price + no_token.price

        # Underpriced - arbitrage opportunity
        if total < 0.97:
            expected_return = ((1.0 - total) / total) * 100 - 2  # Minus ~2% fees
            if expected_return > 1:
                opportunities.append(EdgeOpportunity(
                    id=str(uuid.uuid4())[:8],
                    edge_type=EdgeType.ARBITRAGE,
                    description=f"Binary underpricing: YES ({yes_token.price:.1%}) + NO ({no_token.price:.1%}) = {total:.1%}",
                    confidence=90,
                    expected_return=expected_return,
                    risk_level="low",
                    market_id=market.market_id,
                    market_question=market.question,
                    suggested_action=f"Buy both YES at {yes_token.price:.2%} and NO at {no_token.price:.2%}",
                    reasoning=f"Combined price {total:.1%} < 1.00 means guaranteed profit after fees"
                ))

        # Overpriced - indicates mispricing
        elif total > 1.04:
            opportunities.append(EdgeOpportunity(
                id=str(uuid.uuid4())[:8],
                edge_type=EdgeType.MISPRICING,
                description=f"Binary overpricing: Sum = {total:.1%}",
                confidence=70,
                expected_return=(total - 1.0) * 100 / 2,
                risk_level="medium",
                market_id=market.market_id,
                market_question=market.question,
                suggested_action="Identify and sell the overpriced side",
                reasoning=f"YES ({yes_token.price:.1%}) + NO ({no_token.price:.1%}) = {total:.1%} > 1.00"
            ))

    return opportunities


def detect_multi_outcome_mispricing(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Find multi-outcome markets where probabilities don't sum to 1.
    For mutually exclusive outcomes, sum should = 1.00
    """
    opportunities = []

    for market in markets:
        if len(market.tokens) <= 2:
            continue

        total = sum(t.price for t in market.tokens)

        if total < 0.95:
            expected_return = ((1.0 - total) / total) * 100 - 2
            if expected_return > 2:
                token_summary = ", ".join([
                    f"{t.outcome}: {t.price:.1%}" for t in market.tokens[:4]
                ])

                opportunities.append(EdgeOpportunity(
                    id=str(uuid.uuid4())[:8],
                    edge_type=EdgeType.ARBITRAGE,
                    description=f"Multi-outcome underpricing: Sum = {total:.1%}",
                    confidence=85,
                    expected_return=expected_return,
                    risk_level="low",
                    market_id=market.market_id,
                    market_question=market.question,
                    suggested_action="Buy all outcomes proportionally",
                    reasoning=f"Outcomes: {token_summary}. Total {total:.1%} < 1.00"
                ))

    return opportunities


# =============================================================================
# TEMPORAL ARBITRAGE
# =============================================================================

def detect_temporal_arbitrage(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Find temporal inconsistencies: "X by March" should be <= "X by June"
    """
    opportunities = []

    date_patterns = [
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
        r'\bby\s+\w+\s+\d+',
        r'\bbefore\s+\w+'
    ]

    groups = defaultdict(list)

    for market in markets:
        question = market.question.lower()
        normalized = question
        for pattern in date_patterns:
            normalized = re.sub(pattern, "<DATE>", normalized, flags=re.IGNORECASE)

        if "<DATE>" in normalized:
            groups[normalized].append(market)

    for base_q, group in groups.items():
        if len(group) < 2:
            continue

        sorted_group = sorted(
            group,
            key=lambda m: m.end_date or "9999-12-31"
        )

        for i in range(len(sorted_group) - 1):
            earlier = sorted_group[i]
            later = sorted_group[i + 1]

            if earlier.current_price > later.current_price + 0.03:
                diff = earlier.current_price - later.current_price

                opportunities.append(EdgeOpportunity(
                    id=str(uuid.uuid4())[:8],
                    edge_type=EdgeType.ARBITRAGE,
                    description=f"Temporal mispricing: Earlier ({earlier.current_price:.1%}) > Later ({later.current_price:.1%})",
                    confidence=85,
                    expected_return=diff * 100,
                    risk_level="low",
                    market_id=earlier.market_id,
                    market_question=earlier.question,
                    suggested_action=f"Sell YES on earlier market, Buy YES on later market",
                    reasoning=f"Event by earlier date can't be more likely than by later date. {earlier.question[:50]} vs {later.question[:50]}"
                ))

    return opportunities


# =============================================================================
# VOLUME & LIQUIDITY ANALYSIS
# =============================================================================

def detect_volume_spikes(markets: List[Market], threshold: float = 3.0) -> List[EdgeOpportunity]:
    """
    Find markets with unusual volume relative to liquidity.
    Only signals when price is meaningfully away from 50/50 (clear direction).
    """
    opportunities = []

    for market in markets:
        if market.liquidity == 0:
            continue

        vol_liq_ratio = market.volume_24h / market.liquidity
        if vol_liq_ratio <= threshold:
            continue

        price_deviation = abs(market.current_price - 0.5)
        if price_deviation < 0.1:
            continue

        if market.current_price > 0.5:
            direction = "YES"
            suggested = f"Volume supports YES side (price at {market.current_price:.0%})"
        else:
            direction = "NO"
            suggested = f"Volume supports NO side (price at {market.current_price:.0%})"

        base_confidence = min(75, 50 + (vol_liq_ratio - threshold) * 3)
        confidence = min(80, base_confidence + price_deviation * 20)
        expected_return = round(price_deviation * 10, 1)

        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.VOLUME_SIGNAL,
            description=f"Volume spike: {vol_liq_ratio:.1f}x liquidity, {direction} bias",
            confidence=round(confidence, 0),
            expected_return=expected_return,
            risk_level="high",
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=suggested,
            reasoning=f"24h volume (${market.volume_24h:,.0f}) is {vol_liq_ratio:.1f}x "
                      f"liquidity (${market.liquidity:,.0f}). Price at {market.current_price:.0%} "
                      f"suggests {direction} momentum."
        ))

    return opportunities


def detect_liquidity_gaps(markets: List[Market], min_spread: float = 3.0) -> List[EdgeOpportunity]:
    """
    Find markets with wide spreads where market-making could be profitable.
    """
    opportunities = []

    for market in markets:
        if market.spread_pct < min_spread or market.volume_24h < 1000:
            continue

        spread = market.spread_pct

        if spread > 50:
            risk, confidence = "high", 50
        elif spread > 20:
            risk, confidence = "high", 55
        elif spread > 10:
            risk, confidence = "medium", 65
        else:
            risk, confidence = "medium", 70

        expected_return = min(spread / 3, 15.0)

        token_info = ""
        if market.tokens:
            prices = [f"{t.outcome}: {t.price:.0%}" for t in market.tokens[:3]]
            token_info = f" Tokens: {', '.join(prices)}."
            t0 = market.tokens[0]
            if t0.best_bid > 0 and t0.best_ask > 0:
                token_info += f" Bid: {t0.best_bid:.3f}, Ask: {t0.best_ask:.3f}."

        target_spread = max(1.0, spread / 3)

        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.LIQUIDITY_GAP,
            description=f"Wide spread: {spread:.1f}% ({risk} risk)",
            confidence=confidence,
            expected_return=round(expected_return, 1),
            risk_level=risk,
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=f"Provide liquidity at tighter spread (target {target_spread:.1f}%)",
            reasoning=f"Spread {spread:.1f}% on ${market.volume_24h:,.0f} daily volume, "
                      f"${market.liquidity:,.0f} liquidity.{token_info}"
        ))

    return opportunities


# =============================================================================
# TIGHTENED DETECTION STRATEGIES
# =============================================================================

def detect_deadline_urgency(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Markets approaching resolution with uncertain pricing.
    Only flags markets within 48 hours where price is genuinely uncertain.
    """
    opportunities = []

    for market in markets:
        days = market.days_until_resolution
        if days is None or days > 2 or days < 0:
            continue  # Only flag within 48 hours

        price = market.current_price
        # Must be genuinely uncertain (not near-resolved)
        if price < 0.15 or price > 0.85:
            continue

        uncertainty = min(price, 1 - price)

        urgency_score = (1 - days / 2) * uncertainty * 2
        confidence = min(55, 35 + urgency_score * 50)
        expected_return = round(uncertainty * 20, 1)

        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.DEADLINE_URGENCY,
            description=f"Deadline urgency: {days}d left, price at {price:.0%}",
            confidence=round(confidence),
            expected_return=expected_return,
            risk_level="high",
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=f"Research imminent resolution — price should move sharply soon",
            reasoning=f"Only {days} day(s) until resolution but price is {price:.0%} "
                      f"(uncertainty: {uncertainty:.0%}). Expect rapid convergence."
        ))

    return opportunities


def detect_correlation_edge(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Find correlated markets where one has moved but the other hasn't.
    Requires strong keyword overlap (70%+) and at least 3 shared keywords.
    """
    opportunities = []

    # Stop words to exclude from keyword matching
    stop_words = {"will", "the", "be", "by", "in", "to", "a", "an", "of", "is",
                  "at", "on", "for", "and", "or", "?", "before", "after", "does",
                  "have", "has", "been", "would", "could", "should", "was", "were",
                  "not", "more", "than", "this", "that", "with", "from"}

    market_keywords = {}
    for m in markets:
        words = set(w.strip("?.,!").lower() for w in m.question.split()) - stop_words
        words = {w for w in words if len(w) > 2}
        market_keywords[m.market_id] = words

    market_list = list(markets)
    for i in range(len(market_list)):
        for j in range(i + 1, min(i + 50, len(market_list))):
            m1, m2 = market_list[i], market_list[j]
            kw1 = market_keywords.get(m1.market_id, set())
            kw2 = market_keywords.get(m2.market_id, set())

            if not kw1 or not kw2:
                continue

            overlap = kw1 & kw2

            # Require strong overlap: 70%+ AND at least 3 shared keywords
            if len(overlap) < 3:
                continue
            overlap_ratio = len(overlap) / min(len(kw1), len(kw2))
            if overlap_ratio < 0.7:
                continue

            price_diff = abs(m1.current_price - m2.current_price)
            if price_diff < 0.15:
                continue

            m1_dev = abs(m1.current_price - 0.5)
            m2_dev = abs(m2.current_price - 0.5)

            if m1_dev > m2_dev:
                moved, stale = m1, m2
            else:
                moved, stale = m2, m1

            confidence = min(60, 30 + price_diff * 80)
            expected_return = round(price_diff * 50, 1)

            opportunities.append(EdgeOpportunity(
                id=str(uuid.uuid4())[:8],
                edge_type=EdgeType.CORRELATION,
                description=f"Correlated market divergence: {price_diff:.0%} gap",
                confidence=round(confidence),
                expected_return=min(expected_return, 20),
                risk_level="medium",
                market_id=stale.market_id,
                market_question=stale.question,
                suggested_action=f"Related market at {moved.current_price:.0%} — this one may follow",
                reasoning=f"Related market \"{moved.question[:60]}\" is at {moved.current_price:.0%} "
                          f"while this one is at {stale.current_price:.0%}. "
                          f"Shared keywords: {', '.join(list(overlap)[:5])}."
            ))

    return opportunities


def detect_consensus_divergence(
    markets: List[Market],
    predictions: List[Prediction],
) -> List[EdgeOpportunity]:
    """
    When research agent predictions diverge significantly from market price.
    Only trusts predictions from LLM-backed agents (not heuristic fallbacks).
    """
    opportunities = []

    pred_by_market = {p.market_id: p for p in predictions}

    for market in markets:
        pred = pred_by_market.get(market.market_id)
        if not pred:
            continue

        # Skip heuristic-only predictions (low confidence = likely guessing)
        if pred.confidence <= 35:
            continue

        # Require meaningful divergence and decent confidence
        if abs(pred.edge) < 0.12 or pred.confidence < 60:
            continue

        confidence = min(70, pred.confidence * 0.7 + abs(pred.edge) * 40)
        expected_return = round(abs(pred.edge) * 100, 1)

        if pred.edge > 0:
            action = f"Buy YES — agent predicts {pred.predicted_probability:.0%} vs market {market.current_price:.0%}"
        else:
            action = f"Buy NO — agent predicts {pred.predicted_probability:.0%} vs market {market.current_price:.0%}"

        data_src = f" Data: {', '.join(pred.data_sources)}." if pred.data_sources else ""

        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.CONSENSUS_DIVERGENCE,
            description=f"Agent divergence: {pred.agent_name} sees {abs(pred.edge):.0%} edge",
            confidence=round(confidence),
            expected_return=min(expected_return, 25),
            risk_level="medium",
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=action,
            reasoning=f"{pred.agent_name} predicts {pred.predicted_probability:.0%} "
                      f"(confidence: {pred.confidence}%) vs market at {market.current_price:.0%}. "
                      f"{pred.reasoning[:100]}{data_src}"
        ))

    return opportunities


def detect_category_momentum(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Track if a category is trending in one direction.
    Requires at least 5 markets in a category for meaningful signal.
    """
    opportunities = []

    by_category: Dict[str, List[Market]] = defaultdict(list)
    for m in markets:
        by_category[m.category.value].append(m)

    for cat, cat_markets in by_category.items():
        if len(cat_markets) < 5:  # Need at least 5 for meaningful average
            continue

        prices = [m.current_price for m in cat_markets]
        avg_price = sum(prices) / len(prices)

        cat_bias = avg_price - 0.5
        if abs(cat_bias) < 0.05:
            continue

        for market in cat_markets:
            market_bias = market.current_price - 0.5
            if cat_bias > 0 and market_bias < -0.05:
                divergence = cat_bias - market_bias
            elif cat_bias < 0 and market_bias > 0.05:
                divergence = market_bias - cat_bias
            else:
                continue

            # Require larger divergence (was 0.15, now 0.25)
            if divergence < 0.25:
                continue

            confidence = min(50, 25 + divergence * 60)
            expected_return = round(divergence * 30, 1)

            direction = "YES" if cat_bias > 0 else "NO"

            opportunities.append(EdgeOpportunity(
                id=str(uuid.uuid4())[:8],
                edge_type=EdgeType.CATEGORY_MOMENTUM,
                description=f"Category momentum: {cat} trending {direction}",
                confidence=round(confidence),
                expected_return=min(expected_return, 15),
                risk_level="medium",
                market_id=market.market_id,
                market_question=market.question,
                suggested_action=f"Category {cat} average at {avg_price:.0%} — this market at {market.current_price:.0%} may catch up",
                reasoning=f"{cat.capitalize()} category ({len(cat_markets)} markets) averages "
                          f"{avg_price:.0%} (bias {direction}). This market diverges at "
                          f"{market.current_price:.0%}. Note: category averages are weak signals."
            ))

    return opportunities


def detect_sentiment_edge(
    markets: List[Market], data_sources=None
) -> List[EdgeOpportunity]:
    """
    Cross-reference news sentiment with market price.
    Requires strong sentiment + significant price divergence.
    """
    opportunities = []

    if not data_sources:
        return opportunities

    from .data_sources import politics_source

    for market in markets[:20]:
        sentiment_data = politics_source.get_news_sentiment(market.question)
        if not sentiment_data:
            continue

        sentiment = sentiment_data.get("sentiment", 0.0)
        # Require stronger sentiment signal (was 0.3, now 0.5)
        if abs(sentiment) < 0.5:
            continue

        price = market.current_price

        # Strong positive sentiment + very low price = buy signal
        if sentiment > 0.5 and price < 0.30:
            edge_strength = sentiment * (0.5 - price)
            confidence = min(45, 25 + abs(sentiment) * 15 + (0.3 - price) * 30)
            action = f"Positive sentiment ({sentiment:+.2f}) vs low price ({price:.0%})"
        # Strong negative sentiment + very high price = sell signal
        elif sentiment < -0.5 and price > 0.70:
            edge_strength = abs(sentiment) * (price - 0.5)
            confidence = min(45, 25 + abs(sentiment) * 15 + (price - 0.7) * 30)
            action = f"Negative sentiment ({sentiment:+.2f}) vs high price ({price:.0%})"
        else:
            continue

        source = sentiment_data.get("source", "Unknown")
        article_count = sentiment_data.get("articles", 0)

        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.SENTIMENT,
            description=f"Sentiment divergence: sentiment {sentiment:+.2f} vs price {price:.0%}",
            confidence=round(confidence),
            expected_return=round(edge_strength * 100, 1),
            risk_level="medium",
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=action,
            reasoning=f"Based on {article_count} articles from {source}. "
                      f"Sentiment score {sentiment:+.2f} diverges from market price {price:.0%}. "
                      f"Note: keyword-based sentiment is a weak signal."
        ))

    return opportunities


# =============================================================================
# DEDUPLICATION
# =============================================================================

def _deduplicate_opportunities(opportunities: List[EdgeOpportunity]) -> List[EdgeOpportunity]:
    """
    Remove duplicate opportunities:
    1. Same (market_id, edge_type) — keep highest confidence
    2. Same market_id with overlapping edge types — keep highest confidence
    """
    # First pass: deduplicate by (market_id, edge_type)
    best_by_type: Dict[tuple, EdgeOpportunity] = {}
    for opp in opportunities:
        key = (opp.market_id, opp.edge_type.value)
        existing = best_by_type.get(key)
        if not existing or opp.confidence > existing.confidence:
            best_by_type[key] = opp

    deduped = list(best_by_type.values())

    # Second pass: for same market, don't have both arbitrage AND mispricing
    # (they detect similar things)
    market_opps: Dict[str, List[EdgeOpportunity]] = defaultdict(list)
    for opp in deduped:
        market_opps[opp.market_id].append(opp)

    final = []
    overlapping_types = {
        frozenset({"arbitrage", "mispricing"}),
    }
    for market_id, opps in market_opps.items():
        edge_types = {o.edge_type.value for o in opps}
        for overlap_set in overlapping_types:
            if overlap_set.issubset(edge_types):
                # Keep only the highest confidence one from the overlapping set
                overlap_opps = [o for o in opps if o.edge_type.value in overlap_set]
                best = max(overlap_opps, key=lambda o: o.confidence)
                opps = [o for o in opps if o.edge_type.value not in overlap_set] + [best]
        final.extend(opps)

    return final


# =============================================================================
# MAIN DETECTION FUNCTION
# =============================================================================

def detect_all_edges(
    markets: List[Market],
    predictions: Optional[List[Prediction]] = None,
    data_sources: bool = False,
) -> List[EdgeOpportunity]:
    """
    Run all edge detection algorithms on market data.
    Returns deduplicated opportunities sorted by confidence.
    """
    opportunities = []

    logger.info("Running edge detection...")

    # Strong strategies (real math)
    opportunities.extend(detect_binary_mispricing(markets))
    opportunities.extend(detect_multi_outcome_mispricing(markets))
    opportunities.extend(detect_temporal_arbitrage(markets))
    opportunities.extend(detect_volume_spikes(markets))
    opportunities.extend(detect_liquidity_gaps(markets))

    # Weaker strategies (tightened thresholds)
    opportunities.extend(detect_deadline_urgency(markets))
    opportunities.extend(detect_correlation_edge(markets))
    opportunities.extend(detect_category_momentum(markets))

    if predictions:
        opportunities.extend(detect_consensus_divergence(markets, predictions))

    if data_sources:
        opportunities.extend(detect_sentiment_edge(markets, data_sources=True))

    # Deduplicate before returning
    opportunities = _deduplicate_opportunities(opportunities)

    # Sort by confidence
    opportunities.sort(key=lambda x: x.confidence, reverse=True)

    logger.info(f"Found {len(opportunities)} opportunities (after dedup)")

    return opportunities
