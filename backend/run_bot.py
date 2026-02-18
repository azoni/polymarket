"""
CLI entry point for the Polymarket trading bot.

Usage:
    python run_bot.py              # Run in dry-run mode (default)
    python run_bot.py --live       # Run with real trades (requires credentials)
    python run_bot.py --once       # Single scan cycle then exit
"""

import argparse
import logging
import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from trading.config import TradingConfig
from trading.bot import TradingBot


def main():
    parser = argparse.ArgumentParser(description="Polymarket Trading Bot")
    parser.add_argument("--live", action="store_true", help="Enable live trading (default: dry run)")
    parser.add_argument("--once", action="store_true", help="Run one scan cycle and exit")
    parser.add_argument("--interval", type=int, default=None, help="Scan interval in seconds")
    parser.add_argument("--max-position", type=float, default=None, help="Max $ per position")
    parser.add_argument("--max-loss", type=float, default=None, help="Max daily loss $")
    parser.add_argument("--min-confidence", type=float, default=None, help="Min confidence threshold (0-100)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    # Logging setup
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Build config from env, then override with CLI args
    config = TradingConfig.from_env()

    if args.live:
        config.dry_run = False
    if args.interval:
        config.scan_interval = args.interval
    if args.max_position:
        config.max_position_size = args.max_position
    if args.max_loss:
        config.max_daily_loss = args.max_loss
    if args.min_confidence:
        config.min_confidence = args.min_confidence

    # Safety check for live mode
    if not config.dry_run:
        if not config.has_credentials:
            print("ERROR: Live trading requires POLY_PRIVATE_KEY in .env")
            sys.exit(1)
        print("\n  *** LIVE TRADING MODE ***")
        print(f"  Max position: ${config.max_position_size}")
        print(f"  Max daily loss: ${config.max_daily_loss}")
        print(f"  Max exposure: ${config.max_total_exposure}")
        confirm = input("\n  Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            sys.exit(0)

    bot = TradingBot(config)

    if args.once:
        results = bot.run_once()
        for r in results:
            status = r["status"]
            sig = r.get("signal", {})
            print(f"  [{status.upper()}] {sig.get('side', '?')} {sig.get('size', 0)} "
                  f"@ ${sig.get('price', 0):.3f} | {sig.get('market_question', '?')}")
        if not results:
            print("  No trade signals found.")
    else:
        bot.start()


if __name__ == "__main__":
    main()
