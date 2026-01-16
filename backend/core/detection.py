"""
Edge Detection
==============
Identifies trading opportunities in market data.
"""

import re
import uuid
from typing import List, Dict
from collections import defaultdict
from datetime import datetime
import logging

from .models import Market, EdgeOpportunity, EdgeType

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
    
    # Patterns to normalize dates in questions
    date_patterns = [
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
        r'\bby\s+\w+\s+\d+',
        r'\bbefore\s+\w+'
    ]
    
    # Group markets by normalized question
    groups = defaultdict(list)
    
    for market in markets:
        question = market.question.lower()
        normalized = question
        for pattern in date_patterns:
            normalized = re.sub(pattern, "<DATE>", normalized, flags=re.IGNORECASE)
        
        if "<DATE>" in normalized:
            groups[normalized].append(market)
    
    # Check each group for temporal violations
    for base_q, group in groups.items():
        if len(group) < 2:
            continue
        
        # Sort by end date
        sorted_group = sorted(
            group,
            key=lambda m: m.end_date or "9999-12-31"
        )
        
        for i in range(len(sorted_group) - 1):
            earlier = sorted_group[i]
            later = sorted_group[i + 1]
            
            # Earlier deadline should have lower or equal probability
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
    High volume often indicates informed trading.
    """
    opportunities = []
    
    for market in markets:
        if market.liquidity == 0:
            continue
        
        vol_liq_ratio = market.volume_24h / market.liquidity
        
        if vol_liq_ratio > threshold:
            opportunities.append(EdgeOpportunity(
                id=str(uuid.uuid4())[:8],
                edge_type=EdgeType.VOLUME_SIGNAL,
                description=f"Volume spike: {vol_liq_ratio:.1f}x liquidity",
                confidence=55,
                expected_return=0,  # Unknown direction
                risk_level="high",
                market_id=market.market_id,
                market_question=market.question,
                suggested_action="Research why volume is elevated. Potential informed trading.",
                reasoning=f"24h volume (${market.volume_24h:,.0f}) is {vol_liq_ratio:.1f}x liquidity (${market.liquidity:,.0f})"
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
        
        opportunities.append(EdgeOpportunity(
            id=str(uuid.uuid4())[:8],
            edge_type=EdgeType.LIQUIDITY_GAP,
            description=f"Wide spread: {market.spread_pct:.1f}%",
            confidence=65,
            expected_return=market.spread_pct / 2,  # Capture half the spread
            risk_level="medium",
            market_id=market.market_id,
            market_question=market.question,
            suggested_action=f"Provide liquidity at tighter spread",
            reasoning=f"Spread {market.spread_pct:.1f}% with ${market.volume_24h:,.0f} daily volume"
        ))
    
    return opportunities


# =============================================================================
# MAIN DETECTION FUNCTION
# =============================================================================

def detect_all_edges(markets: List[Market]) -> List[EdgeOpportunity]:
    """
    Run all edge detection algorithms on market data.
    
    Returns opportunities sorted by confidence.
    """
    opportunities = []
    
    logger.info("Running edge detection...")
    
    # Arbitrage
    opportunities.extend(detect_binary_mispricing(markets))
    opportunities.extend(detect_multi_outcome_mispricing(markets))
    opportunities.extend(detect_temporal_arbitrage(markets))
    
    # Volume/Liquidity
    opportunities.extend(detect_volume_spikes(markets))
    opportunities.extend(detect_liquidity_gaps(markets))
    
    # Sort by confidence
    opportunities.sort(key=lambda x: x.confidence, reverse=True)
    
    logger.info(f"Found {len(opportunities)} opportunities")
    
    return opportunities
