# PolyBot

An autonomous trading bot for [Polymarket](https://polymarket.com) prediction markets. It scans markets, uses AI (Claude) to estimate probabilities, applies mathematical models to find profitable trades, and executes them automatically. You get real-time notifications on your phone via Telegram.

---

## Table of Contents

- [How It Works](#how-it-works)
- [What You Need Before Starting](#what-you-need-before-starting)
- [Step 1: Install Python](#step-1-install-python)
- [Step 2: Download PolyBot](#step-2-download-polybot)
- [Step 3: Install Dependencies](#step-3-install-dependencies)
- [Step 4: Set Up Your Accounts](#step-4-set-up-your-accounts)
  - [4a: Polygon Wallet](#4a-polygon-wallet)
  - [4b: Polymarket API](#4b-polymarket-api)
  - [4c: Alchemy (Blockchain Access)](#4c-alchemy-blockchain-access)
  - [4d: Claude API (AI Brain)](#4d-claude-api-ai-brain)
  - [4e: Telegram Bot (Notifications)](#4e-telegram-bot-notifications)
- [Step 5: Configure PolyBot](#step-5-configure-polybot)
- [Step 6: Run PolyBot](#step-6-run-polybot)
- [Step 7: Run Tests](#step-7-run-tests)
- [Deploy on a Remote Server (VPS)](#deploy-on-a-remote-server-vps)
  - [Choose a VPS Provider](#choose-a-vps-provider)
  - [Connect to Your Server](#connect-to-your-server)
  - [Install Everything on the Server](#install-everything-on-the-server)
  - [Set Up PolyBot as a Service](#set-up-polybot-as-a-service)
  - [Managing the Bot on Your Server](#managing-the-bot-on-your-server)
- [Trading Parameters Explained](#trading-parameters-explained)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

---

## How It Works

PolyBot runs a continuous loop:

1. **Scans** all active markets on Polymarket
2. **Asks Claude AI** to estimate the true probability of each outcome
3. **Calculates** whether the market price offers enough edge (default: >5%)
4. **Sizes the position** using the Kelly Criterion (half-Kelly for safety)
5. **Executes the trade** with slippage protection
6. **Sends you a Telegram notification** with the trade details

The bot tracks all positions in a local SQLite database and logs every decision with timestamps.

---

## What You Need Before Starting

- A computer (Windows, Mac, or Linux)
- An internet connection
- About 30 minutes for the initial setup
- Some USDC.e tokens on the Polygon blockchain (this is what the bot trades with)

You will create free accounts on several services. The only costs are:
- **Claude API** — pay per use, typically a few cents per market scan
- **USDC.e on Polygon** — the money the bot trades with (you control how much)
- **VPS** (optional) — ~$8/month if you want the bot to run 24/7

---

## Step 1: Install Python

PolyBot requires **Python 3.11 or newer**.

### Windows

1. Go to https://www.python.org/downloads/
2. Click the big yellow "Download Python" button
3. Run the installer
4. **Important**: Check the box that says "Add Python to PATH" at the bottom of the installer
5. Click "Install Now"

To verify, open a terminal (search for "Terminal" or "Command Prompt" in the Start menu) and type:

```bash
python --version
```

You should see something like `Python 3.12.x` or higher.

### Mac

1. Go to https://www.python.org/downloads/
2. Download and run the macOS installer
3. Follow the prompts

Or if you have Homebrew:

```bash
brew install python@3.12
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

---

## Step 2: Download PolyBot

### Option A: Using Git (recommended)

If you have Git installed:

```bash
git clone https://github.com/p4ulie/ClaudeDemo.git
cd ClaudeDemo/PolyBot
```

### Option B: Download ZIP

1. Go to the GitHub repository page
2. Click the green "Code" button
3. Click "Download ZIP"
4. Extract the ZIP file
5. Open a terminal and navigate to the `PolyBot` folder inside the extracted files

---

## Step 3: Install Dependencies

In your terminal, make sure you are inside the `PolyBot` folder, then run:

```bash
pip install -r requirements.txt
```

This downloads all the libraries PolyBot needs. It may take a minute or two.

> **Tip**: If `pip` doesn't work, try `pip3` instead. On some systems, Python 3 uses `pip3`.

---

## Step 4: Set Up Your Accounts

PolyBot connects to several external services. You need to create accounts and get API keys for each one. This is a one-time setup.

### 4a: Polygon Wallet

You need an Ethereum-compatible wallet with USDC.e on the Polygon network. This is what the bot uses to trade.

1. Install [MetaMask](https://metamask.io/) browser extension (or any Ethereum wallet)
2. Create a new wallet or use an existing one
3. **Write down your private key** — you will need it for PolyBot
   - In MetaMask: click the three dots next to your account → Account Details → Show Private Key
4. Add the Polygon network to MetaMask:
   - Network Name: `Polygon`
   - RPC URL: `https://polygon-rpc.com`
   - Chain ID: `137`
   - Currency Symbol: `MATIC`
5. Transfer some USDC.e to your wallet on Polygon
   - You can bridge from Ethereum using the [Polygon Bridge](https://portal.polygon.technology/bridge)
   - Or buy directly on an exchange that supports Polygon withdrawals

> **Security Warning**: Your private key gives full access to your wallet. Never share it with anyone. The `.env` file where you store it is excluded from Git via `.gitignore`.

### 4b: Polymarket API

1. Go to https://polymarket.com and create an account
2. Connect your wallet
3. PolyBot can derive your API credentials automatically. After configuring your private key (Step 5), run:

```bash
python -c "
from polybot.config import Config
from polybot.market import MarketClient
cfg = Config()
client = MarketClient(cfg.polymarket)
creds = client.derive_api_credentials()
print('Add these to your .env file:')
print(f'POLYMARKET_API_KEY={creds[\"api_key\"]}')
print(f'POLYMARKET_API_SECRET={creds[\"api_secret\"]}')
print(f'POLYMARKET_API_PASSPHRASE={creds[\"api_passphrase\"]}')
"
```

4. Copy the three values into your `.env` file (see Step 5)

### 4c: Alchemy (Blockchain Access)

Alchemy provides access to the Polygon blockchain so the bot can check your balance.

1. Go to https://www.alchemy.com/ and create a free account
2. Click "Create new app"
3. Select **Polygon** as the network
4. Give it any name (e.g., "PolyBot")
5. Click "Create app"
6. On the app page, click "API Key" and copy the HTTPS URL
   - It looks like: `https://polygon-mainnet.g.alchemy.com/v2/your-key-here`

### 4d: Claude API (AI Brain)

Claude is the AI that estimates market probabilities.

1. Go to https://console.anthropic.com/ and create an account
2. Go to "API Keys" in the left sidebar
3. Click "Create Key"
4. Copy the key — it starts with `sk-ant-`
5. Add a payment method in the "Billing" section (you pay per API call, typically a few cents per scan)

### 4e: Telegram Bot (Notifications)

The bot sends trade notifications to your Telegram.

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts to name your bot
4. BotFather gives you a **bot token** — copy it (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
5. Now find your **chat ID**:
   - Search for `@userinfobot` on Telegram
   - Send it any message
   - It replies with your chat ID (a number like `123456789`)

---

## Step 5: Configure PolyBot

1. Copy the example config file:

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

2. Open `.env` in any text editor (Notepad, VS Code, nano, etc.)

3. Fill in your values:

```env
# Your wallet private key (from Step 4a)
POLYMARKET_PRIVATE_KEY=0xYourPrivateKeyHere

# Polymarket API credentials (from Step 4b)
POLYMARKET_API_KEY=your-api-key
POLYMARKET_API_SECRET=your-api-secret
POLYMARKET_API_PASSPHRASE=your-api-passphrase

# Alchemy RPC URL (from Step 4c)
ALCHEMY_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/your-key-here

# Claude API key (from Step 4d)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Telegram (from Step 4e)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789

# Trading parameters (you can adjust these later)
MIN_EDGE=0.05
KELLY_FRACTION=0.5
MAX_SLIPPAGE=0.02
SCAN_INTERVAL_SECONDS=60
MAX_POSITION_USDC=500
BANKROLL_USDC=10000
```

4. Save the file.

> **Important**: The `.env` file contains sensitive information. It is already listed in `.gitignore` so it won't be uploaded to GitHub.

---

## Step 6: Run PolyBot

```bash
python -m polybot.bot
```

The bot will:
- Connect to all services
- Start scanning markets every 60 seconds (configurable)
- Send you a Telegram message: "PolyBot started"
- Log all activity to `polybot.log` and your terminal

To stop the bot, press `Ctrl+C`.

---

## Step 7: Run Tests

To verify everything is set up correctly (does not require API keys):

```bash
python -m pytest tests/ -v
```

You should see all 30 tests pass. These test the math engine and position tracker.

---

## Deploy on a Remote Server (VPS)

Running PolyBot on your own computer means it stops when you close your laptop. For 24/7 operation, deploy it on a VPS (Virtual Private Server). This costs about $5–8 per month.

### Choose a VPS Provider

Any Linux VPS with 1 GB RAM works. Popular options:
- [Hetzner](https://www.hetzner.com/cloud) — starts at €3.79/month (recommended, best value)
- [DigitalOcean](https://www.digitalocean.com/) — starts at $6/month
- [Vultr](https://www.vultr.com/) — starts at $6/month
- [Linode/Akamai](https://www.linode.com/) — starts at $5/month

When creating the server:
- **OS**: Ubuntu 24.04 LTS (or 22.04)
- **Plan**: The cheapest one (1 CPU, 1 GB RAM) is plenty
- **Region**: Choose one close to you for lower latency

After creating the server, the provider gives you an **IP address** and **root password** (or SSH key).

### Connect to Your Server

Open a terminal on your computer and connect via SSH:

```bash
ssh root@YOUR_SERVER_IP
```

Replace `YOUR_SERVER_IP` with the actual IP address. It will ask for the password you received from your VPS provider.

> **Windows**: You can use the built-in Terminal app, or download [PuTTY](https://putty.org/).

### Install Everything on the Server

Run these commands one by one on the server. Copy-paste each line:

```bash
# 1. Update the system
apt update && apt upgrade -y

# 2. Install Python and Git
apt install -y python3.12 python3.12-venv python3-pip git

# 3. Create a dedicated user for the bot (more secure than running as root)
useradd -m -s /bin/bash polybot

# 4. Create the project directory
mkdir -p /opt/polybot
chown polybot:polybot /opt/polybot

# 5. Switch to the polybot user
su - polybot

# 6. Download the code
git clone https://github.com/p4ulie/ClaudeDemo.git /opt/polybot/repo
cp -r /opt/polybot/repo/PolyBot/* /opt/polybot/
cp /opt/polybot/repo/PolyBot/.env.example /opt/polybot/
cp /opt/polybot/repo/PolyBot/.gitignore /opt/polybot/

# 7. Create a Python virtual environment (keeps things clean)
cd /opt/polybot
python3 -m venv .venv
source .venv/bin/activate

# 8. Install dependencies
pip install -r requirements.txt

# 9. Create the config file
cp .env.example .env
```

Now edit the `.env` file with your API keys:

```bash
nano .env
```

Fill in all the values (same as Step 5 above). When done:
- Press `Ctrl+X` to exit
- Press `Y` to save
- Press `Enter` to confirm

Verify the tests pass:

```bash
python -m pytest tests/ -v
```

Exit back to the root user:

```bash
exit
```

### Set Up PolyBot as a Service

A systemd service makes the bot start automatically when the server boots and restart if it crashes.

```bash
# 1. Copy the service file
cp /opt/polybot/polybot.service /etc/systemd/system/

# 2. Tell systemd about the new service
systemctl daemon-reload

# 3. Enable auto-start on boot
systemctl enable polybot

# 4. Start the bot now
systemctl start polybot

# 5. Check that it's running
systemctl status polybot
```

You should see `Active: active (running)` in green.

### Managing the Bot on Your Server

Here are the commands you will use to manage PolyBot once it's deployed:

```bash
# View live logs (press Ctrl+C to stop watching)
journalctl -u polybot -f

# View last 100 log lines
journalctl -u polybot -n 100

# Stop the bot
sudo systemctl stop polybot

# Start the bot
sudo systemctl start polybot

# Restart the bot (e.g., after changing config)
sudo systemctl restart polybot

# Check if the bot is running
sudo systemctl status polybot
```

**To update PolyBot** when new code is released:

```bash
# Switch to the polybot user
su - polybot

# Pull the latest code
cd /opt/polybot/repo
git pull

# Copy updated files
cp -r PolyBot/* /opt/polybot/
exit

# Restart the bot to apply changes
sudo systemctl restart polybot
```

---

## Trading Parameters Explained

These are set in your `.env` file. You can adjust them to match your risk tolerance.

| Parameter | Default | What It Does |
|-----------|---------|--------------|
| `MIN_EDGE` | `0.05` | Only trade when the estimated edge is above 5%. Higher = fewer but safer trades. |
| `KELLY_FRACTION` | `0.5` | Uses half-Kelly for position sizing. `1.0` = full Kelly (more aggressive), `0.25` = quarter Kelly (more conservative). |
| `MAX_SLIPPAGE` | `0.02` | Skip a trade if the price moved more than 2% from expected. Protects against thin orderbooks. |
| `SCAN_INTERVAL_SECONDS` | `60` | How often (in seconds) the bot scans all markets. Lower = more API calls. |
| `MAX_POSITION_USDC` | `500` | Maximum USDC to put into a single trade. |
| `BANKROLL_USDC` | `10000` | Your total trading bankroll. Kelly sizing is calculated as a fraction of this. |

---

## Architecture

```
Market Data ──→ AI Brain ──→ Math Engine ──→ Execution ──→ Telegram Alert
(Polymarket)    (Claude)    (Kelly/EV)     (GTC Order)    (Your Phone)
                                               │
                                          SQLite DB
                                       (Position Tracker)
```

| Layer | Files | Purpose |
|-------|-------|---------|
| 1. Data & Market Access | `market.py`, `blockchain.py` | Fetches prices, orderbooks, and on-chain USDC.e balance |
| 2. AI Brain | `brain.py`, `prompts/v1.py` | Claude estimates true probability per market |
| 3. Math Engine | `math_engine.py` | Expected value filter, Kelly sizing, Bayesian updating |
| 4. Execution | `execution.py`, `db.py` | Places GTC orders, tracks positions in SQLite |
| 5. Monitoring | `monitor.py` | Telegram alerts, `/dashboard` command |
| 6. Infrastructure | `bot.py`, `polybot.service` | Main async loop, systemd service |

---

## Troubleshooting

**"pip: command not found"**
Try `pip3` instead, or `python -m pip install -r requirements.txt`.

**"ModuleNotFoundError: No module named 'polybot'"**
Make sure you are running from inside the `PolyBot` directory, not a parent folder.

**"Failed to connect to Polygon RPC"**
Check that your `ALCHEMY_RPC_URL` in `.env` is correct and starts with `https://`.

**"Telegram send failed"**
Verify your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. You must send `/start` to your bot on Telegram first.

**Bot is running but no trades are placed**
This is normal. The bot only trades when it finds markets with enough edge (>5% by default). Check the logs: `journalctl -u polybot -f` or `polybot.log`.

**Tests fail**
Make sure you installed dependencies with `pip install -r requirements.txt`. Tests do not require API keys.
