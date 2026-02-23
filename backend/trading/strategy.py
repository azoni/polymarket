"""
Strategy engine — connects edge detection to trade execution.
Scans markets, finds opportunities, and decides what to trade.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from core.ingestion import ingest_markets
from core.detection import detect_all_edges
from core.models import EdgeOpportunity, Market

from .config import TradingConfig, trading_config
from .risk import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """A concrete trade to execute."""
    token_id: str
    side: str          # BUY or SELL
    price: float       # limit price
    size: float        # shares
    market_question: str
    edge_type: str
    confidence: float
    expected_return: float
    reasoning: str
    risk_level: str = ""
    suggested_action: str = ""
    market_id: str = ""
    description: str = ""


class TradingStrategy:
    """
    Scans markets for edges and generates trade signals.
    Works with both Polymarket and Kalshi via the exchange parameter.
    """

    def __init__(
        self,
        trader,
        risk: RiskManager,
        config=None,
        exchange: str = "polymarket",
    ):
        self.trader = trader
        self.risk = risk
        self.config = config or trading_config
        self.exchange = exchange

    def scan(self) -> list[TradeSignal]:
        """
        Full scan cycle:
        1. Fetch markets from the configured exchange
        2. Run edge detection
        3. Filter by strategy thresholds
        4. Convert to trade signals
        """
        logger.info(f"Scanning {self.exchange} markets for opportunities...")

        # Fetch markets from the appropriate exchange
        try:
            if self.exchange == "kalshi":
                from core.kalshi_ingestion import ingest_kalshi_markets
                markets = ingest_kalshi_markets(max_markets=100, min_volume=0)
            else:
                markets = ingest_markets(max_markets=100, min_volume=500)
            logger.info(f"Fetched {len(markets)} {self.exchange} markets")
        except Exception as e:
            logger.error(f"Market fetch failed ({self.exchange}): {e}")
            return []

        # Run edge detection
        opportunities = detect_all_edges(markets)
        logger.info(f"Found {len(opportunities)} raw opportunities")

        # Filter and convert to trade signals
        signals = []
        for opp in opportunities:
            signal = self._evaluate_opportunity(opp, markets)
            if signal:
                signals.append(signal)

        logger.info(f"Generated {len(signals)} trade signals")
        return signals

    def _evaluate_opportunity(
        self, opp: EdgeOpportunity, markets: list[Market]
    ) -> Optional[TradeSignal]:
        """Evaluate a single opportunity and convert to a trade signal if it passes."""

        # Filter: enabled edge types
        edge_type_val = opp.edge_type.value if hasattr(opp.edge_type, 'value') else opp.edge_type
        if hasattr(self.config, 'enabled_edge_types') and edge_type_val not in self.config.enabled_edge_types:
            return None

        # Filter: confidence threshold
        if opp.confidence < self.config.min_confidence:
            return None

        # Filter: expected return
        if opp.expected_return < self.config.min_expected_return:
            return None

        # Filter: risk level
        if opp.risk_level not in self.config.allowed_risk_levels:
            return None

        # Find the market
        market = next((m for m in markets if m.market_id == opp.market_id), None)
        if not market:
            return None

        # Filter: liquidity
        if market.liquidity < self.config.min_liquidity:
            return None

        # Filter: price range (configurable)
        min_p = getattr(self.config, 'min_price', 0.05)
        max_p = getattr(self.config, 'max_price', 0.95)
        if market.current_price < min_p or market.current_price > max_p:
            return None

        # Determine trade parameters from the edge type
        token_id, side, price = self._pick_trade(opp, market)
        if not token_id:
            return None

        # Size: based on sizing_mode
        sizing = getattr(self.config, 'sizing_mode', 'confidence')
        if sizing == "fixed":
            raw_size = self.config.max_position_size
        else:
            # Scale with confidence
            raw_size = (opp.confidence / 100) * self.config.max_position_size

        # Reduce size if we already hold this token
        existing_pos = self.risk.open_positions.get(token_id)
        if existing_pos:
            existing_exp = existing_pos.get("exposure", 0) if isinstance(existing_pos, dict) else existing_pos
            remaining = self.config.max_position_size - existing_exp
            if remaining <= 0:
                return None  # already at max for this token
            raw_size = min(raw_size, remaining)

        size = round(raw_size / price, 1) if price > 0 else 0
        if size <= 0:
            return None

        return TradeSignal(
            token_id=token_id,
            side=side,
            price=round(price, 3),
            size=size,
            market_question=market.question[:80],
            edge_type=edge_type_val,
            confidence=opp.confidence,
            expected_return=opp.expected_return,
            reasoning=opp.reasoning,
            risk_level=opp.risk_level,
            suggested_action=opp.suggested_action,
            market_id=opp.market_id,
            description=opp.description,
        )

    def _pick_trade(
        self, opp: EdgeOpportunity, market: Market
    ) -> tuple[str, str, float]:
        """
        Determine which token to trade, direction, and price.
        Uses config.price_aggressiveness for limit order offset.
        Returns (token_id, side, price) or ("", "", 0) if no trade.
        """
        if not market.tokens:
            return "", "", 0

        aggr = getattr(self.config, 'price_aggressiveness', 0.99)
        min_p = getattr(self.config, 'min_price', 0.05)
        max_p = getattr(self.config, 'max_price', 0.95)

        yes_token = next((t for t in market.tokens if t.outcome == "Yes"), None)
        no_token = next((t for t in market.tokens if t.outcome == "No"), None)

        edge_val = opp.edge_type.value if hasattr(opp.edge_type, 'value') else opp.edge_type

        def _in_range(token):
            return token and min_p < token.price < max_p

        if edge_val == "arbitrage":
            if yes_token and no_token:
                if yes_token.price < no_token.price:
                    return yes_token.token_id, "BUY", yes_token.price
                else:
                    return no_token.token_id, "BUY", no_token.price

        elif edge_val == "mispricing":
            # Overpriced market: sell the more expensive side
            if yes_token and no_token:
                if yes_token.price > no_token.price and _in_range(yes_token):
                    return yes_token.token_id, "SELL", round(yes_token.price * (2 - aggr), 3)
                elif _in_range(no_token):
                    return no_token.token_id, "SELL", round(no_token.price * (2 - aggr), 3)

        elif edge_val == "liquidity_gap":
            tradeable = None
            for t in [yes_token, no_token]:
                if _in_range(t):
                    if tradeable is None or abs(t.price - 0.5) < abs(tradeable.price - 0.5):
                        tradeable = t
            if tradeable:
                # Liquidity gap uses slightly more aggressive offset
                liq_aggr = min(aggr, 0.985)
                bid_price = tradeable.price * liq_aggr
                if min_p < bid_price < max_p:
                    return tradeable.token_id, "BUY", round(bid_price, 3)

        elif edge_val == "volume_signal":
            # Volume supports the side the price is leaning toward
            if market.current_price > 0.5 and _in_range(yes_token):
                return yes_token.token_id, "BUY", round(yes_token.price * aggr, 3)
            elif market.current_price < 0.5 and _in_range(no_token):
                return no_token.token_id, "BUY", round(no_token.price * aggr, 3)

        elif edge_val == "sentiment":
            # Positive sentiment -> buy YES; negative -> buy NO
            if "positive" in opp.description.lower() and _in_range(yes_token):
                return yes_token.token_id, "BUY", round(yes_token.price * aggr, 3)
            elif "negative" in opp.description.lower() and _in_range(no_token):
                return no_token.token_id, "BUY", round(no_token.price * aggr, 3)

        elif edge_val == "consensus_divergence":
            # Agent sees higher probability -> buy YES; lower -> buy NO
            if "buy yes" in opp.suggested_action.lower() and _in_range(yes_token):
                return yes_token.token_id, "BUY", round(yes_token.price * aggr, 3)
            elif "buy no" in opp.suggested_action.lower() and _in_range(no_token):
                return no_token.token_id, "BUY", round(no_token.price * aggr, 3)

        elif edge_val == "deadline_urgency":
            # Near deadline: lean with the price direction
            if market.current_price > 0.55 and _in_range(yes_token):
                return yes_token.token_id, "BUY", round(yes_token.price * aggr, 3)
            elif market.current_price < 0.45 and _in_range(no_token):
                return no_token.token_id, "BUY", round(no_token.price * aggr, 3)

        elif edge_val in ("correlation", "category_momentum"):
            # Follow the direction the related market/category is trending
            if market.current_price < 0.45 and _in_range(yes_token):
                # Market is low relative to peers, buy YES expecting catch-up
                return yes_token.token_id, "BUY", round(yes_token.price * aggr, 3)
            elif market.current_price > 0.55 and _in_range(no_token):
                return no_token.token_id, "BUY", round(no_token.price * aggr, 3)

        return "", "", 0

    def _deduplicate_signals(self, signals: list[TradeSignal]) -> list[TradeSignal]:
        """Keep only the highest-confidence signal per token_id."""
        best_by_token: dict[str, TradeSignal] = {}
        for sig in signals:
            existing = best_by_token.get(sig.token_id)
            if not existing or sig.confidence > existing.confidence:
                best_by_token[sig.token_id] = sig
        return list(best_by_token.values())

    def execute_signals(self, signals: list[TradeSignal]) -> list[dict]:
        """Execute a list of trade signals through risk checks and the trader."""
        # Deduplicate: only one signal per token
        signals = self._deduplicate_signals(signals)
        results = []

        for signal in signals:
            # Risk check
            allowed, reason = self.risk.check_trade(
                signal.token_id, signal.side, signal.price, signal.size
            )

            if not allowed:
                logger.warning(f"BLOCKED by risk: {reason} | {signal.market_question}")
                results.append({
                    "status": "blocked",
                    "reason": reason,
                    "signal": signal.__dict__,
                })
                continue

            # Execute
            result = self.trader.place_limit_order(
                token_id=signal.token_id,
                side=signal.side,
                price=signal.price,
                size=signal.size,
            )

            if result:
                self.risk.record_trade(
                    signal.token_id, signal.side, signal.price, signal.size,
                    market=signal.market_question,
                    edge_type=signal.edge_type,
                    reasoning=signal.reasoning,
                    market_id=signal.market_id,
                )
                results.append({
                    "status": "executed" if not self.config.dry_run else "dry_run",
                    "order": result,
                    "signal": signal.__dict__,
                })
                logger.info(f"{'[DRY RUN] ' if self.config.dry_run else ''}EXECUTED: "
                           f"{signal.side} {signal.size} @ ${signal.price} | "
                           f"{signal.market_question}")
            else:
                results.append({
                    "status": "failed",
                    "signal": signal.__dict__,
                })

        return results
