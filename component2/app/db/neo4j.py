import os
from functools import lru_cache
from urllib.parse import urlsplit

from dotenv import load_dotenv
from neo4j import READ_ACCESS, Driver, GraphDatabase, unit_of_work
from neo4j.exceptions import (
    AuthError,
    ConfigurationError,
    DriverError,
    Neo4jError,
    ServiceUnavailable,
    SessionExpired,
)

load_dotenv()

# Schemes that use TLS. "+ssc" accepts self-signed certificates and is
# only appropriate for local development servers.
ENCRYPTED_SCHEMES = {"neo4j+s", "bolt+s", "neo4j+ssc", "bolt+ssc"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _env_seconds(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw)
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive number of seconds.")
    return value


def connection_settings() -> dict[str, float]:
    """Driver timeouts in seconds (environment-overridable)."""
    return {
        "connection_timeout": _env_seconds("C2_NEO4J_CONNECTION_TIMEOUT", 10.0),
        "connection_acquisition_timeout": _env_seconds(
            "C2_NEO4J_ACQUISITION_TIMEOUT", 15.0
        ),
        "max_transaction_retry_time": _env_seconds(
            "C2_NEO4J_MAX_RETRY_TIME", 10.0
        ),
    }


def query_timeout() -> float:
    """Server-side timeout applied to health and validation queries."""
    return _env_seconds("C2_NEO4J_QUERY_TIMEOUT", 15.0)


def _check_uri(uri: str) -> None:
    parts = urlsplit(uri)
    if parts.scheme not in ENCRYPTED_SCHEMES and parts.hostname not in LOCAL_HOSTS:
        # Never echo the URI: it identifies the database host.
        raise RuntimeError(
            "NEO4J_URI must use an encrypted scheme (neo4j+s:// or bolt+s://) "
            "for a non-local database."
        )


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
    _check_uri(uri)

    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        **connection_settings(),
    )


def verify_neo4j_connection() -> None:
    """Raise an exception if Neo4j is unreachable."""
    get_neo4j_driver().verify_connectivity()


def check_neo4j(driver: Driver | None = None) -> dict:
    """Classify database reachability with a read-only query.

    Returns {"status", "detail", "encrypted"} where status is one of
    healthy, not_configured, misconfigured, auth_failed, unreachable or
    query_failed. Messages never contain the URI, user name or password.
    A healthy result only means the server answered `RETURN 1`; it says
    nothing about the schema or the knowledge stored in the graph.
    """
    uri = os.getenv("NEO4J_URI") or ""
    encrypted = urlsplit(uri).scheme in ENCRYPTED_SCHEMES if uri else None
    result = {"status": "healthy", "detail": "read-only query succeeded",
              "encrypted": encrypted}
    try:
        db = driver if driver is not None else get_neo4j_driver()
    except RuntimeError as exc:
        missing = "missing" in str(exc)
        return {**result, "status": "not_configured" if missing else "misconfigured",
                "detail": "Neo4j settings are missing" if missing
                else "Neo4j settings are invalid (see server log)"}
    try:
        @unit_of_work(timeout=query_timeout())
        def ping(tx):
            return tx.run("RETURN 1 AS ok").single()

        with db.session(default_access_mode=READ_ACCESS) as session:
            value = session.execute_read(ping)
        if value is None or value["ok"] != 1:
            return {**result, "status": "query_failed", "detail": "unexpected query result"}
    except AuthError:
        return {**result, "status": "auth_failed", "detail": "authentication was rejected"}
    except (ServiceUnavailable, SessionExpired, OSError):
        return {**result, "status": "unreachable", "detail": "database server could not be reached"}
    except ConfigurationError:
        return {**result, "status": "misconfigured", "detail": "driver configuration is invalid"}
    except (Neo4jError, DriverError) as exc:
        return {**result, "status": "query_failed",
                "detail": f"read query failed ({type(exc).__name__})"}
    return result


def close_neo4j_driver() -> None:
    """Close the driver and clear the cached instance."""
    if get_neo4j_driver.cache_info().currsize:
        get_neo4j_driver().close()
        get_neo4j_driver.cache_clear()
