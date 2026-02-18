"""
Trading bot — main loop that scans, evaluates, and trades on a schedule.
"""

import time
import signal
import logging
import threading
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
        self.balance_history: list[dict] = []  # balance snapshots for P&L chart
        self.trade_history: list[dict] = []    # all executed trades (cap 500)
        self._last_scan_at: str = ""
        self._auto_scan = False
        self._auto_scan_thread: threading.Thread | None = None

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
                    "reasoning": sig.reasoning,
                    "risk_level": sig.risk_level,
                    "suggested_action": sig.suggested_action,
                    "market_id": sig.market_id,
                    "description": sig.description,
                    "status": results[i]["status"] if i < len(results) else "unknown",
                    "reason": results[i].get("reason", "") if i < len(results) else "",
                }
                self.signal_history.append(entry)

            # Cap at 100
            if len(self.signal_history) > 100:
                self.signal_history = self.signal_history[-100:]

            # Record executed trades for performance tracking
            for i, sig in enumerate(signals):
                status = results[i]["status"] if i < len(results) else "unknown"
                if status in ("executed", "dry_run"):
                    cost = sig.price * sig.size
                    self.trade_history.append({
                        "timestamp": self._last_scan_at,
                        "market": sig.market_question,
                        "side": sig.side,
                        "entry_price": sig.price,
                        "size": sig.size,
                        "cost": round(cost, 2),
                        "edge_type": sig.edge_type,
                        "confidence": sig.confidence,
                        "expected_return": sig.expected_return,
                        "token_id": sig.token_id,
                    })
            if len(self.trade_history) > 500:
                self.trade_history = self.trade_history[-500:]

            # Snapshot balance for P&L chart
            pa = self.risk.paper_account
            self.balance_history.append({
                "timestamp": self._last_scan_at,
                "balance": round(pa.balance, 2),
                "pnl": round(pa.pnl, 2),
            })
            if len(self.balance_history) > 500:
                self.balance_history = self.balance_history[-500:]

            return results
        finally:
            self._scanning = False

    def start_auto_scan(self) -> dict:
        """Start automatic scanning on config.scan_interval."""
        if self._auto_scan:
            return {"status": "already_running", "interval": self.config.scan_interval}
        self._auto_scan = True
        self._auto_scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
        self._auto_scan_thread.start()
        logger.info(f"Auto-scan started (interval: {self.config.scan_interval}s)")
        return {"status": "started", "interval": self.config.scan_interval}

    def stop_auto_scan(self) -> dict:
        """Stop automatic scanning."""
        if not self._auto_scan:
            return {"status": "already_stopped"}
        self._auto_scan = False
        logger.info("Auto-scan stopped")
        return {"status": "stopped"}

    def _auto_scan_loop(self):
        """Background loop that calls run_once() on interval."""
        while self._auto_scan:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Auto-scan cycle error: {e}", exc_info=True)
            # Sleep in 1-second increments so stop is responsive
            for _ in range(self.config.scan_interval):
                if not self._auto_scan:
                    break
                time.sleep(1)

    def get_performance_stats(self) -> dict:
        """Compute performance statistics from trade history."""
        if not self.trade_history:
            return {
                "total_trades": 0, "avg_confidence": 0,
                "total_cost": 0, "by_edge_type": {},
                "pnl": round(self.risk.paper_account.pnl, 2),
            }
        total = len(self.trade_history)
        total_cost = sum(t["cost"] for t in self.trade_history)
        avg_confidence = sum(t["confidence"] for t in self.trade_history) / total

        by_edge: dict = {}
        for t in self.trade_history:
            et = t["edge_type"]
            if et not in by_edge:
                by_edge[et] = {"count": 0, "total_cost": 0, "confidences": []}
            by_edge[et]["count"] += 1
            by_edge[et]["total_cost"] += t["cost"]
            by_edge[et]["confidences"].append(t["confidence"])

        for data in by_edge.values():
            data["avg_confidence"] = round(sum(data["confidences"]) / len(data["confidences"]), 1)
            data["total_cost"] = round(data["total_cost"], 2)
            del data["confidences"]

        return {
            "total_trades": total,
            "total_cost": round(total_cost, 2),
            "avg_confidence": round(avg_confidence, 1),
            "by_edge_type": by_edge,
            "pnl": round(self.risk.paper_account.pnl, 2),
        }

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
            "balance_history": self.balance_history,
            "auto_scan": self._auto_scan,
            "performance": self.get_performance_stats(),
        }
