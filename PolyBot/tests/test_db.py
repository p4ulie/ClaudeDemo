"""
Tests for Layer 4: SQLite Position Tracker.
Uses an in-memory database for fast, isolated tests.
"""

import pytest
from polybot.db import PositionTracker


@pytest.fixture
async def tracker():
    """Create an in-memory position tracker for testing."""
    t = PositionTracker(db_path=":memory:")
    await t.connect()
    yield t
    await t.close()


class TestPositionTracker:
    """Tests for position CRUD operations and P&L tracking."""

    @pytest.mark.asyncio
    async def test_open_position(self, tracker):
        # Open a new position and verify it's stored
        pid = await tracker.open_position(
            condition_id="0xabc",
            token_id="token123",
            question="Will X happen?",
            side="BUY",
            entry_price=0.55,
            size_usdc=100.0,
            estimated_prob=0.70,
            edge=0.27,
            kelly_frac=0.15,
        )
        assert pid == 1

        positions = await tracker.get_open_positions()
        assert len(positions) == 1
        assert positions[0].condition_id == "0xabc"
        assert positions[0].entry_price == 0.55

    @pytest.mark.asyncio
    async def test_close_position_with_profit(self, tracker):
        # Open and close with profit
        pid = await tracker.open_position(
            condition_id="0xabc", token_id="t1", question="Test?",
            side="BUY", entry_price=0.50, size_usdc=100.0,
            estimated_prob=0.70, edge=0.40, kelly_frac=0.10,
        )
        await tracker.close_position(pid, exit_price=1.0)

        # Should have no open positions
        open_pos = await tracker.get_open_positions()
        assert len(open_pos) == 0

        # P&L should be positive
        pnl = await tracker.get_pnl_summary()
        assert pnl["total_pnl"] > 0
        assert pnl["wins"] == 1

    @pytest.mark.asyncio
    async def test_close_position_with_loss(self, tracker):
        # Open and close with loss (market resolves NO)
        pid = await tracker.open_position(
            condition_id="0xdef", token_id="t2", question="Losing bet?",
            side="BUY", entry_price=0.60, size_usdc=120.0,
            estimated_prob=0.75, edge=0.25, kelly_frac=0.12,
        )
        await tracker.close_position(pid, exit_price=0.0)

        pnl = await tracker.get_pnl_summary()
        assert pnl["total_pnl"] < 0
        assert pnl["losses"] == 1

    @pytest.mark.asyncio
    async def test_has_open_position(self, tracker):
        # Should detect existing open positions by condition_id
        await tracker.open_position(
            condition_id="0xabc", token_id="t1", question="Test?",
            side="BUY", entry_price=0.50, size_usdc=50.0,
            estimated_prob=0.60, edge=0.10, kelly_frac=0.05,
        )
        assert await tracker.has_open_position("0xabc") is True
        assert await tracker.has_open_position("0xother") is False

    @pytest.mark.asyncio
    async def test_total_exposure(self, tracker):
        # Total exposure is sum of size_usdc across open positions
        await tracker.open_position(
            condition_id="0xa", token_id="t1", question="Q1",
            side="BUY", entry_price=0.50, size_usdc=100.0,
            estimated_prob=0.60, edge=0.10, kelly_frac=0.05,
        )
        await tracker.open_position(
            condition_id="0xb", token_id="t2", question="Q2",
            side="BUY", entry_price=0.40, size_usdc=200.0,
            estimated_prob=0.55, edge=0.15, kelly_frac=0.08,
        )
        exposure = await tracker.get_total_exposure()
        assert exposure == pytest.approx(300.0)

    @pytest.mark.asyncio
    async def test_trade_log(self, tracker):
        # Log a trade against a position
        pid = await tracker.open_position(
            condition_id="0xabc", token_id="t1", question="Test?",
            side="BUY", entry_price=0.50, size_usdc=50.0,
            estimated_prob=0.60, edge=0.10, kelly_frac=0.05,
        )
        await tracker.log_trade(pid, order_id="order123", action="BUY", price=0.50, size=100.0)
        # No assertion needed - just verify it doesn't throw

    @pytest.mark.asyncio
    async def test_pnl_summary_empty(self, tracker):
        # Empty database should return zero P&L
        pnl = await tracker.get_pnl_summary()
        assert pnl["total_trades"] == 0
        assert pnl["total_pnl"] == 0
        assert pnl["win_rate"] == 0
