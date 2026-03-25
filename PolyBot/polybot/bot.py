"""
Layer 6: Main Bot Orchestrator.
Ties all layers together into a fully concurrent asyncio application:
1. Scans markets via Polymarket CLOB API
2. Estimates probabilities via Claude AI
3. Filters by expected value and sizes via Kelly Criterion
4. Executes GTC orders with slippage protection
5. Sends Telegram notifications and logs every decision
6. Recovers from errors and continues running

Designed to run as a systemd service on a VPS.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from polybot.config import Config
from polybot.market import MarketClient
from polybot.brain import AIBrain
from polybot.math_engine import generate_signal
from polybot.execution import TradeExecutor
from polybot.db import PositionTracker
from polybot.blockchain import BlockchainClient
from polybot.monitor import TelegramMonitor

# Configure logging with timestamps for every decision
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("polybot.log"),
    ],
)
logger = logging.getLogger("polybot")


class PolyBot:
    """
    Main bot orchestrator. Runs a continuous scan-evaluate-trade loop
    with full concurrency via asyncio. Catches exceptions at the top level
    so the bot continues running even if individual operations fail.
    """

    def __init__(self, config: Config):
        self.cfg = config

        # Layer 1: Market access
        self.market = MarketClient(config.polymarket)

        # Layer 1/4: Blockchain (balance checks)
        wallet = self._derive_wallet_address(config.polymarket.private_key)
        self.blockchain = BlockchainClient(config.blockchain, wallet)

        # Layer 2: AI brain
        self.brain = AIBrain(config.ai)

        # Layer 4: Position tracker (SQLite)
        self.tracker = PositionTracker()

        # Layer 4: Trade executor
        self.executor = TradeExecutor(
            clob_client=self.market.client,
            position_tracker=self.tracker,
            max_slippage=config.trading.max_slippage,
        )

        # Layer 5: Monitoring
        self.monitor = TelegramMonitor(config.telegram, self.tracker)

    def _derive_wallet_address(self, private_key: str) -> str:
        """Derive Ethereum wallet address from private key."""
        try:
            from eth_account import Account
            acct = Account.from_key(private_key)
            return acct.address
        except Exception:
            logger.warning("Could not derive wallet address from private key")
            return "0x0000000000000000000000000000000000000000"

    async def start(self):
        """Initialize async resources and start the main loop."""
        await self.tracker.connect()
        logger.info("PolyBot starting — scan interval: %ds", self.cfg.trading.scan_interval)
        await self.monitor.send_message("🤖 <b>PolyBot started</b>")

        try:
            await self._run_loop()
        except KeyboardInterrupt:
            logger.info("Shutting down via keyboard interrupt")
        finally:
            await self._shutdown()

    async def _run_loop(self):
        """Main scan-evaluate-trade loop. Runs continuously until stopped."""
        while True:
            try:
                await self._scan_cycle()
            except Exception as e:
                # Error recovery: log the error, notify, and continue
                logger.exception("Error in scan cycle: %s", e)
                await self.monitor.notify_error(str(e), context="scan_cycle")

            await asyncio.sleep(self.cfg.trading.scan_interval)

    async def _scan_cycle(self):
        """
        Single scan cycle:
        1. Fetch active markets
        2. Filter candidates (skip markets we already hold)
        3. Estimate probabilities concurrently via Claude
        4. Generate trade signals via math engine
        5. Execute qualifying trades
        """
        logger.info("--- Scan cycle started at %s ---", datetime.now(timezone.utc).isoformat())

        # Fetch markets from Polymarket CLOB
        raw_markets = self.market.get_markets()
        active_markets = [m for m in raw_markets if m.get("active")]
        logger.info("Found %d active markets", len(active_markets))

        # Check available balance
        balance = self.blockchain.get_usdc_balance()
        current_exposure = await self.tracker.get_total_exposure()
        available = min(balance, self.cfg.trading.bankroll_usdc - current_exposure)

        if available <= 0:
            logger.info("No available capital (balance=$%.2f, exposure=$%.2f)", balance, current_exposure)
            return

        trades_placed = 0

        for raw_market in active_markets:
            try:
                market = self.market.parse_market(raw_market)

                # Skip markets we already have a position in
                if await self.tracker.has_open_position(market.condition_id):
                    continue

                # Skip very low volume markets (less liquid)
                if market.volume < 1000:
                    continue

                # Get orderbook for the YES token
                orderbook = self.market.get_orderbook(market.token_id_yes)

                # Skip thin orderbooks (unreliable prices)
                if orderbook.depth_usdc < 100:
                    continue

                # Layer 2: AI probability estimation
                estimate = await self.brain.estimate_probability(
                    question=market.question,
                    current_price=market.price_yes,
                    market_volume=market.volume,
                )

                # Skip low-confidence estimates
                if estimate.confidence < 0.3:
                    logger.debug("Low confidence (%.2f) for: %s", estimate.confidence, market.question[:40])
                    continue

                # Layer 3: Math engine - generate trade signal
                signal = generate_signal(
                    p_estimated=estimate.estimated_probability,
                    market_price=market.price_yes,
                    bankroll=self.cfg.trading.bankroll_usdc,
                    min_edge=self.cfg.trading.min_edge,
                    kelly_mult=self.cfg.trading.kelly_fraction,
                    max_position=self.cfg.trading.max_position_usdc,
                )

                if not signal.should_trade:
                    continue

                # Layer 4: Execute the trade
                result = await self.executor.execute_trade(
                    signal=signal,
                    token_id=market.token_id_yes,
                    condition_id=market.condition_id,
                    question=market.question,
                    best_ask=orderbook.best_ask,
                    best_bid=orderbook.best_bid,
                    available_balance=available,
                    prompt_version=estimate.prompt_version,
                )

                if result.success:
                    trades_placed += 1
                    available -= signal.position_size_usdc

                    # Layer 5: Notify via Telegram
                    await self.monitor.notify_trade(
                        side=signal.side,
                        question=market.question,
                        price=result.fill_price,
                        size_usdc=signal.position_size_usdc,
                        edge=signal.edge,
                        order_id=result.order_id,
                    )

                    # Stop if we've used all available capital
                    if available < 5:
                        logger.info("Available capital exhausted")
                        break

            except Exception as e:
                logger.error("Error processing market %s: %s", raw_market.get("question", "?")[:30], e)
                continue

        # Scan summary notification
        await self.monitor.notify_scan_summary(len(active_markets), trades_placed)
        logger.info("--- Scan cycle complete: %d markets, %d trades ---", len(active_markets), trades_placed)

    async def _shutdown(self):
        """Clean shutdown: close all connections."""
        logger.info("Shutting down PolyBot...")
        await self.monitor.send_message("🛑 <b>PolyBot stopped</b>")
        await self.brain.close()
        await self.monitor.close()
        await self.tracker.close()
        logger.info("Shutdown complete")


def main():
    """Entry point: load config and run the bot."""
    config = Config()
    bot = PolyBot(config)
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
