
from app.db.schema import NODE_IDENTIFIERS, initialize_schema
from app.db.neo4j import get_neo4j_driver


def main() -> None:
    initialize_schema()
    print("Schema initialization: PASS")

    # Run twice to verify that initialization is repeatable.
    initialize_schema()
    print("Repeat initialization: PASS")

    driver = get_neo4j_driver()

    with driver.session() as session:
        result = session.run("SHOW CONSTRAINTS")
        constraints = list(result)

    expected_names = {
        f"{label.lower()}_id_unique"
        for label in NODE_IDENTIFIERS
    }
    actual_names = {record["name"] for record in constraints}
    missing = expected_names - actual_names

    if missing:
        raise RuntimeError(
            f"Missing uniqueness constraints: {sorted(missing)}"
        )

    print(f"Verified {len(expected_names)} uniqueness constraints.")


if __name__ == "__main__":
    try:
        main()
    finally:
        from app.db.neo4j import close_neo4j_driver

        close_neo4j_driver()
