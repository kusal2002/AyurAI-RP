import os
from functools import lru_cache

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

load_dotenv()


@lru_cache(maxsize=1)
def get_neo4j_driver() -> Driver:
    """Create and reuse the Neo4j driver."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise RuntimeError(
            "Neo4j configuration is missing. "
            "Check NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD."
        )

    return GraphDatabase.driver(
        uri,
        auth=(username, password),
    )


def verify_neo4j_connection() -> None:
    """Raise an exception if Neo4j is unreachable."""
    get_neo4j_driver().verify_connectivity()


def close_neo4j_driver() -> None:
    """Close the driver and clear the cached instance."""
    if get_neo4j_driver.cache_info().currsize:
        get_neo4j_driver().close()
        get_neo4j_driver.cache_clear()
