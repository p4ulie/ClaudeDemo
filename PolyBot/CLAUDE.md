# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is PolyBot

PolyBot is an autonomous Polymarket trading bot written in Python 3.11+. It scans prediction markets, estimates probabilities using Claude AI, applies mathematical filters (Kelly Criterion, expected value), and executes trades with slippage protection. It runs as a systemd service on a VPS ($8/month) with Telegram notifications.

## Architecture (6 Layers)

The bot is organized into 6 layers that form a pipeline:

1. **Data & Market Access** (`market.py`, `blockchain.py`) — Polymarket CLOB API via `py-clob-client` for prices/orderbooks; `web3.py` + Alchemy RPC for on-chain USDC.e balance checks on Polygon
2. **AI Brain** (`brain.py`, `prompts/`) — Claude API estimates true probability per market; structured JSON prompts ensure parseable output; prompt versions tracked in `prompts/v1.py`
3. **Math Engine** (`math_engine.py`) — Expected value filtering (edge > 5%), Kelly Criterion position sizing (half-Kelly default), Bayesian updating for probability revision, log returns for P&L tracking
4. **Execution** (`execution.py`, `db.py`) — GTC orders on CLOB, balance pre-checks, slippage protection (<2%), SQLite position tracker via `aiosqlite`
5. **Monitoring** (`monitor.py`) — Telegram bot via `aiogram` for trade alerts and `/dashboard` command; Python logging with timestamps
6. **Infrastructure** (`bot.py`, `polybot.service`) — asyncio main loop, systemd auto-restart, `.env` config

The main loop in `bot.py` (`PolyBot._scan_cycle`) ties everything together: fetch markets → AI estimate → math filter → execute → notify.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_math_engine.py -v

# Run a specific test class or method
python -m pytest tests/test_math_engine.py::TestKellyCriterion -v

# Start the bot
python -m polybot.bot

# Deploy as systemd service
sudo cp polybot.service /etc/systemd/system/
sudo systemctl enable --now polybot
journalctl -u polybot -f
```

## Configuration

All config is via environment variables loaded from `.env` (see `.env.example`). The `Config` dataclass in `config.py` aggregates all subsections. Key trading parameters: `MIN_EDGE`, `KELLY_FRACTION`, `MAX_SLIPPAGE`, `MAX_POSITION_USDC`, `BANKROLL_USDC`.

## Key Design Decisions

- **Half-Kelly default**: `kelly_fraction=0.5` for safer position sizing vs full Kelly
- **Conservative AI fallback**: if Claude's JSON response fails to parse, returns `p=0.5` (no edge → no trade)
- **Slippage cap**: orders skip if price moved >2% from expected
- **USDC.e on Polygon**: uses bridged USDC (`0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`, 6 decimals)
- **Prompt versioning**: each prompt iteration is a separate module under `prompts/` with a `VERSION` string; estimates record which version produced them
- **Error recovery**: top-level exception handler in scan loop catches errors, notifies via Telegram, and continues
