"""
Layer 4: SQLite Position Tracker.
Local database of all open and closed positions, trades, and P&L history.
Uses aiosqlite for async database operations that don't block the event loop.
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass
import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "polybot.db"

# Schema for the positions table
SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    question TEXT,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    size_usdc REAL NOT NULL,
    n_contracts REAL NOT NULL,
    estimated_prob REAL,
    edge REAL,
    kelly_fraction REAL,
    status TEXT DEFAULT 'open',
    exit_price REAL,
    pnl_usdc REAL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    prompt_version TEXT
);

CREATE TABLE IF NOT EXISTS trade_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER REFERENCES positions(id),
    order_id TEXT,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    timestamp TEXT NOT NULL
);
"""


@dataclass
class Position:
    """Represents a tracked position in the database."""
    id: int
    condition_id: str
    token_id: str
    question: str
    side: str
    entry_price: float
    size_usdc: float
    n_contracts: float
    estimated_prob: float
    edge: float
    kelly_fraction: float
    status: str
    exit_price: float | None
    pnl_usdc: float | None
    opened_at: str
    closed_at: str | None
    prompt_version: str | None


class PositionTracker:
    """
    Async SQLite database for tracking positions and trade history.
    Persists all trading decisions with timestamps for analysis.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        """Open database connection and create tables if needed."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("PositionTracker connected to %s", self.db_path)

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()

    async def open_position(
        self,
        condition_id: str,
        token_id: str,
        question: str,
        side: str,
        entry_price: float,
        size_usdc: float,
        estimated_prob: float,
        edge: float,
        kelly_frac: float,
        prompt_version: str = "",
    ) -> int:
        """Record a new open position. Returns the position ID."""
        n_contracts = size_usdc / entry_price
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO positions
               (condition_id, token_id, question, side, entry_price, size_usdc,
                n_contracts, estimated_prob, edge, kelly_fraction, status, opened_at, prompt_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (condition_id, token_id, question, side, entry_price, size_usdc,
             n_contracts, estimated_prob, edge, kelly_frac, now, prompt_version),
        )
        await self._db.commit()
        logger.info("Opened position #%d: %s %s @ %.3f", cursor.lastrowid, side, question[:40], entry_price)
        return cursor.lastrowid

    async def close_position(self, position_id: int, exit_price: float):
        """Mark a position as closed and calculate realized P&L."""
        row = await self._db.execute_fetchall(
            "SELECT entry_price, n_contracts, side FROM positions WHERE id = ?",
            (position_id,),
        )
        if not row:
            logger.warning("Position #%d not found", position_id)
            return

        entry_price, n_contracts, side = row[0][0], row[0][1], row[0][2]
        # P&L: (exit - entry) * contracts for BUY, (entry - exit) * contracts for SELL
        if side == "BUY":
            pnl = (exit_price - entry_price) * n_contracts
        else:
            pnl = (entry_price - exit_price) * n_contracts

        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """UPDATE positions SET status='closed', exit_price=?, pnl_usdc=?, closed_at=?
               WHERE id=?""",
            (exit_price, pnl, now, position_id),
        )
        await self._db.commit()
        logger.info("Closed position #%d: P&L=$%.2f", position_id, pnl)

    async def log_trade(self, position_id: int, order_id: str, action: str, price: float, size: float):
        """Log an individual trade execution against a position."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO trade_log (position_id, order_id, action, price, size, timestamp) VALUES (?,?,?,?,?,?)",
            (position_id, order_id, action, price, size, now),
        )
        await self._db.commit()

    async def get_open_positions(self) -> list[Position]:
        """Fetch all currently open positions."""
        rows = await self._db.execute_fetchall(
            "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC"
        )
        return [Position(*row) for row in rows]

    async def get_total_exposure(self) -> float:
        """Sum of size_usdc across all open positions."""
        rows = await self._db.execute_fetchall(
            "SELECT COALESCE(SUM(size_usdc), 0) FROM positions WHERE status = 'open'"
        )
        return rows[0][0]

    async def get_pnl_summary(self) -> dict:
        """Aggregate P&L statistics across all closed positions."""
        rows = await self._db.execute_fetchall(
            """SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_usdc > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usdc <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(pnl_usdc), 0) as total_pnl,
                COALESCE(AVG(pnl_usdc), 0) as avg_pnl
               FROM positions WHERE status = 'closed'"""
        )
        r = rows[0]
        return {
            "total_trades": r[0],
            "wins": r[1],
            "losses": r[2],
            "total_pnl": r[3],
            "avg_pnl": r[4],
            "win_rate": r[1] / r[0] if r[0] > 0 else 0,
        }

    async def has_open_position(self, condition_id: str) -> bool:
        """Check if we already have an open position in a given market."""
        rows = await self._db.execute_fetchall(
            "SELECT COUNT(*) FROM positions WHERE condition_id = ? AND status = 'open'",
            (condition_id,),
        )
        return rows[0][0] > 0
