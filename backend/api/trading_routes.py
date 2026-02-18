"""
Trading API — bot status, signals, and scan trigger.
"""

from fastapi import APIRouter
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
