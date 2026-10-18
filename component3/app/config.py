try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "AyurAI Component 3 Safety Assessment API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    PORT: int = 8003
    
    # Neo4j Settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Model Thresholds
    HIGH_RISK_THRESHOLD: float = 0.70
    CAUTION_THRESHOLD: float = 0.35
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
