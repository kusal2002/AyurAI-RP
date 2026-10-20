from typing import List, Optional
from pydantic import BaseModel, Field


class HerbEntity(BaseModel):
    id: str
    common_name: str
    sanskrit_name: Optional[str] = None
    botanical_name: str
    active_compounds: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    traditional_uses: List[str] = Field(default_factory=list)


class DrugEntity(BaseModel):
    id: str
    generic_name: str
    brand_names: List[str] = Field(default_factory=list)
    drug_class: str
    metabolizing_enzymes: List[str] = Field(default_factory=list)
    target_receptors: List[str] = Field(default_factory=list)
    narrow_therapeutic_index: bool = False


class InteractionRelation(BaseModel):
    id: str
    source_entity: str
    target_entity: str
    relation_type: str  # INTERACTS_WITH, INHIBITS, INDUCES, CHELATES_WITH, CONTRAINDICATED_IN
    severity: str       # Mild, Moderate, Severe
    mechanism: str
    evidence_level: str # Established, Probable, Possible
    pmid: Optional[str] = None
