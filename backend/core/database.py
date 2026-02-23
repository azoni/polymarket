"""
Database Persistence
====================
SQLite database for persisting markets, opportunities, predictions,
trade signals, and agent activity across server restarts.
"""

import sqlite3
import json
import threading
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import (
    Market, Token, EdgeOpportunity, Prediction,
    MarketCategory, EdgeType, DashboardStats
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class Database:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: str = "polymarket_edge.db"):
        self.db_path = db_path
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def initialize(self):
        """Create tables if they don't exist."""
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS markets (
                market_id TEXT PRIMARY KEY,
                condition_id TEXT DEFAULT '',
                question TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'other',
                tags TEXT DEFAULT '[]',
                current_price REAL DEFAULT 0.5,
                spread_pct REAL DEFAULT 0.0,
                volume_24h REAL DEFAULT 0.0,
                liquidity REAL DEFAULT 0.0,
                end_date TEXT,
                days_until_resolution INTEGER,
                edge_score REAL DEFAULT 0.0,
                liquidity_score REAL DEFAULT 0.0,
                efficiency_score REAL DEFAULT 0.0,
                researchability_score REAL DEFAULT 0.0,
                tokens TEXT DEFAULT '[]',
                polymarket_url TEXT DEFAULT '',
                first_seen_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                edge_type TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL,
                expected_return REAL NOT NULL,
                risk_level TEXT NOT NULL,
                market_id TEXT NOT NULL,
                market_question TEXT NOT NULL,
                suggested_action TEXT DEFAULT '',
                reasoning TEXT DEFAULT '',
                detected_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                market_question TEXT NOT NULL,
                predicted_probability REAL NOT NULL,
                current_price REAL NOT NULL,
                edge REAL NOT NULL,
                confidence REAL NOT NULL,
                confidence_low REAL DEFAULT 0.0,
                confidence_high REAL DEFAULT 1.0,
                direction TEXT NOT NULL,
                strength TEXT NOT NULL,
                reasoning TEXT DEFAULT '',
                key_risks TEXT DEFAULT '[]',
                catalysts TEXT DEFAULT '[]',
                agent_name TEXT DEFAULT '',
                data_sources TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS trade_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cycle INTEGER,
                market_id TEXT,
                market_question TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                edge_type TEXT,
                confidence REAL,
                expected_return REAL,
                reasoning TEXT DEFAULT '',
                risk_level TEXT DEFAULT '',
                suggested_action TEXT DEFAULT '',
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'unknown',
                block_reason TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_question TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                cost REAL NOT NULL,
                edge_type TEXT,
                confidence REAL,
                expected_return REAL,
                token_id TEXT
            );

            CREATE TABLE IF NOT EXISTS balance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL NOT NULL,
                pnl REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                market_id TEXT,
                market_question TEXT,
                action TEXT NOT NULL,
                data_source TEXT DEFAULT '',
                success INTEGER DEFAULT 1,
                duration_ms REAL DEFAULT 0,
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS positions (
                token_id TEXT PRIMARY KEY,
                exchange TEXT DEFAULT 'polymarket',
                exposure REAL NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                market_id TEXT DEFAULT '',
                market TEXT DEFAULT '',
                edge_type TEXT DEFAULT '',
                reasoning TEXT DEFAULT '',
                opened_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS paper_account (
                exchange TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                starting_balance REAL NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Record schema version
        existing = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            conn.commit()

        logger.info(f"Database initialized: {self.db_path}")

    # ─── Markets ────────────────────────────────────────────────────────

    def upsert_markets(self, markets: List[Market]):
        conn = self._conn
        now = datetime.now().isoformat()
        rows = []
        for m in markets:
            tokens_json = json.dumps([t.model_dump() for t in m.tokens])
            tags_json = json.dumps(m.tags)
            rows.append((
                m.market_id, m.condition_id, m.question, m.description,
                m.category.value, tags_json, m.current_price, m.spread_pct,
                m.volume_24h, m.liquidity, m.end_date, m.days_until_resolution,
                m.edge_score, m.liquidity_score, m.efficiency_score,
                m.researchability_score, tokens_json, m.polymarket_url, now
            ))
        conn.executemany("""
            INSERT INTO markets (
                market_id, condition_id, question, description,
                category, tags, current_price, spread_pct,
                volume_24h, liquidity, end_date, days_until_resolution,
                edge_score, liquidity_score, efficiency_score,
                researchability_score, tokens, polymarket_url, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(market_id) DO UPDATE SET
                condition_id=excluded.condition_id,
                question=excluded.question,
                description=excluded.description,
                category=excluded.category,
                tags=excluded.tags,
                current_price=excluded.current_price,
                spread_pct=excluded.spread_pct,
                volume_24h=excluded.volume_24h,
                liquidity=excluded.liquidity,
                end_date=excluded.end_date,
                days_until_resolution=excluded.days_until_resolution,
                edge_score=excluded.edge_score,
                liquidity_score=excluded.liquidity_score,
                efficiency_score=excluded.efficiency_score,
                researchability_score=excluded.researchability_score,
                tokens=excluded.tokens,
                polymarket_url=excluded.polymarket_url,
                updated_at=excluded.updated_at
        """, rows)
        conn.commit()

    def _exchange_filter(self, exchange: Optional[str], id_col: str = "market_id") -> tuple:
        """Return (SQL fragment, params) to filter by exchange using market_id prefix."""
        if exchange == "kalshi":
            return f" AND {id_col} LIKE ?", ["kalshi:%"]
        elif exchange == "polymarket":
            return f" AND {id_col} NOT LIKE ?", ["kalshi:%"]
        return "", []

    def get_markets(
        self,
        category: Optional[str] = None,
        min_score: float = 0,
        min_volume: float = 0,
        sort_by: str = "edge_score",
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        exchange: Optional[str] = None,
    ) -> List[Market]:
        allowed_sorts = {"edge_score", "volume_24h", "liquidity", "spread_pct"}
        if sort_by not in allowed_sorts:
            sort_by = "edge_score"

        query = "SELECT * FROM markets WHERE 1=1"
        params: list = []

        ex_sql, ex_params = self._exchange_filter(exchange)
        query += ex_sql
        params.extend(ex_params)

        if category:
            query += " AND category = ?"
            params.append(category)
        if min_score > 0:
            query += " AND edge_score >= ?"
            params.append(min_score)
        if min_volume > 0:
            query += " AND volume_24h >= ?"
            params.append(min_volume)
        if search:
            query += " AND LOWER(question) LIKE ?"
            params.append(f"%{search.lower()}%")

        direction = "DESC" if sort_by != "spread_pct" else "ASC"
        query += f" ORDER BY {sort_by} {direction} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_market(r) for r in rows]

    def get_market(self, market_id: str) -> Optional[Market]:
        row = self._conn.execute(
            "SELECT * FROM markets WHERE market_id = ?", (market_id,)
        ).fetchone()
        return self._row_to_market(row) if row else None

    def _row_to_market(self, row: sqlite3.Row) -> Market:
        tokens_data = json.loads(row["tokens"])
        tokens = [Token(**t) for t in tokens_data]
        tags = json.loads(row["tags"])
        return Market(
            market_id=row["market_id"],
            condition_id=row["condition_id"],
            question=row["question"],
            description=row["description"],
            category=MarketCategory(row["category"]),
            tags=tags,
            current_price=row["current_price"],
            spread_pct=row["spread_pct"],
            volume_24h=row["volume_24h"],
            liquidity=row["liquidity"],
            end_date=row["end_date"],
            days_until_resolution=row["days_until_resolution"],
            edge_score=row["edge_score"],
            liquidity_score=row["liquidity_score"],
            efficiency_score=row["efficiency_score"],
            researchability_score=row["researchability_score"],
            tokens=tokens,
            polymarket_url=row["polymarket_url"],
        )

    # ─── Opportunities ──────────────────────────────────────────────────

    def save_opportunities(self, opportunities: List[EdgeOpportunity], exchange: Optional[str] = None):
        conn = self._conn
        # Deactivate old opportunities (scoped by exchange)
        if exchange == "kalshi":
            conn.execute("UPDATE opportunities SET is_active = 0 WHERE market_id LIKE 'kalshi:%'")
        elif exchange == "polymarket":
            conn.execute("UPDATE opportunities SET is_active = 0 WHERE market_id NOT LIKE 'kalshi:%'")
        else:
            conn.execute("UPDATE opportunities SET is_active = 0")
        rows = []
        for o in opportunities:
            detected_at = o.detected_at.isoformat() if isinstance(o.detected_at, datetime) else str(o.detected_at)
            rows.append((
                o.id, o.edge_type.value, o.description, o.confidence,
                o.expected_return, o.risk_level, o.market_id,
                o.market_question, o.suggested_action, o.reasoning,
                detected_at, 1
            ))
        conn.executemany("""
            INSERT OR REPLACE INTO opportunities (
                id, edge_type, description, confidence, expected_return,
                risk_level, market_id, market_question, suggested_action,
                reasoning, detected_at, is_active
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    def get_opportunities(
        self,
        edge_type: Optional[str] = None,
        min_confidence: float = 0,
        risk_level: Optional[str] = None,
        limit: int = 50,
        exchange: Optional[str] = None,
    ) -> List[EdgeOpportunity]:
        query = "SELECT * FROM opportunities WHERE is_active = 1"
        params: list = []

        ex_sql, ex_params = self._exchange_filter(exchange)
        query += ex_sql
        params.extend(ex_params)

        if edge_type:
            query += " AND edge_type = ?"
            params.append(edge_type)
        if min_confidence > 0:
            query += " AND confidence >= ?"
            params.append(min_confidence)
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level)

        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def get_market_opportunities(self, market_id: str) -> List[EdgeOpportunity]:
        rows = self._conn.execute(
            "SELECT * FROM opportunities WHERE market_id = ? AND is_active = 1 ORDER BY confidence DESC",
            (market_id,)
        ).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def _row_to_opportunity(self, row: sqlite3.Row) -> EdgeOpportunity:
        return EdgeOpportunity(
            id=row["id"],
            edge_type=EdgeType(row["edge_type"]),
            description=row["description"],
            confidence=row["confidence"],
            expected_return=row["expected_return"],
            risk_level=row["risk_level"],
            market_id=row["market_id"],
            market_question=row["market_question"],
            suggested_action=row["suggested_action"],
            reasoning=row["reasoning"],
        )

    # ─── Predictions ────────────────────────────────────────────────────

    def save_predictions(self, predictions: List[Prediction], exchange: Optional[str] = None):
        conn = self._conn
        # Clear old predictions scoped by exchange
        if exchange == "kalshi":
            conn.execute("DELETE FROM predictions WHERE market_id LIKE 'kalshi:%'")
        elif exchange == "polymarket":
            conn.execute("DELETE FROM predictions WHERE market_id NOT LIKE 'kalshi:%'")
        else:
            conn.execute("DELETE FROM predictions")
        rows = []
        for p in predictions:
            data_sources = json.dumps(getattr(p, "data_sources", []))
            rows.append((
                p.market_id, p.market_question, p.predicted_probability,
                p.current_price, p.edge, p.confidence, p.confidence_low,
                p.confidence_high, p.direction, p.strength, p.reasoning,
                json.dumps(p.key_risks), json.dumps(p.catalysts),
                p.agent_name, data_sources
            ))
        conn.executemany("""
            INSERT INTO predictions (
                market_id, market_question, predicted_probability,
                current_price, edge, confidence, confidence_low,
                confidence_high, direction, strength, reasoning,
                key_risks, catalysts, agent_name, data_sources
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    def get_predictions(
        self,
        direction: Optional[str] = None,
        min_edge: float = 0,
        limit: int = 50,
        exchange: Optional[str] = None,
    ) -> List[Prediction]:
        query = """
            SELECT p.*, m.polymarket_url
            FROM predictions p
            LEFT JOIN markets m ON p.market_id = m.market_id
            WHERE 1=1
        """
        params: list = []

        ex_sql, ex_params = self._exchange_filter(exchange, id_col="p.market_id")
        query += ex_sql
        params.extend(ex_params)

        if direction:
            query += " AND p.direction = ?"
            params.append(direction)
        if min_edge > 0:
            query += " AND ABS(p.edge) >= ?"
            params.append(min_edge)

        query += " ORDER BY ABS(p.edge) DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_prediction(r) for r in rows]

    def get_market_predictions(self, market_id: str) -> List[Prediction]:
        rows = self._conn.execute(
            """SELECT p.*, m.polymarket_url
               FROM predictions p
               LEFT JOIN markets m ON p.market_id = m.market_id
               WHERE p.market_id = ? ORDER BY ABS(p.edge) DESC""",
            (market_id,)
        ).fetchall()
        return [self._row_to_prediction(r) for r in rows]

    def _row_to_prediction(self, row: sqlite3.Row) -> Prediction:
        keys = row.keys()
        return Prediction(
            market_id=row["market_id"],
            market_question=row["market_question"],
            predicted_probability=row["predicted_probability"],
            current_price=row["current_price"],
            edge=row["edge"],
            confidence=row["confidence"],
            confidence_low=row["confidence_low"],
            confidence_high=row["confidence_high"],
            direction=row["direction"],
            strength=row["strength"],
            reasoning=row["reasoning"],
            key_risks=json.loads(row["key_risks"]),
            catalysts=json.loads(row["catalysts"]),
            agent_name=row["agent_name"],
            data_sources=json.loads(row["data_sources"]),
            polymarket_url=row["polymarket_url"] if "polymarket_url" in keys else "",
        )

    # ─── Trade Signals ──────────────────────────────────────────────────

    def save_signal(self, signal: dict):
        conn = self._conn
        conn.execute("""
            INSERT INTO trade_signals (
                timestamp, cycle, market_id, market_question, side, price,
                size, edge_type, confidence, expected_return, reasoning,
                risk_level, suggested_action, description, status, block_reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            signal.get("timestamp", ""),
            signal.get("cycle"),
            signal.get("market_id", ""),
            signal.get("market", ""),
            signal.get("side", ""),
            signal.get("price", 0),
            signal.get("size", 0),
            signal.get("edge_type", ""),
            signal.get("confidence", 0),
            signal.get("expected_return", 0),
            signal.get("reasoning", ""),
            signal.get("risk_level", ""),
            signal.get("suggested_action", ""),
            signal.get("description", ""),
            signal.get("status", "unknown"),
            signal.get("reason", ""),
        ))
        conn.commit()

    def get_signals(self, limit: int = 100) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM trade_signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Trade History ──────────────────────────────────────────────────

    def save_trade(self, trade: dict):
        conn = self._conn
        conn.execute("""
            INSERT INTO trade_history (
                timestamp, market_question, side, entry_price, size,
                cost, edge_type, confidence, expected_return, token_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            trade.get("timestamp", ""),
            trade.get("market", ""),
            trade.get("side", ""),
            trade.get("entry_price", 0),
            trade.get("size", 0),
            trade.get("cost", 0),
            trade.get("edge_type", ""),
            trade.get("confidence", 0),
            trade.get("expected_return", 0),
            trade.get("token_id", ""),
        ))
        conn.commit()

    def get_trades(self, limit: int = 500) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Balance Snapshots ──────────────────────────────────────────────

    def save_balance_snapshot(self, timestamp: str, balance: float, pnl: float):
        conn = self._conn
        conn.execute(
            "INSERT INTO balance_snapshots (timestamp, balance, pnl) VALUES (?,?,?)",
            (timestamp, balance, pnl)
        )
        conn.commit()

    def get_balance_history(self, limit: int = 500) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM balance_snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = [dict(r) for r in rows]
        result.reverse()  # chronological order
        return result

    # ─── Agent Activity ─────────────────────────────────────────────────

    def log_agent_activity(
        self,
        agent_name: str,
        market_id: Optional[str],
        market_question: Optional[str],
        action: str,
        data_source: str = "",
        success: bool = True,
        duration_ms: float = 0,
        details: str = "",
    ):
        conn = self._conn
        conn.execute("""
            INSERT INTO agent_activity (
                agent_name, market_id, market_question, action,
                data_source, success, duration_ms, details
            ) VALUES (?,?,?,?,?,?,?,?)
        """, (
            agent_name, market_id, market_question, action,
            data_source, 1 if success else 0, duration_ms, details
        ))
        conn.commit()

    def get_agent_activity(
        self, agent_name: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        if agent_name:
            rows = self._conn.execute(
                "SELECT * FROM agent_activity WHERE agent_name = ? ORDER BY id DESC LIMIT ?",
                (agent_name, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM agent_activity ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_agent_stats(self) -> List[dict]:
        """Get aggregate stats per agent for the status endpoint."""
        rows = self._conn.execute("""
            SELECT
                agent_name,
                COUNT(*) as total_actions,
                SUM(CASE WHEN action = 'analyze' THEN 1 ELSE 0 END) as markets_analyzed,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                MAX(created_at) as last_run,
                AVG(duration_ms) as avg_duration_ms
            FROM agent_activity
            GROUP BY agent_name
        """).fetchall()
        return [dict(r) for r in rows]

    # ─── Positions ─────────────────────────────────────────────────────

    def save_positions(self, positions: dict, exchange: str = "polymarket"):
        """Persist all open positions (replaces existing for this exchange)."""
        conn = self._conn
        conn.execute("DELETE FROM positions WHERE exchange = ?", (exchange,))
        for token_id, pos in positions.items():
            if isinstance(pos, dict):
                conn.execute("""
                    INSERT INTO positions (token_id, exchange, exposure, side, entry_price,
                        market_id, market, edge_type, reasoning, opened_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (
                    token_id, exchange,
                    pos.get("exposure", 0),
                    pos.get("side", "BUY"),
                    pos.get("entry_price", 0),
                    pos.get("market_id", ""),
                    pos.get("market", ""),
                    pos.get("edge_type", ""),
                    pos.get("reasoning", ""),
                    pos.get("opened_at", datetime.now().isoformat()),
                ))
        conn.commit()

    def load_positions(self, exchange: str = "polymarket") -> dict:
        """Load open positions for an exchange."""
        rows = self._conn.execute(
            "SELECT * FROM positions WHERE exchange = ?", (exchange,)
        ).fetchall()
        positions = {}
        for r in rows:
            positions[r["token_id"]] = {
                "exposure": r["exposure"],
                "side": r["side"],
                "entry_price": r["entry_price"],
                "market_id": r["market_id"],
                "market": r["market"],
                "edge_type": r["edge_type"],
                "reasoning": r["reasoning"],
                "opened_at": r["opened_at"],
            }
        return positions

    def save_paper_account(self, exchange: str, balance: float,
                           starting_balance: float, realized_pnl: float):
        """Persist paper account state."""
        conn = self._conn
        conn.execute("""
            INSERT INTO paper_account (exchange, balance, starting_balance, realized_pnl, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(exchange) DO UPDATE SET
                balance=excluded.balance,
                starting_balance=excluded.starting_balance,
                realized_pnl=excluded.realized_pnl,
                updated_at=excluded.updated_at
        """, (exchange, balance, starting_balance, realized_pnl, datetime.now().isoformat()))
        conn.commit()

    def load_paper_account(self, exchange: str = "polymarket") -> dict | None:
        """Load paper account state. Returns None if not saved yet."""
        row = self._conn.execute(
            "SELECT * FROM paper_account WHERE exchange = ?", (exchange,)
        ).fetchone()
        if row:
            return {
                "balance": row["balance"],
                "starting_balance": row["starting_balance"],
                "realized_pnl": row["realized_pnl"],
            }
        return None

    # ─── Dashboard Stats ────────────────────────────────────────────────

    def get_stats(self, exchange: Optional[str] = None) -> dict:
        conn = self._conn

        ex_sql, ex_params = self._exchange_filter(exchange)

        total_markets = conn.execute(
            f"SELECT COUNT(*) FROM markets WHERE 1=1{ex_sql}", ex_params
        ).fetchone()[0]
        total_opps = conn.execute(
            f"SELECT COUNT(*) FROM opportunities WHERE is_active = 1{ex_sql}", ex_params
        ).fetchone()[0]
        high_conf = conn.execute(
            f"SELECT COUNT(*) FROM opportunities WHERE is_active = 1 AND confidence >= 70{ex_sql}", ex_params
        ).fetchone()[0]
        total_preds = conn.execute(
            f"SELECT COUNT(*) FROM predictions WHERE 1=1{ex_sql}", ex_params
        ).fetchone()[0]

        cat_rows = conn.execute(
            f"SELECT category, COUNT(*) as cnt FROM markets WHERE 1=1{ex_sql} GROUP BY category", ex_params
        ).fetchall()
        markets_by_category = {r["category"]: r["cnt"] for r in cat_rows}

        return {
            "total_markets": total_markets,
            "total_opportunities": total_opps,
            "high_confidence_opps": high_conf,
            "total_predictions": total_preds,
            "markets_by_category": markets_by_category,
        }
