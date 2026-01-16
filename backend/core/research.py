"""
Research Agents
===============
Category-specific agents that analyze markets and produce predictions.
Currently uses heuristics - designed to be extended with real data sources.
"""

from typing import List, Optional
from abc import ABC, abstractmethod
import logging

from .models import Market, Prediction, MarketCategory

logger = logging.getLogger(__name__)


# =============================================================================
# BASE AGENT
# =============================================================================

class ResearchAgent(ABC):
    """Base class for research agents."""
    
    def __init__(self, name: str, categories: List[MarketCategory]):
        self.name = name
        self.categories = categories
    
    @abstractmethod
    def can_analyze(self, market: Market) -> bool:
        """Check if this agent can analyze the market."""
        pass
    
    @abstractmethod
    def analyze(self, market: Market) -> Prediction:
        """Analyze market and produce prediction."""
        pass
    
    def research(self, market: Market) -> Optional[Prediction]:
        """Full research pipeline."""
        if not self.can_analyze(market):
            return None
        
        prediction = self.analyze(market)
        prediction.agent_name = self.name
        return prediction


# =============================================================================
# CATEGORY AGENTS
# =============================================================================

class PoliticsAgent(ResearchAgent):
    """
    Agent for political markets.
    
    Data sources (to implement):
    - Polling aggregators (538, RCP)
    - Prediction market comparisons
    - News sentiment
    """
    
    KEYWORDS = ["election", "president", "senate", "congress", "trump", "biden", 
                "republican", "democrat", "governor", "vote"]
    
    def __init__(self):
        super().__init__("PoliticsAgent", [MarketCategory.POLITICS])
    
    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.POLITICS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)
    
    def analyze(self, market: Market) -> Prediction:
        # Placeholder: In production, fetch polls and expert forecasts
        # For now, use market price with slight mean reversion assumption
        
        current = market.current_price
        predicted = current + (0.03 * (0.5 - current))  # Slight mean reversion
        edge = predicted - current
        
        if abs(edge) < 0.02:
            direction, strength = "hold", "weak"
        elif edge > 0:
            direction = "buy_yes"
            strength = "strong" if edge > 0.1 else "moderate"
        else:
            direction = "buy_no"
            strength = "strong" if edge < -0.1 else "moderate"
        
        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=predicted,
            current_price=current,
            edge=edge,
            confidence=50,  # Low without real data
            confidence_low=max(0, predicted - 0.15),
            confidence_high=min(1, predicted + 0.15),
            direction=direction,
            strength=strength,
            reasoning="Placeholder analysis. Would use polling data, historical patterns, and expert forecasts.",
            key_risks=["Polling error", "Late-breaking news", "Turnout uncertainty"],
            catalysts=["Debates", "Major endorsements", "News events"]
        )


class SportsAgent(ResearchAgent):
    """
    Agent for sports markets.
    
    Data sources (to implement):
    - Team/player statistics
    - Injury reports
    - Vegas lines comparison
    """
    
    KEYWORDS = ["nfl", "nba", "mlb", "nhl", "super bowl", "championship", 
                "playoffs", "finals", "game", "match", "win"]
    
    def __init__(self):
        super().__init__("SportsAgent", [MarketCategory.SPORTS])
    
    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.SPORTS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)
    
    def analyze(self, market: Market) -> Prediction:
        current = market.current_price
        
        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=current,
            current_price=current,
            edge=0,
            confidence=40,
            confidence_low=max(0, current - 0.2),
            confidence_high=min(1, current + 0.2),
            direction="hold",
            strength="weak",
            reasoning="Would use team statistics, injury reports, and Vegas lines.",
            key_risks=["Injuries", "Weather", "Unexpected events"],
            catalysts=["Injury updates", "Lineup announcements"]
        )


class CryptoAgent(ResearchAgent):
    """
    Agent for crypto markets.
    
    Data sources (to implement):
    - On-chain analytics
    - Price data
    - Sentiment indicators
    """
    
    KEYWORDS = ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", 
                "sol", "token", "halving"]
    
    def __init__(self):
        super().__init__("CryptoAgent", [MarketCategory.CRYPTO])
    
    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.CRYPTO:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)
    
    def analyze(self, market: Market) -> Prediction:
        current = market.current_price
        
        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=current,
            current_price=current,
            edge=0,
            confidence=35,
            confidence_low=max(0, current - 0.25),
            confidence_high=min(1, current + 0.25),
            direction="hold",
            strength="weak",
            reasoning="Would use price technicals, on-chain metrics, and sentiment.",
            key_risks=["Volatility", "Regulatory news", "Market manipulation"],
            catalysts=["ETF decisions", "Protocol upgrades", "Macro events"]
        )


class EconomicsAgent(ResearchAgent):
    """
    Agent for economics markets.
    
    Data sources (to implement):
    - FRED data
    - Fed communications
    - Futures markets
    """
    
    KEYWORDS = ["fed", "interest rate", "inflation", "gdp", "unemployment", 
                "recession", "cpi", "fomc"]
    
    def __init__(self):
        super().__init__("EconomicsAgent", [MarketCategory.ECONOMICS])
    
    def can_analyze(self, market: Market) -> bool:
        if market.category == MarketCategory.ECONOMICS:
            return True
        q = market.question.lower()
        return any(kw in q for kw in self.KEYWORDS)
    
    def analyze(self, market: Market) -> Prediction:
        current = market.current_price
        
        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=current,
            current_price=current,
            edge=0,
            confidence=60,
            confidence_low=max(0, current - 0.1),
            confidence_high=min(1, current + 0.1),
            direction="hold",
            strength="weak",
            reasoning="Would use FRED data, Fed communications, and futures implied probabilities.",
            key_risks=["Data revisions", "Fed pivot", "External shocks"],
            catalysts=["FOMC meetings", "CPI releases", "Jobs reports"]
        )


class GeneralAgent(ResearchAgent):
    """Fallback agent for uncategorized markets."""
    
    def __init__(self):
        super().__init__("GeneralAgent", [MarketCategory.OTHER])
    
    def can_analyze(self, market: Market) -> bool:
        return True  # Catches everything else
    
    def analyze(self, market: Market) -> Prediction:
        current = market.current_price
        
        return Prediction(
            market_id=market.market_id,
            market_question=market.question,
            predicted_probability=current,
            current_price=current,
            edge=0,
            confidence=30,
            confidence_low=max(0, current - 0.3),
            confidence_high=min(1, current + 0.3),
            direction="hold",
            strength="weak",
            reasoning="Uncategorized market. Requires manual research.",
            key_risks=["Unknown factors"],
            catalysts=["Varies"]
        )


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class AgentOrchestrator:
    """Coordinates research agents."""
    
    def __init__(self):
        # Order matters - more specific agents first
        self.agents = [
            PoliticsAgent(),
            SportsAgent(),
            CryptoAgent(),
            EconomicsAgent(),
            GeneralAgent()  # Fallback
        ]
    
    def find_agent(self, market: Market) -> ResearchAgent:
        """Find the best agent for a market."""
        for agent in self.agents:
            if agent.can_analyze(market):
                return agent
        return self.agents[-1]  # GeneralAgent fallback
    
    def research_market(self, market: Market) -> Prediction:
        """Research a single market."""
        agent = self.find_agent(market)
        return agent.research(market)
    
    def research_markets(self, markets: List[Market], min_edge: float = 0.0) -> List[Prediction]:
        """
        Research multiple markets.
        
        Args:
            markets: List of markets to research
            min_edge: Minimum absolute edge to include
        
        Returns:
            List of predictions sorted by absolute edge
        """
        predictions = []
        
        for market in markets:
            pred = self.research_market(market)
            if pred and abs(pred.edge) >= min_edge:
                predictions.append(pred)
        
        # Sort by absolute edge
        predictions.sort(key=lambda p: abs(p.edge), reverse=True)
        
        logger.info(f"Generated {len(predictions)} predictions")
        
        return predictions
