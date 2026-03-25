"""
Tests for Layer 3: Math Engine.
Covers expected value, Kelly Criterion, Bayesian updating, log returns,
and the full trade signal pipeline.
"""

import numpy as np
import pytest
from polybot.math_engine import (
    compute_edge,
    compute_ev,
    kelly_fraction,
    bayesian_update,
    bayesian_update_sequential,
    log_returns,
    portfolio_pnl,
    generate_signal,
    prob_to_log_odds,
    log_odds_to_prob,
)


# --- Expected Value Tests ---

class TestExpectedValue:
    """Tests for EV and edge computation."""

    def test_positive_edge(self):
        # Estimated prob 70%, market at 55% => positive edge
        edge = compute_edge(0.70, 0.55)
        assert edge == pytest.approx(0.2727, abs=0.001)

    def test_zero_edge(self):
        # Estimated matches market => no edge
        edge = compute_edge(0.50, 0.50)
        assert edge == pytest.approx(0.0)

    def test_negative_edge(self):
        # Market overpriced relative to our estimate
        edge = compute_edge(0.40, 0.55)
        assert edge < 0

    def test_ev_simple(self):
        # EV = p - m
        ev = compute_ev(0.70, 0.55)
        assert ev == pytest.approx(0.15)

    def test_boundary_market_price(self):
        # Edge cases: market price at 0 or 1
        assert compute_edge(0.5, 0.0) == 0.0
        assert compute_edge(0.5, 1.0) == 0.0


# --- Kelly Criterion Tests ---

class TestKellyCriterion:
    """Tests for Kelly fraction position sizing."""

    def test_positive_edge_buy(self):
        # p=0.70, m=0.55, half-Kelly
        f = kelly_fraction(0.70, 0.55, fractional=0.5)
        # Full Kelly: (0.70 - 0.55) / (1 - 0.55) = 0.333
        # Half Kelly: 0.167
        assert f == pytest.approx(0.1667, abs=0.001)

    def test_no_edge_returns_zero(self):
        # When p == m, Kelly is 0
        f = kelly_fraction(0.50, 0.50)
        assert f == pytest.approx(0.0)

    def test_full_kelly(self):
        # Full Kelly (fractional=1.0) is more aggressive
        f = kelly_fraction(0.70, 0.55, fractional=1.0)
        assert f == pytest.approx(0.3333, abs=0.001)

    def test_negative_edge_sell(self):
        # When p < m, fraction should be negative (sell signal)
        f = kelly_fraction(0.30, 0.55, fractional=0.5)
        assert f < 0

    def test_clamp_to_bounds(self):
        # Extreme inputs should be clamped to [-1, 1]
        f = kelly_fraction(0.99, 0.01, fractional=1.0)
        assert f <= 1.0
        f = kelly_fraction(0.01, 0.99, fractional=1.0)
        assert f >= -1.0


# --- Bayesian Updating Tests ---

class TestBayesianUpdate:
    """Tests for Bayesian probability updating."""

    def test_strong_positive_evidence(self):
        # Prior 50%, strong positive evidence
        posterior = bayesian_update(0.50, likelihood_true=0.80, likelihood_false=0.30)
        assert posterior == pytest.approx(0.7273, abs=0.001)

    def test_neutral_evidence(self):
        # Equal likelihoods should not change the prior
        posterior = bayesian_update(0.60, likelihood_true=0.50, likelihood_false=0.50)
        assert posterior == pytest.approx(0.60, abs=0.001)

    def test_sequential_updates(self):
        # Two sequential updates should match chained single updates
        evidence = [(0.80, 0.30), (0.40, 0.70)]
        seq = bayesian_update_sequential(0.50, evidence)

        # Manual chain
        p1 = bayesian_update(0.50, 0.80, 0.30)
        p2 = bayesian_update(p1, 0.40, 0.70)
        assert seq == pytest.approx(p2, abs=0.0001)

    def test_log_odds_roundtrip(self):
        # Converting to log odds and back should preserve the value
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            lo = prob_to_log_odds(p)
            p_back = log_odds_to_prob(lo)
            assert p_back == pytest.approx(p, abs=1e-6)

    def test_extreme_evidence(self):
        # Very strong evidence should push posterior toward 1
        posterior = bayesian_update(0.50, likelihood_true=0.99, likelihood_false=0.01)
        assert posterior > 0.98


# --- Log Returns Tests ---

class TestLogReturns:
    """Tests for log return and portfolio P&L calculations."""

    def test_simple_log_return(self):
        # Buy at 0.50, sell at 1.00 => ln(1.0/0.5) = 0.693
        lr = log_returns(np.array([0.50]), np.array([1.00]))
        assert lr[0] == pytest.approx(0.6931, abs=0.001)

    def test_loss_log_return(self):
        # Total loss (exit=0) should use floor to avoid -inf
        lr = log_returns(np.array([0.50]), np.array([0.0]))
        assert np.isfinite(lr[0])
        assert lr[0] < -10  # Very negative but finite

    def test_portfolio_pnl_basic(self):
        # Two positions: one win, one loss
        result = portfolio_pnl(
            bankroll=10000,
            entry_prices=np.array([0.50, 0.60]),
            exit_prices=np.array([1.00, 0.00]),
            allocations=np.array([0.10, 0.10]),
        )
        # Win: 0.10 * 10000 / 0.50 * (1.0 - 0.5) = $1000
        assert result["dollar_pnl"][0] == pytest.approx(1000.0)
        # Loss: 0.10 * 10000 / 0.60 * (0.0 - 0.6) = -$1000
        assert result["dollar_pnl"][1] == pytest.approx(-1000.0, abs=1.0)

    def test_portfolio_no_change(self):
        # If exit == entry, P&L should be 0
        result = portfolio_pnl(
            bankroll=5000,
            entry_prices=np.array([0.50]),
            exit_prices=np.array([0.50]),
            allocations=np.array([0.20]),
        )
        assert result["total_dollar_pnl"] == pytest.approx(0.0)
        assert result["portfolio_log_return"] == pytest.approx(0.0)


# --- Trade Signal Generator Tests ---

class TestGenerateSignal:
    """Tests for the full signal generation pipeline."""

    def test_trade_with_high_edge(self):
        # 70% estimate vs 55% market = 27% edge > 5% threshold
        signal = generate_signal(
            p_estimated=0.70,
            market_price=0.55,
            bankroll=10000,
            min_edge=0.05,
            kelly_mult=0.5,
            max_position=500,
        )
        assert signal.should_trade is True
        assert signal.side == "BUY"
        assert signal.edge > 0.05
        assert signal.position_size_usdc > 0
        assert signal.position_size_usdc <= 500

    def test_no_trade_low_edge(self):
        # 52% estimate vs 50% market = 4% edge < 5% threshold
        signal = generate_signal(
            p_estimated=0.52,
            market_price=0.50,
            bankroll=10000,
            min_edge=0.05,
        )
        assert signal.should_trade is False
        assert signal.position_size_usdc == 0

    def test_position_capped_at_max(self):
        # Very high edge should still cap at max_position
        signal = generate_signal(
            p_estimated=0.95,
            market_price=0.20,
            bankroll=100000,
            max_position=500,
        )
        assert signal.should_trade is True
        assert signal.position_size_usdc <= 500

    def test_sell_signal(self):
        # Market overpriced: 30% estimate vs 60% market
        signal = generate_signal(
            p_estimated=0.30,
            market_price=0.60,
            bankroll=10000,
            min_edge=0.05,
        )
        assert signal.should_trade is True
        assert signal.side == "SELL"
        assert signal.edge < 0
