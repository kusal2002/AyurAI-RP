import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.neo4j_client import Neo4jClient
from app.core.graph_service import GraphService
from scripts.seed_neo4j import build_cypher_statements


def test_neo4j_client_initialization_and_fallback():
    client = Neo4jClient()
    assert client is not None
    # Offline fallback behavior: is_connected returns False gracefully without throwing unhandled exceptions
    is_conn = client.is_connected
    assert isinstance(is_conn, bool)


def test_graph_service_returns_valid_stats():
    service = GraphService()
    stats = service.get_graph_stats()
    assert stats is not None
    assert "nodes" in stats
    assert "relationships" in stats
    assert stats["nodes"].get("Herb", 0) >= 30
    assert stats["nodes"].get("Drug", 0) >= 50
    assert stats["total_nodes"] > 100


def test_graph_service_finds_multi_hop_pathway():
    service = GraphService()
    # Test Yashtimadhu -> Glabridin -> CYP2C9 -> Warfarin pathway
    result = service.find_multi_hop_path("Yashtimadhu", "Warfarin")
    assert result is not None
    assert result["herb"] == "Yashtimadhu"
    assert result["drug"] == "Warfarin"
    assert result["direct_interaction_rule"] is not None
    assert "CYP2C9" in result["direct_interaction_rule"]["mechanism"] or len(result["pathways"]) > 0


def test_cypher_statement_generation():
    statements = build_cypher_statements()
    assert len(statements) >= 300
    # Verify constraints and MERGE statements exist
    assert any("CONSTRAINT" in s for s in statements)
    assert any("MERGE (h:Herb" in s for s in statements)
    assert any("MERGE (d:Drug" in s for s in statements)
    assert any("INTERACTS_WITH" in s for s in statements)
