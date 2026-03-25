"""
Layer 5: Monitoring and Alerts.
- Telegram bot via aiogram for real-time trade notifications
- Position dashboard: view and close positions from phone
- Python logging with timestamps for every decision
- Error recovery: catches exceptions and continues running
"""

import logging
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from polybot.config import TelegramConfig
from polybot.db import PositionTracker

logger = logging.getLogger(__name__)

# Router for handling Telegram commands
router = Router()


class TelegramMonitor:
    """
    Sends real-time trade notifications and provides a position dashboard
    via Telegram. Users can view and close positions from their phone.
    """

    def __init__(self, cfg: TelegramConfig, tracker: PositionTracker):
        self.chat_id = cfg.chat_id
        self.tracker = tracker
        self.bot = Bot(
            token=cfg.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) if cfg.bot_token else None

    async def send_message(self, text: str):
        """Send a message to the configured Telegram chat."""
        if not self.bot:
            logger.debug("Telegram not configured, skipping: %s", text[:50])
            return
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
        except Exception as e:
            # Error recovery: log and continue, don't crash the bot
            logger.error("Telegram send failed: %s", e)

    async def notify_trade(
        self,
        side: str,
        question: str,
        price: float,
        size_usdc: float,
        edge: float,
        order_id: str,
    ):
        """Send a trade execution notification."""
        emoji = "🟢" if side == "BUY" else "🔴"
        text = (
            f"{emoji} <b>Trade Executed</b>\n\n"
            f"<b>Market:</b> {question}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Price:</b> {price:.3f}\n"
            f"<b>Size:</b> ${size_usdc:.2f}\n"
            f"<b>Edge:</b> {edge:.2%}\n"
            f"<b>Order:</b> <code>{order_id[:16]}...</code>"
        )
        await self.send_message(text)

    async def notify_error(self, error: str, context: str = ""):
        """Send an error alert so issues are caught immediately."""
        text = (
            f"⚠️ <b>Error</b>\n\n"
            f"<b>Context:</b> {context}\n"
            f"<b>Error:</b> {error}"
        )
        await self.send_message(text)

    async def notify_scan_summary(self, markets_scanned: int, trades_placed: int):
        """Periodic summary of scanning activity."""
        text = (
            f"📊 <b>Scan Complete</b>\n\n"
            f"Markets scanned: {markets_scanned}\n"
            f"Trades placed: {trades_placed}"
        )
        await self.send_message(text)

    async def send_dashboard(self):
        """Send a position dashboard showing all open positions and P&L."""
        positions = await self.tracker.get_open_positions()
        pnl = await self.tracker.get_pnl_summary()
        exposure = await self.tracker.get_total_exposure()

        if not positions:
            lines = ["📋 <b>Dashboard</b>\n\nNo open positions."]
        else:
            lines = [f"📋 <b>Dashboard</b> ({len(positions)} open)\n"]
            for p in positions:
                lines.append(
                    f"• {p.side} <b>{p.question[:40]}</b>\n"
                    f"  Entry: {p.entry_price:.3f} | Size: ${p.size_usdc:.0f} | Edge: {p.edge:.1%}"
                )

        lines.append(f"\n💰 <b>Exposure:</b> ${exposure:.2f}")
        lines.append(
            f"📈 <b>Closed P&L:</b> ${pnl['total_pnl']:.2f} "
            f"({pnl['wins']}W / {pnl['losses']}L | {pnl['win_rate']:.0%})"
        )
        await self.send_message("\n".join(lines))

    async def close(self):
        """Close the bot session cleanly."""
        if self.bot:
            await self.bot.session.close()


def setup_command_handlers(monitor: TelegramMonitor):
    """
    Register Telegram command handlers for the position dashboard.
    /dashboard - View open positions and P&L
    /balance - Check current exposure
    """

    @router.message(F.text == "/dashboard")
    async def cmd_dashboard(message: Message):
        """Handle /dashboard command - show position overview."""
        await monitor.send_dashboard()

    @router.message(F.text == "/balance")
    async def cmd_balance(message: Message):
        """Handle /balance command - show current exposure."""
        exposure = await monitor.tracker.get_total_exposure()
        pnl = await monitor.tracker.get_pnl_summary()
        await message.answer(
            f"💰 <b>Current Exposure:</b> ${exposure:.2f}\n"
            f"📈 <b>Total P&L:</b> ${pnl['total_pnl']:.2f}"
        )

    return router
