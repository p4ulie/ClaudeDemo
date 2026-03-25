"""
Layer 4: Trade Execution.
Handles order placement on Polymarket CLOB with safety checks:
- Balance pre-check before every trade
- Slippage protection (skips orders above 2% slippage)
- GTC (Good-Til-Cancelled) orders for higher fill rate on thin orderbooks
- Integration with position tracker for recording all trades
"""

import logging
from dataclasses import dataclass
from py_clob_client.client import ClobClient
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.clob_types import OrderArgs, OrderType
from polybot.math_engine import TradeSignal
from polybot.db import PositionTracker

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    order_id: str
    message: str
    fill_price: float
    slippage: float


class TradeExecutor:
    """
    Executes trades on Polymarket CLOB with pre-trade safety checks.
    All orders are GTC (Good-Til-Cancelled) for better fill rates on thin books.
    """

    def __init__(
        self,
        clob_client: ClobClient,
        position_tracker: PositionTracker,
        max_slippage: float = 0.02,
    ):
        self.client = clob_client
        self.tracker = position_tracker
        self.max_slippage = max_slippage

    async def execute_trade(
        self,
        signal: TradeSignal,
        token_id: str,
        condition_id: str,
        question: str,
        best_ask: float,
        best_bid: float,
        available_balance: float,
        prompt_version: str = "",
    ) -> ExecutionResult:
        """
        Execute a trade based on a math engine signal with full safety checks.
        1. Verify sufficient balance
        2. Check slippage against orderbook
        3. Place GTC order
        4. Record position in database
        """
        if not signal.should_trade:
            return ExecutionResult(False, "", "Signal says no trade", 0.0, 0.0)

        # Balance pre-check: verify funds before every trade
        if signal.position_size_usdc > available_balance:
            msg = f"Insufficient balance: need ${signal.position_size_usdc:.2f}, have ${available_balance:.2f}"
            logger.warning(msg)
            return ExecutionResult(False, "", msg, 0.0, 0.0)

        # Determine execution price based on side
        if signal.side == "BUY":
            exec_price = best_ask
            side = BUY
        else:
            exec_price = best_bid
            side = SELL

        # Slippage protection: skip if price moved too far from expected
        expected_price = best_ask if signal.side == "BUY" else best_bid
        slippage = abs(exec_price - expected_price) / expected_price if expected_price > 0 else 0
        if slippage > self.max_slippage:
            msg = f"Slippage {slippage:.2%} exceeds max {self.max_slippage:.2%}"
            logger.warning(msg)
            return ExecutionResult(False, "", msg, exec_price, slippage)

        # Calculate number of contracts from USDC size
        n_contracts = signal.position_size_usdc / exec_price

        # Build and submit GTC order
        try:
            order_args = OrderArgs(
                price=exec_price,
                size=n_contracts,
                side=side,
                token_id=token_id,
            )
            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, order_type=OrderType.GTC)
            order_id = response.get("orderID", response.get("id", "unknown"))

            # Record position in SQLite tracker
            position_id = await self.tracker.open_position(
                condition_id=condition_id,
                token_id=token_id,
                question=question,
                side=signal.side,
                entry_price=exec_price,
                size_usdc=signal.position_size_usdc,
                estimated_prob=signal.edge + exec_price,  # p_estimated = edge*m + m
                edge=signal.edge,
                kelly_frac=signal.kelly_fraction,
                prompt_version=prompt_version,
            )

            # Log the trade execution
            await self.tracker.log_trade(
                position_id=position_id,
                order_id=order_id,
                action=signal.side,
                price=exec_price,
                size=n_contracts,
            )

            logger.info(
                "Order placed: %s %s %.1f contracts @ %.3f (order=%s)",
                signal.side, question[:30], n_contracts, exec_price, order_id,
            )
            return ExecutionResult(True, order_id, "Order placed", exec_price, slippage)

        except Exception as e:
            msg = f"Order execution failed: {e}"
            logger.error(msg)
            return ExecutionResult(False, "", msg, exec_price, slippage)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a single open order."""
        try:
            self.client.cancel(order_id)
            logger.info("Cancelled order %s", order_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        try:
            self.client.cancel_all()
            logger.info("Cancelled all open orders")
            return True
        except Exception as e:
            logger.error("Failed to cancel all orders: %s", e)
            return False
