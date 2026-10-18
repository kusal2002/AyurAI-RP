// ============================================================================
// AyurAI Component 3: Ayurvedic Safety Knowledge Graph Schema (Neo4j)
// Author: Ransika A D L (IT23308466)
// Project: AyurAI - Herb-Drug Interaction & Safety Prediction
// ============================================================================

// --- 1. UNIQUE CONSTRAINTS ---

CREATE CONSTRAINT herb_id_unique IF NOT EXISTS
FOR (h:Herb) REQUIRE h.id IS UNIQUE;

CREATE CONSTRAINT drug_id_unique IF NOT EXISTS
FOR (d:Drug) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT compound_name_unique IF NOT EXISTS
FOR (c:Compound) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT enzyme_name_unique IF NOT EXISTS
FOR (e:Enzyme) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT target_name_unique IF NOT EXISTS
FOR (t:Target) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT condition_name_unique IF NOT EXISTS
FOR (cond:Condition) REQUIRE cond.name IS UNIQUE;

CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (ev:Evidence) REQUIRE ev.id IS UNIQUE;

// --- 2. INDEXES FOR PERFORMANCE ---

CREATE INDEX herb_name_idx IF NOT EXISTS
FOR (h:Herb) ON (h.common_name);

CREATE INDEX herb_botanical_idx IF NOT EXISTS
FOR (h:Herb) ON (h.botanical_name);

CREATE INDEX drug_generic_name_idx IF NOT EXISTS
FOR (d:Drug) ON (d.generic_name);

CREATE INDEX drug_class_idx IF NOT EXISTS
FOR (d:Drug) ON (d.drug_class);

CREATE INDEX interaction_severity_idx IF NOT EXISTS
FOR ()-[r:INTERACTS_WITH]-() ON (r.severity);

// --- 3. SAMPLE MULTI-HOP CYPHER QUERY PATTERNS ---

// Multi-hop path from Herb -> Compound -> Enzyme <- Drug:
// MATCH path = (h:Herb)-[:CONTAINS_COMPOUND]->(c:Compound)-[r:INHIBITS|INDUCES]->(e:Enzyme)<-[:METABOLIZED_BY]-(d:Drug)
// WHERE toLower(h.common_name) = toLower($herb_name) AND toLower(d.generic_name) = toLower($drug_name)
// RETURN path;

// Target receptor overlap path:
// MATCH path = (h:Herb)-[:CONTAINS_COMPOUND]->(c:Compound)-[:BINDS_TO]->(t:Target)<-[:ACTS_ON]-(d:Drug)
// WHERE toLower(h.common_name) = toLower($herb_name) AND toLower(d.generic_name) = toLower($drug_name)
// RETURN path;
