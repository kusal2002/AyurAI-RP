import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
elif (BASE_DIR.parent / ".env").exists():
    load_dotenv(BASE_DIR.parent / ".env")

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AyurAI Component 3 Safety Assessment API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    PORT: int = int(os.getenv("PORT", "8003"))
    
    # Neo4j Settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    
    # Model Thresholds
    HIGH_RISK_THRESHOLD: float = float(os.getenv("HIGH_RISK_THRESHOLD", "0.70"))
    CAUTION_THRESHOLD: float = float(os.getenv("CAUTION_THRESHOLD", "0.35"))
    
    class Config:
        env_file = str(ENV_PATH)
        extra = "ignore"


settings = Settings()

