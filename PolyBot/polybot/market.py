"""
Layer 1: Data and Market Access.
Wraps py-clob-client to fetch real-time prices, orderbooks, and market metadata
from the Polymarket CLOB API.
"""

import logging
from dataclasses import dataclass
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from polybot.config import PolymarketConfig

logger = logging.getLogger(__name__)


@dataclass
class MarketInfo:
    """Parsed market data for a single Polymarket market."""
    condition_id: str
    question: str
    token_id_yes: str
    token_id_no: str
    price_yes: float
    price_no: float
    volume: float
    active: bool


@dataclass
class OrderBookSnapshot:
    """Snapshot of an orderbook for one side of a market."""
    bids: list[tuple[float, float]]  # (price, size) pairs
    asks: list[tuple[float, float]]
    best_bid: float
    best_ask: float
    spread: float
    depth_usdc: float  # total liquidity in top 5 levels


class MarketClient:
    """
    Client for Polymarket CLOB API.
    Handles authentication, market discovery, and orderbook fetching.
    """

    def __init__(self, cfg: PolymarketConfig):
        # Build API credentials from config
        creds = ApiCreds(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            api_passphrase=cfg.api_passphrase,
        )
        self.client = ClobClient(
            host=cfg.host,
            key=cfg.private_key,
            chain_id=cfg.chain_id,
            creds=creds,
        )
        logger.info("MarketClient initialized for chain_id=%d", cfg.chain_id)

    def derive_api_credentials(self) -> dict:
        """
        One-time operation: derive API key/secret/passphrase from your private key.
        Save the returned values to your .env file.
        """
        creds = self.client.derive_api_key()
        logger.info("Derived API credentials successfully")
        return {
            "api_key": creds.api_key,
            "api_secret": creds.api_secret,
            "api_passphrase": creds.api_passphrase,
        }

    def get_markets(self, next_cursor: str = "") -> list[dict]:
        """Fetch paginated list of available markets."""
        response = self.client.get_markets(next_cursor=next_cursor)
        logger.info("Fetched %d markets", len(response.get("data", [])))
        return response.get("data", [])

    def get_market(self, condition_id: str) -> dict:
        """Fetch a single market by its condition ID."""
        return self.client.get_market(condition_id)

    def get_orderbook(self, token_id: str) -> OrderBookSnapshot:
        """
        Fetch current orderbook for a token (YES or NO side).
        Returns parsed snapshot with spread and depth metrics.
        """
        book = self.client.get_order_book(token_id)
        bids = [(float(b.price), float(b.size)) for b in book.bids] if book.bids else []
        asks = [(float(a.price), float(a.size)) for a in book.asks] if book.asks else []

        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 1.0
        spread = best_ask - best_bid

        # Sum top 5 levels of liquidity (price * size)
        depth = sum(p * s for p, s in bids[:5]) + sum(p * s for p, s in asks[:5])

        return OrderBookSnapshot(
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            depth_usdc=depth,
        )

    def get_price(self, token_id: str) -> float:
        """Get the current midpoint price for a token."""
        mid = self.client.get_midpoint(token_id)
        return float(mid)

    def get_open_orders(self) -> list[dict]:
        """Fetch all currently open orders for this account."""
        return self.client.get_orders()

    def parse_market(self, raw: dict) -> MarketInfo:
        """Parse raw market API response into a MarketInfo dataclass."""
        tokens = raw.get("tokens", [])
        # Tokens list: first is YES, second is NO
        yes_token = tokens[0] if len(tokens) > 0 else {}
        no_token = tokens[1] if len(tokens) > 1 else {}

        return MarketInfo(
            condition_id=raw.get("condition_id", ""),
            question=raw.get("question", ""),
            token_id_yes=yes_token.get("token_id", ""),
            token_id_no=no_token.get("token_id", ""),
            price_yes=float(yes_token.get("price", 0)),
            price_no=float(no_token.get("price", 0)),
            volume=float(raw.get("volume", 0)),
            active=raw.get("active", False),
        )
