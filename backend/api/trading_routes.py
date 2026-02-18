"""
Trading API — bot status, signals, scan trigger, and config management.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/trading", tags=["trading"])

# Global bot reference — set by main.py on startup
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


@trading_router.get("/status")
async def trading_status():
    """Bot mode, balance, risk metrics, signal count."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}
    return _bot.get_status()


@trading_router.get("/signals")
async def trading_signals():
    """Recent trade signals with execution status."""
    if _bot is None:
        return []
    # Return newest first
    return list(reversed(_bot.signal_history))


@trading_router.post("/scan")
async def trigger_scan():
    """Trigger a single scan cycle and return results."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}

    if _bot._scanning:
        return {"error": "Scan already in progress"}

    logger.info("Manual scan triggered via API")
    results = _bot.run_once()
    return {
        "status": "ok",
        "results": results,
        "signal_count": len(results),
        "balance": _bot.risk.paper_account.to_dict(),
    }


@trading_router.post("/reset")
async def reset_balance():
    """Reset paper account to starting balance and clear all state."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}

    starting = _bot.risk.paper_account.starting_balance

    _bot.risk.paper_account.balance = starting
    _bot.risk.open_positions.clear()
    _bot.risk.trades_today.clear()
    _bot.risk._day_start_balance = starting
    _bot.signal_history.clear()
    _bot.balance_history.clear()
    _bot.trade_history.clear()
    _bot._cycles = 0

    logger.info("Paper account reset to $%.2f", starting)
    return {"status": "ok", "balance": _bot.risk.paper_account.to_dict()}


# --- Config endpoints ---

# Safe fields exposed to the UI (no secrets)
_CONFIG_FIELDS = [
    "dry_run", "max_position_size", "max_daily_loss", "max_total_exposure",
    "max_open_orders", "min_confidence", "min_expected_return", "min_liquidity",
    "scan_interval",
]


class ConfigUpdate(BaseModel):
    dry_run: Optional[bool] = None
    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_total_exposure: Optional[float] = None
    max_open_orders: Optional[int] = None
    min_confidence: Optional[float] = None
    min_expected_return: Optional[float] = None
    min_liquidity: Optional[float] = None
    scan_interval: Optional[int] = None


@trading_router.get("/config")
async def get_config():
    """Return safe (non-secret) config fields."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}
    return {k: getattr(_bot.config, k) for k in _CONFIG_FIELDS}


@trading_router.put("/config")
async def update_config(update: ConfigUpdate):
    """Partial update of config fields. Only provided fields change."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}

    changes = update.model_dump(exclude_none=True)
    for key, value in changes.items():
        if key in _CONFIG_FIELDS:
            old = getattr(_bot.config, key)
            setattr(_bot.config, key, value)
            logger.info(f"Config updated: {key} = {old} -> {value}")

    return {k: getattr(_bot.config, k) for k in _CONFIG_FIELDS}


# --- Auto-scan endpoints ---

@trading_router.post("/auto-scan/start")
async def start_auto_scan():
    """Start automatic scanning on the configured interval."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}
    return _bot.start_auto_scan()


@trading_router.post("/auto-scan/stop")
async def stop_auto_scan():
    """Stop automatic scanning."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}
    return _bot.stop_auto_scan()


# --- Performance endpoints ---

@trading_router.get("/performance")
async def get_performance():
    """Get trade performance statistics."""
    if _bot is None:
        return {"error": "Trading bot not initialized"}
    return _bot.get_performance_stats()


@trading_router.get("/trades")
async def get_trade_history():
    """Get executed trade history (newest first)."""
    if _bot is None:
        return []
    return list(reversed(_bot.trade_history))
