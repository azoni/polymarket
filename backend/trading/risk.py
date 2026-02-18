"""
Risk management — guards against overexposure and runaway losses.
Every trade must pass through RiskManager before execution.
"""

import logging
from datetime import datetime, date
from dataclasses import dataclass, field

from .config import TradingConfig, trading_config

logger = logging.getLogger(__name__)

PAPER_STARTING_BALANCE = 10_000.0


class PaperAccount:
    """Simulated account for paper trading. Starts at $10k."""

    def __init__(self, starting_balance: float = PAPER_STARTING_BALANCE):
        self.starting_balance = starting_balance
        self.balance = starting_balance

    def deduct(self, amount: float):
        self.balance -= amount

    def credit(self, amount: float):
        self.balance += amount

    @property
    def pnl(self) -> float:
        return self.balance - self.starting_balance

    def to_dict(self) -> dict:
        return {
            "balance": round(self.balance, 2),
            "starting_balance": self.starting_balance,
            "pnl": round(self.pnl, 2),
        }


@dataclass
class TradeRecord:
    """A completed or attempted trade."""
    timestamp: datetime
    token_id: str
    side: str
    price: float
    size: float
    pnl: float = 0.0  # realized P&L (filled after resolution)


class RiskManager:
    """Enforces position limits, daily loss limits, and exposure caps."""

    def __init__(self, config: TradingConfig = None):
        self.config = config or trading_config
        self.trades_today: list[TradeRecord] = []
        self.open_positions: dict[str, float] = {}  # token_id -> $ exposure
        self._current_date: date = date.today()
        self.paper_account = PaperAccount()
        self._day_start_balance: float = self.paper_account.balance

    def _reset_daily(self):
        """Reset daily counters if the date has changed."""
        today = date.today()
        if today != self._current_date:
            logger.info(f"New trading day: {today}. Resetting daily counters.")
            self.trades_today.clear()
            self._day_start_balance = self.paper_account.balance
            self._current_date = today

    @property
    def daily_pnl(self) -> float:
        """Today's P&L based on paper account balance delta."""
        self._reset_daily()
        return self.paper_account.balance - self._day_start_balance

    @property
    def total_exposure(self) -> float:
        """Total $ across all open positions."""
        return sum(abs(v) for v in self.open_positions.values())

    @property
    def open_order_count(self) -> int:
        return len(self.open_positions)

    def check_trade(self, token_id: str, side: str, price: float, size: float) -> tuple[bool, str]:
        """
        Check if a trade passes all risk checks.
        Returns (allowed, reason).
        """
        self._reset_daily()
        cost = price * size

        # 1. Daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            return False, f"Daily loss limit hit (${self.daily_pnl:.2f} / -${self.config.max_daily_loss:.2f})"

        # 2. Position size limit
        if cost > self.config.max_position_size:
            return False, f"Position too large (${cost:.2f} > ${self.config.max_position_size:.2f})"

        # 3. Max open orders
        if token_id not in self.open_positions and self.open_order_count >= self.config.max_open_orders:
            return False, f"Too many open positions ({self.open_order_count} / {self.config.max_open_orders})"

        # 4. Total exposure
        new_exposure = self.total_exposure + cost
        if new_exposure > self.config.max_total_exposure:
            return False, f"Total exposure exceeded (${new_exposure:.2f} > ${self.config.max_total_exposure:.2f})"

        # 5. No doubling down on existing position without headroom
        if token_id in self.open_positions:
            existing = self.open_positions[token_id]
            if existing + cost > self.config.max_position_size:
                return False, f"Would exceed position limit on this token (${existing + cost:.2f})"

        return True, "OK"

    def record_trade(self, token_id: str, side: str, price: float, size: float):
        """Record a trade that was executed."""
        self._reset_daily()
        cost = price * size

        self.trades_today.append(TradeRecord(
            timestamp=datetime.now(),
            token_id=token_id,
            side=side,
            price=price,
            size=size,
        ))

        if side == "BUY":
            self.open_positions[token_id] = self.open_positions.get(token_id, 0) + cost
            self.paper_account.deduct(cost)
        elif side == "SELL":
            self.open_positions[token_id] = self.open_positions.get(token_id, 0) - cost
            self.paper_account.credit(cost)
            if self.open_positions.get(token_id, 0) <= 0:
                self.open_positions.pop(token_id, None)

        logger.info(f"Recorded {side} {size:.1f} @ ${price:.3f} = ${cost:.2f}. "
                     f"Exposure: ${self.total_exposure:.2f}, Open: {self.open_order_count}")

    def get_status(self) -> dict:
        """Current risk status for dashboard/logging."""
        self._reset_daily()
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_limit": self.config.max_daily_loss,
            "total_exposure": round(self.total_exposure, 2),
            "max_exposure": self.config.max_total_exposure,
            "open_positions": self.open_order_count,
            "max_positions": self.config.max_open_orders,
            "trades_today": len(self.trades_today),
            "position_details": {k: round(v, 2) for k, v in self.open_positions.items()},
        }
