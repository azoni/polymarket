"""
Polymarket CLOB client wrapper.
Handles authentication, order placement, positions, and balances.
"""

import logging
from typing import Optional
from datetime import datetime

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType

from .config import TradingConfig, trading_config

logger = logging.getLogger(__name__)


class PolymarketTrader:
    """Wraps py-clob-client with error handling and dry-run support."""

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or trading_config
        self._client: Optional[ClobClient] = None
        self._authenticated = False

    # ==================== Auth ====================

    def connect(self) -> bool:
        """Initialize and authenticate the CLOB client."""
        if not self.config.has_credentials:
            logger.error("No private key configured. Set POLY_PRIVATE_KEY in .env")
            return False

        try:
            self._client = ClobClient(
                host=self.config.clob_host,
                key=self.config.private_key,
                chain_id=self.config.chain_id,
            )

            if self.config.funder:
                self._client.funder = self.config.funder

            # Use pre-derived API creds if available, otherwise derive them
            if self.config.has_api_creds:
                self._client.set_api_creds(ApiCreds(
                    api_key=self.config.api_key,
                    api_secret=self.config.api_secret,
                    api_passphrase=self.config.api_passphrase,
                ))
                logger.info("Using pre-configured API credentials")
            else:
                creds = self._client.derive_api_key()
                self._client.set_api_creds(creds)
                logger.info("Derived API credentials from private key")

            self._authenticated = True
            logger.info(f"Connected to Polymarket CLOB (chain {self.config.chain_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._authenticated = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._authenticated and self._client is not None

    def _require_connection(self):
        if not self.is_connected:
            raise RuntimeError("Not connected. Call connect() first.")

    # ==================== Market Data ====================

    def get_order_book(self, token_id: str) -> dict:
        """Get the order book for a token."""
        self._require_connection()
        try:
            return self._client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Failed to get order book for {token_id}: {e}")
            return {}

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get the midpoint price for a token."""
        self._require_connection()
        try:
            mid = self._client.get_midpoint(token_id)
            return float(mid) if mid else None
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
        Place a limit order.

        Args:
            token_id: The token to trade
            side: "BUY" or "SELL"
            price: Limit price (0-1)
            size: Number of shares
        """
        # Validate
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")
        if not 0 < price < 1:
            raise ValueError(f"Price must be between 0 and 1, got {price}")
        if size <= 0:
            raise ValueError(f"Size must be positive, got {size}")

        cost = price * size
        logger.info(f"{'[DRY RUN] ' if self.config.dry_run else ''}"
                     f"Placing {side} order: {size:.1f} shares @ ${price:.3f} "
                     f"(${cost:.2f}) token={token_id[:12]}...")

        if self.config.dry_run:
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
            order = self._client.create_order(OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
            ))
            result = self._client.post_order(order, OrderType.GTC)
            logger.info(f"Order placed: {result}")
            return result
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        self._require_connection()

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would cancel order {order_id}")
            return True

        try:
            self._client.cancel(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        self._require_connection()

        if self.config.dry_run:
            logger.info("[DRY RUN] Would cancel all orders")
            return True

        try:
            self._client.cancel_all()
            logger.info("Cancelled all open orders")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return False

    # ==================== Positions ====================

    def get_open_orders(self) -> list:
        """Get all open orders."""
        self._require_connection()
        try:
            return self._client.get_orders() or []
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    def get_trades(self) -> list:
        """Get recent trade history."""
        self._require_connection()
        try:
            return self._client.get_trades() or []
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []

    def get_balance(self) -> Optional[float]:
        """Get USDC balance on Polygon."""
        self._require_connection()
        try:
            bal = self._client.get_balance_allowance()
            if isinstance(bal, dict):
                return float(bal.get("balance", 0)) / 1e6  # USDC has 6 decimals
            return None
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
