"""
Layer 3: Math Engine.
Implements core trading mathematics:
- Expected Value calculation with edge filtering (>5% threshold)
- Kelly Criterion for position sizing as fraction of bankroll
- Bayesian Updating for probability revision when new evidence arrives
- Log Returns for P&L tracking across positions
All operations use NumPy for fast array math.
"""

import logging
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Output of the math engine: whether and how much to trade."""
    should_trade: bool
    side: str  # "BUY" or "SELL"
    edge: float  # expected edge as fraction of cost
    kelly_fraction: float  # fraction of bankroll to allocate
    position_size_usdc: float  # dollar amount to trade
    expected_value: float  # EV per unit


# --- Expected Value ---

def compute_edge(p_estimated: float, market_price: float) -> float:
    """
    Compute trading edge as fraction of cost.
    edge = (p - m) / m for buying YES at price m with estimated prob p.
    Positive edge means the market undervalues the outcome.
    """
    if market_price <= 0 or market_price >= 1:
        return 0.0
    return (p_estimated - market_price) / market_price


def compute_ev(p_estimated: float, market_price: float) -> float:
    """
    Expected value per contract for buying YES at market_price.
    EV = p * (1 - m) - (1 - p) * m = p - m
    """
    return p_estimated - market_price


# --- Kelly Criterion ---

def kelly_fraction(p_estimated: float, market_price: float, fractional: float = 0.5) -> float:
    """
    Kelly Criterion for binary prediction market position sizing.
    f* = (p - m) / (1 - m), then scaled by fractional Kelly multiplier.
    Half-Kelly (0.5) is the default for safer risk management.

    Returns fraction of bankroll to allocate. Negative = bet against (sell YES).
    """
    if market_price <= 0 or market_price >= 1:
        return 0.0
    f_star = (p_estimated - market_price) / (1 - market_price)
    f_star *= fractional
    return float(np.clip(f_star, -1.0, 1.0))


# --- Bayesian Updating ---

def prob_to_log_odds(p: float) -> float:
    """Convert probability to log-odds for numerically stable Bayesian updates."""
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(np.log(p / (1 - p)))


def log_odds_to_prob(lo: float) -> float:
    """Convert log-odds back to probability."""
    return float(1.0 / (1.0 + np.exp(-lo)))


def bayesian_update(prior: float, likelihood_true: float, likelihood_false: float) -> float:
    """
    Single Bayesian update on a binary hypothesis using log-odds form.
    prior: P(H) before evidence
    likelihood_true: P(Evidence | H is true)
    likelihood_false: P(Evidence | H is false)
    Returns: posterior P(H | Evidence)
    """
    lo = prob_to_log_odds(prior)
    llr = np.log(likelihood_true / likelihood_false)
    return log_odds_to_prob(lo + llr)


def bayesian_update_sequential(prior: float, evidence: list[tuple[float, float]]) -> float:
    """
    Apply multiple Bayesian updates sequentially.
    evidence: list of (likelihood_if_true, likelihood_if_false) tuples.
    Each update's posterior becomes the next update's prior.
    """
    lo = prob_to_log_odds(prior)
    for lt, lf in evidence:
        lo += np.log(lt / lf)
    return log_odds_to_prob(lo)


# --- Log Returns ---

def log_returns(entry_prices: np.ndarray, exit_prices: np.ndarray) -> np.ndarray:
    """
    Compute log returns per position.
    Log returns are additive across time, making portfolio math clean.
    Uses a floor of 1e-10 to avoid -inf on total losses (exit_price=0).
    """
    exit_floored = np.maximum(exit_prices, 1e-10)
    return np.log(exit_floored / entry_prices)


def portfolio_pnl(
    bankroll: float,
    entry_prices: np.ndarray,
    exit_prices: np.ndarray,
    allocations: np.ndarray,
) -> dict:
    """
    Calculate P&L across multiple positions using log returns.
    bankroll: starting capital
    entry_prices: price paid per contract
    exit_prices: settlement or current price per contract
    allocations: fraction of bankroll in each position (from Kelly)
    Returns dict with per-position and aggregate P&L.
    """
    lr = log_returns(entry_prices, exit_prices)
    dollars_in = bankroll * allocations
    n_contracts = dollars_in / entry_prices
    dollar_pnl = n_contracts * (exit_prices - entry_prices)
    portfolio_log_return = float(np.sum(allocations * lr))

    return {
        "log_returns": lr,
        "dollar_pnl": dollar_pnl,
        "total_dollar_pnl": float(np.sum(dollar_pnl)),
        "portfolio_log_return": portfolio_log_return,
        "final_bankroll": bankroll * np.exp(portfolio_log_return),
    }


# --- Trade Signal Generator ---

def generate_signal(
    p_estimated: float,
    market_price: float,
    bankroll: float,
    min_edge: float = 0.05,
    kelly_mult: float = 0.5,
    max_position: float = 500.0,
) -> TradeSignal:
    """
    Full pipeline: compute EV, check edge threshold, size via Kelly.
    Combines all math components into a single trade/no-trade decision.
    """
    edge = compute_edge(p_estimated, market_price)
    ev = compute_ev(p_estimated, market_price)
    kf = kelly_fraction(p_estimated, market_price, fractional=kelly_mult)

    # Determine side: positive edge = buy YES, negative = sell YES
    side = "BUY" if edge > 0 else "SELL"
    abs_edge = abs(edge)

    # Only trade if edge exceeds minimum threshold
    if abs_edge < min_edge:
        return TradeSignal(
            should_trade=False, side=side, edge=edge,
            kelly_fraction=kf, position_size_usdc=0.0, expected_value=ev,
        )

    # Position size: Kelly fraction of bankroll, capped at max_position
    raw_size = bankroll * abs(kf)
    position_size = min(raw_size, max_position)

    logger.info(
        "Signal: %s edge=%.2f%% kelly=%.3f size=$%.2f",
        side, abs_edge * 100, kf, position_size,
    )

    return TradeSignal(
        should_trade=True,
        side=side,
        edge=edge,
        kelly_fraction=kf,
        position_size_usdc=position_size,
        expected_value=ev,
    )
