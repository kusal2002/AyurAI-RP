import logging
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    Driver = None
    NEO4J_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Singleton Neo4j database client with resilient local fallback."""

    _instance: Optional["Neo4jClient"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._driver: Optional[Any] = None
        self._connected: bool = False
        self._initialized = True
        self.connect()

    def connect(self) -> bool:
        """Attempts to establish connection to Neo4j instance."""
        if not NEO4J_AVAILABLE:
            logger.warning("Neo4j python package not installed. Running in offline/fallback mode.")
            self._connected = False
            return False

        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=3.0,
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._connected = True
            logger.info("Successfully connected to Neo4j database at %s", settings.NEO4J_URI)
            return True
        except Exception as e:
            logger.warning(
                "Could not connect to Neo4j at %s (%s). System will use local JSON cache.",
                settings.NEO4J_URI,
                str(e),
            )
            self._connected = False
            self._driver = None
            return False

    @property
    def is_connected(self) -> bool:
        """Returns True if live Neo4j driver is active and connected."""
        return self._connected and self._driver is not None

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher read query and returns list of records as dicts."""
        if not self.is_connected:
            return []

        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error("Error executing Cypher query: %s", str(e))
            return []

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a Cypher write transaction."""
        if not self.is_connected:
            return None

        try:
            with self._driver.session() as session:
                return session.execute_write(lambda tx: tx.run(query, parameters or {}).consume())
        except Exception as e:
            logger.error("Error executing Cypher write transaction: %s", str(e))
            return None

    def close(self):
        """Closes the Neo4j driver connection."""
        if self._driver is not None:
            self._driver.close()
            self._connected = False
            self._driver = None
            logger.info("Neo4j driver connection closed.")
