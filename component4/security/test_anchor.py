"""Send ONE test anchor to the AuditAnchor contract on Sepolia.

Usage:  python component4/security/test_anchor.py
Reads SEPOLIA_RPC_URL, CONTRACT_ADDRESS and WALLET_PRIVATE_KEY from component4/.env.

The transaction is signed here with the private key (a plain transaction), the same
way the API will sign anchors later. This avoids MetaMask's smart-account wrapper.

AuditAnchor.abi.json is the ABI exported from Remix for AuditAnchor.sol (same folder).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")  # component4/.env

SEPOLIA_CHAIN_ID = 11155111

w3 = Web3(Web3.HTTPProvider(os.environ["SEPOLIA_RPC_URL"]))
abi = json.loads((HERE / "AuditAnchor.abi.json").read_text())
contract = w3.eth.contract(address=Web3.to_checksum_address(os.environ["CONTRACT_ADDRESS"].strip()), abi=abi)
acct = w3.eth.account.from_key(os.environ["WALLET_PRIVATE_KEY"].strip())  # never printed

print("Owner on-chain:", contract.functions.owner().call())
print("My address:    ", acct.address)
print("Anchors before:", contract.functions.count().call())

# A recognisable dummy value (32 bytes of 0x11): this is a connectivity test, not a real audit hash
test_hash = bytes.fromhex("11" * 32)

# 1) Dry run: simulates the call without sending anything. If the contract would
#    reject it (e.g. "not authorised"), this raises with the reason and we stop here.
contract.functions.anchor(test_hash).call({"from": acct.address})
print("Dry run: OK")

# 2) Real transaction: build, sign locally with the private key, send, wait for it to be mined
tx = contract.functions.anchor(test_hash).build_transaction({
    "from": acct.address,
    "nonce": w3.eth.get_transaction_count(acct.address),
    "chainId": SEPOLIA_CHAIN_ID,
})
signed = acct.sign_transaction(tx)
raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction  # name differs between web3 versions
tx_hash = w3.eth.send_raw_transaction(raw)
print("Sent, waiting to be mined...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

cost = receipt.gasUsed * receipt.effectiveGasPrice
print("Status:", receipt.status, "(1 = success)")
print("Tx hash: 0x" + tx_hash.hex().removeprefix("0x"))
print("Block:", receipt.blockNumber, "| gas used:", receipt.gasUsed, "| cost:", w3.from_wei(cost, "ether"), "ETH")
print("Anchors after: ", contract.functions.count().call())
print("View it: https://sepolia.etherscan.io/tx/0x" + tx_hash.hex().removeprefix("0x"))
