"""
Data Models
===========
Pydantic models for type safety and API serialization.
Pydantic v2 compatible.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MarketCategory(str, Enum):
    """Market categories for filtering and agent routing."""
    POLITICS = "politics"
    SPORTS = "sports"
    CRYPTO = "crypto"
    ECONOMICS = "economics"
    ENTERTAINMENT = "entertainment"
    SCIENCE = "science"
    OTHER = "other"


class EdgeType(str, Enum):
    """Types of trading edges we can detect."""
    ARBITRAGE = "arbitrage"
    MISPRICING = "mispricing"
    CORRELATION = "correlation"
    VOLUME_SIGNAL = "volume_signal"
    LIQUIDITY_GAP = "liquidity_gap"


class Token(BaseModel):
    """A single outcome token in a market."""
    token_id: str
    outcome: str
    price: float
    best_bid: float = 0.0
    best_ask: float = 0.0


class Market(BaseModel):
    """Complete market data structure."""
    market_id: str
    condition_id: str = ""
    question: str
    description: str = ""
    
    # Categorization
    category: MarketCategory = MarketCategory.OTHER
    tags: List[str] = Field(default_factory=list)
    
    # Pricing
    current_price: float = 0.5
    spread_pct: float = 0.0
    
    # Volume & Liquidity
    volume_24h: float = 0.0
    liquidity: float = 0.0
    
    # Timing
    end_date: Optional[str] = None
    days_until_resolution: Optional[int] = None
    
    # Scores (0-100)
    edge_score: float = 0.0
    liquidity_score: float = 0.0
    efficiency_score: float = 0.0
    researchability_score: float = 0.0
    
    # Tokens
    tokens: List[Token] = Field(default_factory=list)
    
    # Links
    polymarket_url: str = ""


class EdgeOpportunity(BaseModel):
    """A detected edge/trading opportunity."""
    id: str = ""
    edge_type: EdgeType
    description: str
    confidence: float  # 0-100
    expected_return: float  # percentage
    risk_level: str  # low, medium, high
    
    # Market info
    market_id: str
    market_question: str
    
    # Trade suggestion
    suggested_action: str = ""
    reasoning: str = ""
    
    # Metadata
    detected_at: datetime = Field(default_factory=datetime.now)


class Prediction(BaseModel):
    """Research agent prediction for a market."""
    market_id: str
    market_question: str
    
    # Prediction
    predicted_probability: float
    current_price: float
    edge: float  # predicted - current
    
    # Confidence
    confidence: float  # 0-100
    confidence_low: float = 0.0
    confidence_high: float = 1.0
    
    # Direction
    direction: str  # buy_yes, buy_no, hold
    strength: str  # strong, moderate, weak
    
    # Analysis
    reasoning: str = ""
    key_risks: List[str] = Field(default_factory=list)
    catalysts: List[str] = Field(default_factory=list)
    
    # Agent info
    agent_name: str = ""


class DashboardStats(BaseModel):
    """Summary stats for the dashboard."""
    total_markets: int = 0
    total_opportunities: int = 0
    high_confidence_opps: int = 0
    total_predictions: int = 0
    markets_by_category: Dict[str, Any] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None