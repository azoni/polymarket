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
from .client import PolymarketTrader
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
    Scans Polymarket for edges and generates trade signals.
    Uses the existing edge detection + additional filters.
    """

    def __init__(
        self,
        trader: PolymarketTrader,
        risk: RiskManager,
        config: Optional[TradingConfig] = None,
    ):
        self.trader = trader
        self.risk = risk
        self.config = config or trading_config

    def scan(self) -> list[TradeSignal]:
        """
        Full scan cycle:
        1. Fetch markets from Polymarket Gamma API
        2. Run edge detection
        3. Filter by strategy thresholds
        4. Convert to trade signals
        """
        logger.info("Scanning markets for opportunities...")

        # Fetch and process markets using existing ingestion pipeline
        try:
            markets = ingest_markets(max_markets=100, min_volume=500)
            logger.info(f"Fetched {len(markets)} markets")
        except Exception as e:
            logger.error(f"Market fetch failed: {e}")
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

        # Filter: skip extreme-probability markets (untradeable)
        if market.current_price < 0.05 or market.current_price > 0.95:
            return None

        # Determine trade parameters from the edge type
        token_id, side, price = self._pick_trade(opp, market)
        if not token_id:
            return None

        # Size: scale with confidence, cap at max_position_size
        raw_size = (opp.confidence / 100) * self.config.max_position_size
        size = round(raw_size / price, 1) if price > 0 else 0
        if size <= 0:
            return None

        return TradeSignal(
            token_id=token_id,
            side=side,
            price=round(price, 3),
            size=size,
            market_question=market.question[:80],
            edge_type=opp.edge_type.value,
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
        Returns (token_id, side, price) or ("", "", 0) if no trade.
        """
        if not market.tokens:
            return "", "", 0

        yes_token = next((t for t in market.tokens if t.outcome == "Yes"), None)
        no_token = next((t for t in market.tokens if t.outcome == "No"), None)

        if opp.edge_type.value == "arbitrage":
            # For arbitrage: buy the cheaper side
            if yes_token and no_token:
                if yes_token.price < no_token.price:
                    return yes_token.token_id, "BUY", yes_token.price
                else:
                    return no_token.token_id, "BUY", no_token.price

        elif opp.edge_type.value == "mispricing":
            # Buy underpriced or sell overpriced
            action = opp.suggested_action.lower()
            if "buy" in action and "yes" in action and yes_token:
                return yes_token.token_id, "BUY", yes_token.price
            elif "buy" in action and "no" in action and no_token:
                return no_token.token_id, "BUY", no_token.price
            elif "sell" in action and yes_token:
                return yes_token.token_id, "SELL", yes_token.price

        elif opp.edge_type.value == "liquidity_gap":
            # Provide liquidity — buy slightly below AMM price
            # (CLOB books are mostly empty, AMM price is the reference)
            tradeable = None
            for t in [yes_token, no_token]:
                if t and 0.1 < t.price < 0.9:
                    if tradeable is None or abs(t.price - 0.5) < abs(tradeable.price - 0.5):
                        tradeable = t

            if tradeable:
                # Place limit order 1-2% below AMM price to capture spread
                bid_price = tradeable.price * 0.985
                if 0.05 < bid_price < 0.95:
                    return tradeable.token_id, "BUY", round(bid_price, 3)

        elif opp.edge_type.value == "volume_signal":
            # High volume — if near 50/50, buy the cheaper side
            for t in [yes_token, no_token]:
                if t and 0.3 < t.price < 0.7:
                    return t.token_id, "BUY", round(t.price * 0.99, 3)

        return "", "", 0

    def execute_signals(self, signals: list[TradeSignal]) -> list[dict]:
        """Execute a list of trade signals through risk checks and the trader."""
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
                    signal.token_id, signal.side, signal.price, signal.size
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
