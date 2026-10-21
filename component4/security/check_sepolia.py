"""Connectivity check for Ethereum Sepolia (used later for audit-log anchoring).

Usage:  python component4/security/check_sepolia.py
Reads SEPOLIA_RPC_URL and WALLET_ADDRESS from component4/.env.
Never prints the RPC URL, because it contains the Alchemy API key.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

SEPOLIA_CHAIN_ID = 11155111  # Ethereum mainnet is 1

# component4/.env, found relative to this file, so it works from any folder
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

rpc_url = os.getenv("SEPOLIA_RPC_URL")
if not rpc_url:
    sys.exit("SEPOLIA_RPC_URL is not set in component4/.env")

w3 = Web3(Web3.HTTPProvider(rpc_url))
connected = w3.is_connected()
print("Connected:", connected)
if not connected:
    sys.exit("Could not reach the RPC endpoint (check the URL and your internet connection).")

chain_id = w3.eth.chain_id
print("Chain ID:", chain_id, "(Sepolia)" if chain_id == SEPOLIA_CHAIN_ID else "(NOT Sepolia - check the URL)")
print("Latest block:", w3.eth.block_number)

address = os.getenv("WALLET_ADDRESS", "").strip()
if not address:
    print("Balance: skipped - add WALLET_ADDRESS (your full 0x... address from MetaMask) to component4/.env")
elif not Web3.is_address(address):
    print("Balance: skipped - WALLET_ADDRESS is not a valid address (a full address is 0x + 40 hex characters)")
else:
    balance = w3.eth.get_balance(Web3.to_checksum_address(address))
    print("Balance:", w3.from_wei(balance, "ether"), "ETH (Sepolia test ETH, no real value)")
