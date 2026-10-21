
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Manual connectivity check against the configured AuraDB instance.
# Run it explicitly with `python test_neo4j_connection.py`. The check lives
# in main() so that importing this module (for example during pytest
# collection) never opens a network connection.


def main() -> None:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise RuntimeError(
            "Missing Neo4j settings. Check NEO4J_URI, "
            "NEO4J_USERNAME, and NEO4J_PASSWORD in .env."
        )

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password),
    )

    try:
        driver.verify_connectivity()
        print("SUCCESS: Connected to Neo4j AuraDB!")
    except Exception as exc:
        print(f"CONNECTION FAILED: {type(exc).__name__}")
        print("Check your AuraDB status, .env settings, and network connection.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
