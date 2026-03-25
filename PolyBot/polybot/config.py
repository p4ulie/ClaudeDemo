"""
Configuration management for PolyBot.
Loads settings from environment variables via python-dotenv.
All sensitive values (API keys, private keys) are read from .env file.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class PolymarketConfig:
    """Polymarket CLOB API connection settings."""
    host: str = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com")
    chain_id: int = int(os.getenv("POLYMARKET_CHAIN_ID", "137"))
    private_key: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    api_key: str = os.getenv("POLYMARKET_API_KEY", "")
    api_secret: str = os.getenv("POLYMARKET_API_SECRET", "")
    api_passphrase: str = os.getenv("POLYMARKET_API_PASSPHRASE", "")


@dataclass(frozen=True)
class BlockchainConfig:
    """Polygon RPC and on-chain settings."""
    rpc_url: str = os.getenv("ALCHEMY_RPC_URL", "")
    # USDC.e (Bridged USDC) on Polygon - 6 decimals
    usdc_address: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    usdc_decimals: int = 6


@dataclass(frozen=True)
class AIConfig:
    """Claude API settings for probability estimation."""
    api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram bot notification settings."""
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: int = int(os.getenv("TELEGRAM_CHAT_ID", "0"))


@dataclass(frozen=True)
class TradingConfig:
    """Trading strategy parameters."""
    min_edge: float = float(os.getenv("MIN_EDGE", "0.05"))
    kelly_fraction: float = float(os.getenv("KELLY_FRACTION", "0.5"))
    max_slippage: float = float(os.getenv("MAX_SLIPPAGE", "0.02"))
    scan_interval: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
    max_position_usdc: float = float(os.getenv("MAX_POSITION_USDC", "500"))
    bankroll_usdc: float = float(os.getenv("BANKROLL_USDC", "10000"))


@dataclass(frozen=True)
class Config:
    """Top-level config aggregating all subsections."""
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    blockchain: BlockchainConfig = field(default_factory=BlockchainConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
