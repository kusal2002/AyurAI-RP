"""Configuration read from environment variables (or component4/.env)."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

COMPONENT_DIR = Path(__file__).resolve().parent.parent  # component4/
load_dotenv(COMPONENT_DIR / ".env")

# PostgreSQL in the proposal, e.g.
#   DATABASE_URL=postgresql+psycopg2://ayurai:password@localhost:5432/ayurai_c4
# Falls back to a local SQLite file so the API also runs before Postgres is installed.
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{COMPONENT_DIR / 'api' / 'c4_dev.sqlite3'}"

# Secret used to sign JWTs. If none is configured, a random one is made per
# process (safe, but every restart logs everybody out).
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Shared key that Component 2 / 3 services send to post audit events.
SERVICE_API_KEY = os.getenv("C4_SERVICE_API_KEY", "")

RESULTS_DIR = COMPONENT_DIR / "results"

# ---------- Component 2's knowledge graph (Neo4j AuraDB), for FAKL ----------
# Full-access credentials owned by Component 2: Component 4 only ever READS.
C2_NEO4J_URI = os.getenv("C2_NEO4J_URI", "")
C2_NEO4J_USERNAME = os.getenv("C2_NEO4J_USERNAME", "")
C2_NEO4J_PASSWORD = os.getenv("C2_NEO4J_PASSWORD", "")
C2_NEO4J_DATABASE = os.getenv("C2_NEO4J_DATABASE", "") or None   # None = server default

# ---------- Blockchain anchoring (Ethereum Sepolia testnet) ----------
# All optional: without them the API runs normally and anchoring returns 503.
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "")          # contains the Alchemy key: never log it
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "").strip()  # deployed AuditAnchor contract
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "").strip()  # signs anchor transactions: never log it
SEPOLIA_CHAIN_ID = 11155111
ETHERSCAN_URL = "https://sepolia.etherscan.io"
ANCHOR_ABI_PATH = COMPONENT_DIR / "security" / "AuditAnchor.abi.json"
