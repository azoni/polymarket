"""
Trading configuration — all settings from environment variables.
DRY_RUN is True by default so nothing trades until you explicitly enable it.
"""

import os
from dataclasses import dataclass, field


@dataclass
class TradingConfig:
    # --- Polymarket CLOB credentials ---
    private_key: str = ""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    funder: str = ""  # proxy wallet funder address (optional)

    # --- Connection ---
    clob_host: str = "https://clob.polymarket.com"
    chain_id: int = 137  # Polygon mainnet

    # --- Risk limits ---
    max_position_size: float = 50.0    # max $ per position
    max_daily_loss: float = 25.0       # stop trading if daily loss exceeds this
    max_open_orders: int = 5           # max concurrent open orders
    max_total_exposure: float = 200.0  # max $ across all positions

    # --- Strategy thresholds ---
    min_confidence: float = 60.0       # min edge confidence (0-100)
    min_expected_return: float = 3.0   # min expected return %
    min_liquidity: float = 5000.0      # skip illiquid markets ($ liquidity)
    allowed_risk_levels: list = field(default_factory=lambda: ["low", "medium", "high"])

    # --- Bot behavior ---
    dry_run: bool = True               # paper trade by default
    scan_interval: int = 120           # seconds between scans
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "TradingConfig":
        return cls(
            private_key=os.getenv("POLY_PRIVATE_KEY", ""),
            api_key=os.getenv("POLY_API_KEY", ""),
            api_secret=os.getenv("POLY_API_SECRET", ""),
            api_passphrase=os.getenv("POLY_API_PASSPHRASE", ""),
            funder=os.getenv("POLY_FUNDER", ""),
            clob_host=os.getenv("POLY_CLOB_HOST", "https://clob.polymarket.com"),
            chain_id=int(os.getenv("POLY_CHAIN_ID", "137")),
            max_position_size=float(os.getenv("POLY_MAX_POSITION", "50")),
            max_daily_loss=float(os.getenv("POLY_MAX_DAILY_LOSS", "25")),
            max_open_orders=int(os.getenv("POLY_MAX_OPEN_ORDERS", "5")),
            max_total_exposure=float(os.getenv("POLY_MAX_EXPOSURE", "200")),
            min_confidence=float(os.getenv("POLY_MIN_CONFIDENCE", "60")),
            min_expected_return=float(os.getenv("POLY_MIN_RETURN", "3")),
            min_liquidity=float(os.getenv("POLY_MIN_LIQUIDITY", "5000")),
            dry_run=os.getenv("POLY_DRY_RUN", "true").lower() != "false",
            scan_interval=int(os.getenv("POLY_SCAN_INTERVAL", "120")),
            log_level=os.getenv("POLY_LOG_LEVEL", "INFO"),
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.private_key)

    @property
    def has_api_creds(self) -> bool:
        return all([self.api_key, self.api_secret, self.api_passphrase])


trading_config = TradingConfig.from_env()
