"""
Kalshi CLOB client wrapper.
Mirrors PolymarketTrader interface for exchange-agnostic bot usage.
Uses kalshi-python SDK when credentials are available, pure paper mode otherwise.
"""

import logging
from typing import Optional
from datetime import datetime

from .config import KalshiConfig, kalshi_config

logger = logging.getLogger(__name__)


class KalshiTrader:
    """Wraps kalshi-python SDK with the same interface as PolymarketTrader."""

    def __init__(self, config: Optional[KalshiConfig] = None):
        self.config = config or kalshi_config
        self._client = None
        self._authenticated = False

    # ==================== Auth ====================

    def connect(self) -> bool:
        """Initialize and authenticate the Kalshi client."""
        if not self.config.has_credentials:
            if self.config.dry_run:
                logger.warning("No Kalshi credentials — running in pure paper mode")
                self._authenticated = False
                return True  # paper mode is fine without creds
            logger.error("No Kalshi credentials configured. Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH")
            return False

        try:
            from kalshi import ExchangeClient

            # Demo vs production
            if self.config.dry_run:
                host = "https://demo-api.kalshi.co/trade-api/v2"
            else:
                host = "https://trading-api.kalshi.com/trade-api/v2"

            # Read private key
            with open(self.config.private_key_path, "r") as f:
                private_key = f.read()

            self._client = ExchangeClient(
                exchange_api_base=host,
                key_id=self.config.api_key_id,
                private_key=private_key,
            )

            # Test connection by fetching balance
            self._client.get_balance()
            self._authenticated = True
            mode = "demo" if self.config.dry_run else "production"
            logger.info(f"Connected to Kalshi ({mode})")
            return True

        except ImportError:
            logger.warning("kalshi-python package not installed — paper mode only")
            self._authenticated = False
            return self.config.dry_run
        except FileNotFoundError:
            logger.error(f"Private key file not found: {self.config.private_key_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Kalshi: {e}")
            self._authenticated = False
            return self.config.dry_run

    @property
    def is_connected(self) -> bool:
        return self._authenticated and self._client is not None

    def _require_connection(self):
        if not self.is_connected:
            raise RuntimeError("Not connected to Kalshi. Call connect() first.")

    # ==================== Market Data ====================

    def get_order_book(self, token_id: str) -> dict:
        """Get the order book for a market ticker. Normalizes cents to 0-1."""
        if not self.is_connected:
            return {}
        try:
            book = self._client.get_orderbook(ticker=token_id)
            # Normalize cents to 0-1
            result = {"bids": [], "asks": []}
            for bid in book.get("orderbook", {}).get("yes", []):
                result["bids"].append({
                    "price": bid[0] / 100,
                    "size": bid[1],
                })
            for ask in book.get("orderbook", {}).get("no", []):
                result["asks"].append({
                    "price": 1 - ask[0] / 100,  # no price complement
                    "size": ask[1],
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get order book for {token_id}: {e}")
            return {}

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get the midpoint price for a market ticker (0-1 scale)."""
        if not self.is_connected:
            return None
        try:
            market = self._client.get_market(ticker=token_id)
            yes_bid = market.get("market", {}).get("yes_bid", 0)
            yes_ask = market.get("market", {}).get("yes_ask", 0)
            if yes_bid and yes_ask:
                return (yes_bid + yes_ask) / 200  # cents to 0-1
            last = market.get("market", {}).get("last_price", 50)
            return last / 100
        except Exception as e:
            logger.error(f"Failed to get midpoint for {token_id}: {e}")
            return None

    # ==================== Orders ====================

    def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
    ) -> Optional[dict]:
        """
        Place a limit order on Kalshi.

        Args:
            token_id: Kalshi market ticker
            side: "BUY" or "SELL"
            price: Limit price (0-1), converted to cents internally
            size: Number of contracts
        """
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")
        if not 0 < price < 1:
            raise ValueError(f"Price must be between 0 and 1, got {price}")
        if size <= 0:
            raise ValueError(f"Size must be positive, got {size}")

        cents_price = int(round(price * 100))
        cents_price = max(1, min(99, cents_price))
        cost = price * size

        logger.info(f"{'[DRY RUN] ' if self.config.dry_run else ''}"
                     f"Placing {side} order: {size:.0f} contracts @ {cents_price}c "
                     f"(${cost:.2f}) ticker={token_id}")

        if self.config.dry_run and not self.is_connected:
            return {
                "dry_run": True,
                "side": side,
                "price": price,
                "size": size,
                "cost": cost,
                "token_id": token_id,
                "timestamp": datetime.now().isoformat(),
            }

        self._require_connection()
        try:
            # Kalshi SDK: side is "yes" or "no", action is "buy" or "sell"
            kalshi_side = "yes"
            kalshi_action = side.lower()

            order = self._client.create_order(
                ticker=token_id,
                action=kalshi_action,
                side=kalshi_side,
                type="limit",
                yes_price=cents_price,
                count=int(size),
            )
            logger.info(f"Order placed on Kalshi: {order}")
            return order
        except Exception as e:
            logger.error(f"Kalshi order failed: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self.config.dry_run and not self.is_connected:
            logger.info(f"[DRY RUN] Would cancel Kalshi order {order_id}")
            return True

        self._require_connection()
        try:
            self._client.cancel_order(order_id=order_id)
            logger.info(f"Cancelled Kalshi order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Kalshi order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if self.config.dry_run and not self.is_connected:
            logger.info("[DRY RUN] Would cancel all Kalshi orders")
            return True

        self._require_connection()
        try:
            orders = self._client.get_orders(status="resting")
            for order in orders.get("orders", []):
                self._client.cancel_order(order_id=order["order_id"])
            logger.info("Cancelled all Kalshi open orders")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel all Kalshi orders: {e}")
            return False

    # ==================== Positions ====================

    def get_open_orders(self) -> list:
        """Get all open orders."""
        if not self.is_connected:
            return []
        try:
            result = self._client.get_orders(status="resting")
            return result.get("orders", [])
        except Exception as e:
            logger.error(f"Failed to get Kalshi open orders: {e}")
            return []

    def get_trades(self) -> list:
        """Get recent trade history."""
        if not self.is_connected:
            return []
        try:
            result = self._client.get_fills()
            return result.get("fills", [])
        except Exception as e:
            logger.error(f"Failed to get Kalshi trades: {e}")
            return []

    def get_balance(self) -> Optional[float]:
        """Get account balance in dollars."""
        if not self.is_connected:
            return None
        try:
            result = self._client.get_balance()
            # Kalshi returns balance in cents
            balance_cents = result.get("balance", 0)
            return balance_cents / 100
        except Exception as e:
            logger.error(f"Failed to get Kalshi balance: {e}")
            return None
