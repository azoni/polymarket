"""
LLM Client
===========
Claude-powered market analysis for research agents.
Falls back gracefully when ANTHROPIC_API_KEY is not set.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_client = None
_available = False


def _init_client():
    """Lazily initialize the Anthropic client."""
    global _client, _available
    if _client is not None:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.startswith("#"):
        logger.info("No ANTHROPIC_API_KEY set — LLM analysis disabled")
        _available = False
        _client = False  # sentinel: attempted but unavailable
        return

    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)
        _available = True
        logger.info("Anthropic client initialized — LLM analysis enabled")
    except ImportError:
        logger.warning("anthropic package not installed — LLM analysis disabled")
        _available = False
        _client = False
    except Exception as e:
        logger.warning(f"Failed to initialize Anthropic client: {e}")
        _available = False
        _client = False


def is_available() -> bool:
    """Check if LLM analysis is available."""
    _init_client()
    return _available


def analyze_market(
    question: str,
    category: str,
    current_price: float,
    external_data: Dict[str, Any],
    market_context: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Ask Claude to analyze a prediction market and estimate probability.

    Returns dict with: probability, confidence, reasoning, direction,
    key_risks, catalysts — or None if unavailable/failed.
    """
    _init_client()
    if not _available:
        return None

    # Build the prompt with all available data
    data_section = ""
    for source, data in external_data.items():
        if data:
            data_section += f"\n**{source}:**\n{json.dumps(data, indent=2, default=str)}\n"

    if not data_section:
        data_section = "\nNo external data available.\n"

    prompt = f"""You are an expert prediction market analyst. Analyze this market and estimate the true probability.

**Market Question:** {question}
**Category:** {category}
**Current Polymarket Price:** {current_price:.1%} (this is what the market currently thinks)
{f"**Additional Context:** {market_context}" if market_context else ""}

**External Data:**{data_section}

Based on all available information, provide your analysis. Think step by step:
1. What does the external data tell us?
2. Is the current market price too high, too low, or about right?
3. What's your estimated true probability?

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "probability": <float 0.01-0.99>,
  "confidence": <int 1-95, how confident you are in your estimate>,
  "reasoning": "<2-3 sentence explanation>",
  "direction": "<buy_yes if probability > current price + 0.03, buy_no if probability < current price - 0.03, else hold>",
  "strength": "<strong if |edge| > 0.08, moderate if > 0.03, else weak>",
  "key_risks": ["<risk 1>", "<risk 2>"],
  "catalysts": ["<catalyst 1>", "<catalyst 2>"]
}}"""

    try:
        start = time.time()
        response = _client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        duration_ms = (time.time() - start) * 1000

        text = response.content[0].text.strip()

        # Parse JSON (handle potential markdown fences)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)

        # Validate and clamp values
        result["probability"] = max(0.01, min(0.99, float(result.get("probability", current_price))))
        result["confidence"] = max(1, min(95, int(result.get("confidence", 50))))
        result["duration_ms"] = round(duration_ms, 1)
        result["source"] = "Claude"

        logger.info(
            f"LLM analysis ({duration_ms:.0f}ms): {question[:50]}... → "
            f"{result['probability']:.0%} ({result['direction']}, {result['confidence']}% conf)"
        )
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM analysis failed: {e}")
        return None
