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

LLM_TIMEOUT = 30  # seconds
LLM_MAX_RETRIES = 1


def _init_client():
    """Lazily initialize the Anthropic client."""
    global _client, _available
    if _client is not None:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.startswith("#"):
        logger.info("No ANTHROPIC_API_KEY set — LLM analysis disabled. "
                    "Set ANTHROPIC_API_KEY in .env to enable Claude-powered market analysis.")
        _available = False
        _client = False  # sentinel: attempted but unavailable
        return

    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key, timeout=LLM_TIMEOUT)
        _available = True
        logger.info("Anthropic client initialized — LLM analysis enabled")
    except ImportError:
        logger.warning("anthropic package not installed — run: pip install anthropic")
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


SYSTEM_PROMPT = """You are a calibrated prediction market analyst. Your job is to estimate the true probability of events.

CALIBRATION RULES (critical):
- Your probabilities must be well-calibrated: events you rate at 70% should resolve YES roughly 70% of the time.
- Consider base rates before adjusting. Most things don't happen — start from the outside view.
- Distinguish between "I have strong evidence" vs "I don't know." When you lack data, stay close to the market price.
- Never output extreme probabilities (< 5% or > 95%) unless the evidence is overwhelming.
- Your confidence score reflects DATA QUALITY, not conviction. High confidence = strong evidence. Low confidence = guessing.

CONFIDENCE GUIDELINES:
- 70-80%: Strong external data directly relevant to this question (e.g., official polling, live odds, on-chain data)
- 50-69%: Some relevant data but indirect or stale
- 30-49%: Weak data, mostly reasoning from priors
- 1-29%: No relevant data, pure speculation

OUTPUT: Respond with ONLY valid JSON (no markdown, no code fences)."""


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
    has_real_data = False
    for source, data in external_data.items():
        if data:
            data_section += f"\n**{source}:**\n{json.dumps(data, indent=2, default=str)}\n"
            has_real_data = True

    if not data_section:
        data_section = "\nNo external data available. Stay close to market price.\n"

    # Set confidence cap based on data availability
    max_confidence = 80 if has_real_data else 60

    prompt = f"""Analyze this prediction market:

**Market Question:** {question}
**Category:** {category}
**Current Polymarket Price:** {current_price:.1%} (this is what the market currently thinks)
{f"**Additional Context:** {market_context}" if market_context else ""}

**External Data:**{data_section}

Think step by step:
1. What is the base rate for this type of event?
2. What does the external data tell us (if any)?
3. Is the current market price too high, too low, or about right?
4. What's your estimated true probability?

Respond with ONLY valid JSON:
{{
  "probability": <float 0.05-0.95>,
  "confidence": <int 1-{max_confidence}, based on data quality NOT conviction>,
  "reasoning": "<2-3 sentence explanation starting with the key evidence>",
  "direction": "<buy_yes if probability > current price + 0.03, buy_no if probability < current price - 0.03, else hold>",
  "strength": "<strong if |edge| > 0.08, moderate if > 0.03, else weak>",
  "key_risks": ["<risk 1>", "<risk 2>"],
  "catalysts": ["<catalyst 1>", "<catalyst 2>"]
}}"""

    for attempt in range(1 + LLM_MAX_RETRIES):
        try:
            start = time.time()
            response = _client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            duration_ms = (time.time() - start) * 1000

            text = response.content[0].text.strip()

            # Parse JSON (handle potential markdown fences)
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)

            # Validate and clamp values
            result["probability"] = max(0.02, min(0.98, float(result.get("probability", current_price))))
            result["confidence"] = max(1, min(max_confidence, int(result.get("confidence", 50))))
            result["duration_ms"] = round(duration_ms, 1)
            result["source"] = "Claude"

            logger.info(
                f"LLM analysis ({duration_ms:.0f}ms): {question[:50]}... → "
                f"{result['probability']:.0%} ({result['direction']}, {result['confidence']}% conf)"
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON (attempt {attempt + 1}): {e}")
            if attempt < LLM_MAX_RETRIES:
                time.sleep(1)
                continue
            return None
        except Exception as e:
            logger.warning(f"LLM analysis failed (attempt {attempt + 1}): {e}")
            if attempt < LLM_MAX_RETRIES:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            return None

    return None
