"""
Trading API — multi-exchange bot status, signals, scan trigger, and config management.
Supports {exchange} path parameter for Polymarket and Kalshi.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/trading", tags=["trading"])

# Global bot references — set by main.py on startup
_bots: dict = {}

VALID_EXCHANGES = ["polymarket", "kalshi"]


def set_bot(exchange: str, bot):
    """Register a bot for an exchange."""
    _bots[exchange] = bot


def _get_bot(exchange: str):
    """Get bot for exchange, raise 404 if not found."""
    if exchange not in VALID_EXCHANGES:
        raise HTTPException(status_code=404, detail=f"Unknown exchange: {exchange}")
    bot = _bots.get(exchange)
    if bot is None:
        raise HTTPException(status_code=404, detail=f"{exchange} bot not initialized")
    return bot


# --- Exchange list ---

@trading_router.get("/exchanges")
async def list_exchanges():
    """List available exchanges and their status."""
    return {
        "exchanges": [
            {
                "id": ex,
                "name": ex.title(),
                "available": ex in _bots,
                "mode": _bots[ex].config.dry_run if ex in _bots else None,
            }
            for ex in VALID_EXCHANGES
        ]
    }


# --- Status / signals / scan ---

@trading_router.get("/{exchange}/status")
async def trading_status(exchange: str):
    """Bot mode, balance, risk metrics, signal count."""
    bot = _get_bot(exchange)
    status = bot.get_status()
    status["exchange"] = exchange
    return status


@trading_router.get("/{exchange}/signals")
async def trading_signals(exchange: str):
    """Recent trade signals with execution status."""
    bot = _get_bot(exchange)
    return list(reversed(bot.signal_history))


@trading_router.post("/{exchange}/scan")
async def trigger_scan(exchange: str):
    """Trigger a single scan cycle and return results."""
    bot = _get_bot(exchange)

    if bot._scanning:
        return {"error": "Scan already in progress"}

    logger.info(f"Manual scan triggered for {exchange} via API")
    results = bot.run_once()
    return {
        "status": "ok",
        "exchange": exchange,
        "results": results,
        "signal_count": len(results),
        "balance": bot.risk.paper_account.to_dict(),
    }


@trading_router.post("/{exchange}/reset")
async def reset_balance(exchange: str):
    """Reset paper account to starting balance and clear all state."""
    bot = _get_bot(exchange)

    starting = bot.risk.paper_account.starting_balance

    bot.risk.paper_account.balance = starting
    bot.risk.open_positions.clear()
    bot.risk.trades_today.clear()
    bot.risk._day_start_balance = starting
    bot.signal_history.clear()
    bot.balance_history.clear()
    bot.trade_history.clear()
    bot._cycles = 0

    logger.info("Paper account reset to $%.2f for %s", starting, exchange)
    return {"status": "ok", "balance": bot.risk.paper_account.to_dict()}


# --- Config endpoints ---

_CONFIG_FIELDS = [
    "dry_run", "max_position_size", "max_daily_loss", "max_total_exposure",
    "max_open_orders", "min_confidence", "min_expected_return", "min_liquidity",
    "scan_interval",
    # Execution controls
    "enabled_edge_types", "allowed_risk_levels",
    "price_aggressiveness", "min_price", "max_price", "sizing_mode",
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
    # Execution controls
    enabled_edge_types: Optional[List[str]] = None
    allowed_risk_levels: Optional[List[str]] = None
    price_aggressiveness: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sizing_mode: Optional[str] = None


@trading_router.get("/{exchange}/config")
async def get_config(exchange: str):
    """Return safe (non-secret) config fields."""
    bot = _get_bot(exchange)
    return {k: getattr(bot.config, k) for k in _CONFIG_FIELDS}


@trading_router.put("/{exchange}/config")
async def update_config(exchange: str, update: ConfigUpdate):
    """Partial update of config fields. Only provided fields change."""
    bot = _get_bot(exchange)

    changes = update.model_dump(exclude_none=True)
    for key, value in changes.items():
        if key in _CONFIG_FIELDS:
            old = getattr(bot.config, key)
            setattr(bot.config, key, value)
            logger.info(f"Config updated ({exchange}): {key} = {old} -> {value}")

    return {k: getattr(bot.config, k) for k in _CONFIG_FIELDS}


# --- Auto-scan endpoints ---

@trading_router.post("/{exchange}/auto-scan/start")
async def start_auto_scan(exchange: str):
    """Start automatic scanning on the configured interval."""
    bot = _get_bot(exchange)
    return bot.start_auto_scan()


@trading_router.post("/{exchange}/auto-scan/stop")
async def stop_auto_scan(exchange: str):
    """Stop automatic scanning."""
    bot = _get_bot(exchange)
    return bot.stop_auto_scan()


# --- Performance endpoints ---

@trading_router.get("/{exchange}/performance")
async def get_performance(exchange: str):
    """Get trade performance statistics."""
    bot = _get_bot(exchange)
    return bot.get_performance_stats()


@trading_router.get("/{exchange}/trades")
async def get_trade_history(exchange: str):
    """Get executed trade history (newest first)."""
    bot = _get_bot(exchange)
    return list(reversed(bot.trade_history))


@trading_router.get("/{exchange}/wallet")
async def get_wallet_balance(exchange: str):
    """Get real wallet balance."""
    bot = _get_bot(exchange)
    return bot._get_wallet_balance()
