"""Write and read audit-chain hashes on the AuditAnchor contract (Ethereum Sepolia).

Proposal FR9: only a 32-byte hash goes on-chain, never patient data or records.
Errors are re-raised as BlockchainError with fixed, safe messages, because the
original web3 exceptions can contain the RPC URL (which includes the API key).
"""

import json

from web3 import Web3

from settings import (
    ANCHOR_ABI_PATH,
    CONTRACT_ADDRESS,
    ETHERSCAN_URL,
    SEPOLIA_CHAIN_ID,
    SEPOLIA_RPC_URL,
    WALLET_PRIVATE_KEY,
)


class BlockchainError(Exception):
    """Failure talking to the chain. The message is safe to show to users."""


def is_configured():
    return bool(SEPOLIA_RPC_URL and CONTRACT_ADDRESS and WALLET_PRIVATE_KEY)


def tx_url(tx_hash):
    return f"{ETHERSCAN_URL}/tx/{tx_hash}"


def _contract():
    """Connect to Sepolia and return (web3, contract). Raises BlockchainError."""
    if not is_configured():
        raise BlockchainError("Blockchain anchoring is not configured on this server.")
    try:
        w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL, request_kwargs={"timeout": 20}))
        if w3.eth.chain_id != SEPOLIA_CHAIN_ID:
            raise BlockchainError("The configured RPC endpoint is not Ethereum Sepolia.")
        abi = json.loads(ANCHOR_ABI_PATH.read_text())
        contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)
        return w3, contract
    except BlockchainError:
        raise
    except Exception:
        raise BlockchainError("Could not connect to the Sepolia network.") from None


def anchor_hash(hex_hash):
    """Store one 32-byte hash on-chain. Returns {onchain_id, tx_hash, block_number}.

    Signs a plain transaction with the server's key and waits for it to be mined
    (Sepolia makes a block about every 12 seconds).
    """
    w3, contract = _contract()
    try:
        account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
        value = bytes.fromhex(hex_hash)
        # Dry run first: if the contract would reject it ("not authorised"), stop before paying gas
        contract.functions.anchor(value).call({"from": account.address})
        tx = contract.functions.anchor(value).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": SEPOLIA_CHAIN_ID,
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    except Exception:
        raise BlockchainError("The anchor transaction could not be sent or confirmed.") from None

    if receipt.status != 1:
        raise BlockchainError("The anchor transaction was mined but reverted.")
    # The contract's HashAnchored event tells us the id it assigned
    events = contract.events.HashAnchored().process_receipt(receipt)
    if not events:
        raise BlockchainError("The anchor transaction emitted no HashAnchored event.")
    return {
        "onchain_id": int(events[0]["args"]["id"]),
        "tx_hash": "0x" + tx_hash.hex().removeprefix("0x"),
        "block_number": receipt.blockNumber,
    }


def read_anchor(onchain_id):
    """Return the hash stored on-chain under `onchain_id`, as 64 hex characters."""
    _, contract = _contract()
    try:
        value = contract.functions.hashes(onchain_id).call()
    except Exception:
        raise BlockchainError("Could not read the anchored hash from the contract.") from None
    return value.hex().removeprefix("0x")
