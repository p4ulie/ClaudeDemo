"""
Layer 1/4: Blockchain interactions via web3.py.
Handles USDC.e balance checks, allowance verification, and token approvals
on Polygon via Alchemy RPC.
"""

import logging
from web3 import Web3
from polybot.config import BlockchainConfig

logger = logging.getLogger(__name__)

# Minimal ERC20 ABI for balance, allowance, and approve operations
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function",
    },
]


class BlockchainClient:
    """
    Polygon blockchain client for USDC.e balance and allowance operations.
    Uses web3.py with Alchemy RPC endpoint.
    """

    def __init__(self, cfg: BlockchainConfig, wallet_address: str):
        self.w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        self.wallet = Web3.to_checksum_address(wallet_address)
        self.usdc_decimals = cfg.usdc_decimals
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(cfg.usdc_address),
            abi=ERC20_ABI,
        )
        if self.w3.is_connected():
            logger.info("Connected to Polygon RPC (chain_id=%d)", self.w3.eth.chain_id)
        else:
            logger.error("Failed to connect to Polygon RPC at %s", cfg.rpc_url)

    def get_usdc_balance(self) -> float:
        """Get USDC.e balance in human-readable units (6 decimals)."""
        raw = self.usdc_contract.functions.balanceOf(self.wallet).call()
        balance = raw / (10 ** self.usdc_decimals)
        logger.debug("USDC.e balance: %.2f", balance)
        return balance

    def get_allowance(self, spender: str) -> float:
        """Check how much USDC.e the spender contract is approved to use."""
        spender_addr = Web3.to_checksum_address(spender)
        raw = self.usdc_contract.functions.allowance(self.wallet, spender_addr).call()
        return raw / (10 ** self.usdc_decimals)

    def approve_usdc(self, spender: str, amount_usdc: float, private_key: str) -> str:
        """
        Approve a spender contract to transfer USDC.e on our behalf.
        Returns the transaction hash.
        """
        spender_addr = Web3.to_checksum_address(spender)
        amount_raw = int(amount_usdc * (10 ** self.usdc_decimals))

        tx = self.usdc_contract.functions.approve(spender_addr, amount_raw).build_transaction({
            "from": self.wallet,
            "nonce": self.w3.eth.get_transaction_count(self.wallet),
            "gas": 100_000,
            "gasPrice": self.w3.eth.gas_price,
        })

        signed = self.w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info("USDC.e approval tx sent: %s", tx_hash.hex())
        return tx_hash.hex()

    def is_connected(self) -> bool:
        """Check if the RPC connection is alive."""
        return self.w3.is_connected()
