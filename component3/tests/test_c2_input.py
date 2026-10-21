from app.models.c2_input import C2CandidatePackage


def test_package_accepts_missing_component1_confidence():
    package = C2CandidatePackage(
        case_id="C1-SYNTH-002",
        anemia_risk_tier="Low",
        anemia_confidence=None,
        ayurvedic_interpretation="Roga: Pandu (knowledge-graph association, not a diagnosis)",
        candidates=[],
    )
    assert package.anemia_confidence is None
