"""
Trading bot — main loop that scans, evaluates, and trades on a schedule.
"""

import time
import signal
import logging
from datetime import datetime

from .config import TradingConfig, trading_config
from .client import PolymarketTrader
from .risk import RiskManager
from .strategy import TradingStrategy

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Autonomous trading bot that:
    1. Connects to Polymarket CLOB
    2. Scans markets on an interval
    3. Runs edge detection
    4. Executes qualifying trades through risk management
    """

    def __init__(self, config: TradingConfig = None):
        self.config = config or trading_config
        self.trader = PolymarketTrader(self.config)
        self.risk = RiskManager(self.config)
        self.strategy = TradingStrategy(self.trader, self.risk, self.config)
        self._running = False
        self._cycles = 0
        self._scanning = False
        self.signal_history: list[dict] = []  # last 100 signal results
        self._last_scan_at: str = ""

    def start(self):
        """Start the bot loop."""
        mode = "DRY RUN" if self.config.dry_run else "LIVE"
        logger.info(f"Starting Polymarket Trading Bot [{mode}]")
        logger.info(f"  Max position: ${self.config.max_position_size}")
        logger.info(f"  Max daily loss: ${self.config.max_daily_loss}")
        logger.info(f"  Max exposure: ${self.config.max_total_exposure}")
        logger.info(f"  Min confidence: {self.config.min_confidence}%")
        logger.info(f"  Scan interval: {self.config.scan_interval}s")

        # Connect to CLOB (skip in dry run if no credentials)
        if self.config.has_credentials:
            if not self.trader.connect():
                logger.error("Failed to connect to Polymarket CLOB. Exiting.")
                return
        elif not self.config.dry_run:
            logger.error("No credentials configured and not in dry run mode. Exiting.")
            return
        else:
            logger.warning("No credentials — running in DRY RUN mode (paper trading)")

        # Handle graceful shutdown
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info("Bot is live. Press Ctrl+C to stop.")
        self._run_loop()

    def _run_loop(self):
        """Main scan-and-trade loop."""
        while self._running:
            self._cycles += 1
            logger.info(f"\n{'='*50}")
            logger.info(f"Cycle #{self._cycles} | {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"{'='*50}")

            try:
                # Scan for opportunities
                signals = self.strategy.scan()

                if signals:
                    logger.info(f"Found {len(signals)} actionable signals:")
                    for s in signals:
                        logger.info(f"  {s.side} {s.size} @ ${s.price:.3f} | "
                                   f"{s.edge_type} ({s.confidence:.0f}% conf, "
                                   f"{s.expected_return:.1f}% EV) | {s.market_question}")

                    # Execute through risk management
                    results = self.strategy.execute_signals(signals)

                    executed = sum(1 for r in results if r["status"] in ("executed", "dry_run"))
                    blocked = sum(1 for r in results if r["status"] == "blocked")
                    failed = sum(1 for r in results if r["status"] == "failed")

                    logger.info(f"Results: {executed} executed, {blocked} blocked, {failed} failed")
                else:
                    logger.info("No actionable signals this cycle")

                # Log risk status
                risk_status = self.risk.get_status()
                logger.info(f"Risk: PnL ${risk_status['daily_pnl']:.2f} | "
                           f"Exposure ${risk_status['total_exposure']:.2f}/"
                           f"${risk_status['max_exposure']} | "
                           f"Positions {risk_status['open_positions']}/"
                           f"{risk_status['max_positions']}")

            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)

            # Sleep until next scan
            if self._running:
                logger.info(f"Next scan in {self.config.scan_interval}s...")
                time.sleep(self.config.scan_interval)

        logger.info("Bot stopped.")

    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown on Ctrl+C or SIGTERM."""
        logger.info("\nShutdown signal received. Finishing current cycle...")
        self._running = False

    def run_once(self) -> list[dict]:
        """Run a single scan cycle (useful for testing / API trigger)."""
        if self.config.has_credentials and not self.trader.is_connected:
            self.trader.connect()

        self._scanning = True
        self._cycles += 1
        self._last_scan_at = datetime.now().isoformat()

        try:
            signals = self.strategy.scan()
            results = self.strategy.execute_signals(signals) if signals else []

            # Store signal history (capped at 100)
            for i, sig in enumerate(signals):
                entry = {
                    "timestamp": self._last_scan_at,
                    "cycle": self._cycles,
                    "market": sig.market_question,
                    "side": sig.side,
                    "price": sig.price,
                    "size": sig.size,
                    "edge_type": sig.edge_type,
                    "confidence": sig.confidence,
                    "expected_return": sig.expected_return,
                    "status": results[i]["status"] if i < len(results) else "unknown",
                    "reason": results[i].get("reason", "") if i < len(results) else "",
                }
                self.signal_history.append(entry)

            # Cap at 100
            if len(self.signal_history) > 100:
                self.signal_history = self.signal_history[-100:]

            return results
        finally:
            self._scanning = False

    def get_status(self) -> dict:
        """Get current bot status for the dashboard."""
        risk = self.risk.get_status()
        return {
            "running": self._running,
            "scanning": self._scanning,
            "mode": "paper" if self.config.dry_run else "live",
            "cycles": self._cycles,
            "connected": self.trader.is_connected,
            "last_scan_at": self._last_scan_at,
            "signal_count": len(self.signal_history),
            "balance": self.risk.paper_account.to_dict(),
            "risk": risk,
        }
