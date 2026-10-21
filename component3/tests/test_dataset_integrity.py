import json
from pathlib import Path

from app.models.patient_context import PatientContext
from app.models.graph_entities import HerbEntity, DrugEntity, InteractionRelation

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def test_herbs_dataset_contains_at_least_30_entities():
    herbs_file = DATA_DIR / "herbs_anemia.json"
    assert herbs_file.exists(), "herbs_anemia.json does not exist"
    
    with open(herbs_file, "r", encoding="utf-8") as f:
        herbs = json.load(f)

    assert len(herbs) >= 30, f"Expected >= 30 herbs, got {len(herbs)}"

    ids = [h["id"] for h in herbs]
    assert len(ids) == len(set(ids)), "Duplicate herb IDs found in dataset"

    # Validate schema against Pydantic
    for h in herbs:
        model = HerbEntity(
            id=h["id"],
            common_name=h["common_name"],
            sanskrit_name=h["sanskrit_name"],
            botanical_name=h["botanical_name"],
            active_compounds=h.get("active_compounds", []),
            contraindications=h.get("contraindications", []),
            traditional_uses=h.get("traditional_uses", []),
        )
        assert model.common_name != ""


def test_pharma_drugs_dataset_contains_at_least_50_entities():
    drugs_file = DATA_DIR / "pharma_drugs.json"
    assert drugs_file.exists(), "pharma_drugs.json does not exist"

    with open(drugs_file, "r", encoding="utf-8") as f:
        drugs = json.load(f)

    assert len(drugs) >= 50, f"Expected >= 50 drugs, got {len(drugs)}"

    ids = [d["id"] for d in drugs]
    assert len(ids) == len(set(ids)), "Duplicate drug IDs found in dataset"

    # Validate against Pydantic
    for d in drugs:
        model = DrugEntity(
            id=d["id"],
            generic_name=d["generic_name"],
            brand_names=d.get("brand_names", []),
            drug_class=d["drug_class"],
            metabolizing_enzymes=d.get("metabolizing_enzymes", []),
            target_receptors=d.get("target_receptors", []),
            narrow_therapeutic_index=d.get("narrow_therapeutic_index", False),
        )
        assert model.generic_name != ""


def test_known_interactions_contains_100_balanced_pairs():
    interactions_file = DATA_DIR / "known_interactions.json"
    assert interactions_file.exists(), "known_interactions.json does not exist"

    with open(interactions_file, "r", encoding="utf-8") as f:
        interactions = json.load(f)

    assert len(interactions) >= 100, f"Expected >= 100 interaction pairs, got {len(interactions)}"

    ids = [i["id"] for i in interactions]
    assert len(ids) == len(set(ids)), "Duplicate interaction IDs found in dataset"

    # Check balance between positive and negative/safe pairs
    positive_pairs = [i for i in interactions if i.get("severity", "").lower() in ["low", "mild", "moderate", "high", "severe"]]
    negative_pairs = [i for i in interactions if i.get("severity", "").lower() in ["none", "safe"] or "safe" in i.get("interaction_type", "").lower()]

    assert len(positive_pairs) >= 50, f"Expected >= 50 positive pairs, got {len(positive_pairs)}"
    assert len(negative_pairs) >= 50, f"Expected >= 50 safe/negative pairs, got {len(negative_pairs)}"


def test_cyp_enzymes_dataset_contains_10_pathways():
    cyp_file = DATA_DIR / "cyp_enzymes.json"
    assert cyp_file.exists(), "cyp_enzymes.json does not exist"

    with open(cyp_file, "r", encoding="utf-8") as f:
        pathways = json.load(f)

    assert len(pathways) >= 10, f"Expected >= 10 enzyme pathways, got {len(pathways)}"
    enzymes = [p["enzyme"] for p in pathways]
    assert "CYP3A4" in enzymes
    assert "CYP2C9" in enzymes
    assert "CYP2D6" in enzymes


def test_synthetic_patients_contains_500_valid_profiles():
    patients_file = DATA_DIR / "synthetic_patients_500.json"
    assert patients_file.exists(), "synthetic_patients_500.json does not exist"

    with open(patients_file, "r", encoding="utf-8") as f:
        patients = json.load(f)

    assert len(patients) == 500, f"Expected 500 patients, got {len(patients)}"

    # Sample test validation through Pydantic
    for p in patients[:50]:
        model = PatientContext(**p)
        assert model.patient_id.startswith("PT-SL-")
        assert 18 <= model.age <= 100
        assert model.organ_function.egfr is not None
