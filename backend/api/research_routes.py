"""
Research Agent Routes
=====================
API endpoints for research agent status, activity, and on-demand research.
"""

from fastapi import APIRouter, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

research_router = APIRouter(prefix="/agents", tags=["research"])

# Database reference (set from main.py via routes)
_db = None
_orchestrator = None


def set_research_deps(db, orchestrator):
    """Set database and orchestrator references."""
    global _db, _orchestrator
    _db = db
    _orchestrator = orchestrator


@research_router.get("/status")
async def get_agent_status():
    """Get status of all research agents."""
    agent_names = ["PoliticsAgent", "SportsAgent", "CryptoAgent", "EconomicsAgent", "GeneralAgent"]

    if not _db:
        return [
            {"name": name, "status": "unknown", "markets_analyzed": 0,
             "successes": 0, "failures": 0, "last_run": None}
            for name in agent_names
        ]

    stats = _db.get_agent_stats()
    stats_by_name = {s["agent_name"]: s for s in stats}

    result = []
    for name in agent_names:
        s = stats_by_name.get(name, {})
        total = s.get("total_actions", 0)
        successes = s.get("successes", 0)
        failures = s.get("failures", 0)
        success_rate = round(successes / total * 100, 1) if total > 0 else 0

        result.append({
            "name": name,
            "status": "online" if successes > 0 and success_rate > 50 else ("degraded" if total > 0 else "idle"),
            "markets_analyzed": s.get("markets_analyzed", 0),
            "successes": successes,
            "failures": failures,
            "success_rate": success_rate,
            "last_run": s.get("last_run"),
            "avg_duration_ms": round(s.get("avg_duration_ms", 0), 1),
        })

    return result


@research_router.get("/activity")
async def get_agent_activity(
    agent_name: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get recent agent activity log."""
    if not _db:
        return []
    return _db.get_agent_activity(agent_name=agent_name, limit=limit)


@research_router.post("/research/{market_id}")
async def research_single_market(market_id: str):
    """Trigger research for a single market and return prediction."""
    if not _db or not _orchestrator:
        return {"error": "Research system not initialized"}

    market = _db.get_market(market_id)
    if not market:
        return {"error": "Market not found"}

    prediction = _orchestrator.research_market(market)
    if prediction:
        _db.save_predictions([prediction])
        return prediction.model_dump()
    return {"error": "No prediction generated"}
