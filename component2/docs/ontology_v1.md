# AyurAI Component 2 Ontology v1.0

## Purpose

This ontology defines the initial knowledge representation structure for
AyurAI Component 2: Ayurvedic Knowledge Graph, Reasoning and Recommendation
Engine.

The ontology represents evidence-grounded relationships between symptoms,
Ayurvedic disease concepts, Dosha, Dhatu, therapeutic principles and
candidate interventions.

It is intended for research decision support and does not independently
perform clinical diagnosis or prescribe treatment.

## Node Types

### Symptom

Represents an observed or reported symptom supplied through the approved
Component 1 interface or described in Ayurvedic evidence.

### Roga

Represents an Ayurvedic disease or disease concept relevant to the
reasoning process. The initial research scope focuses on Pandu.

### Dosha

Represents Dosha concepts used in Ayurvedic reasoning.

### Dhatu

Represents Dhatu concepts used in Ayurvedic reasoning.

### TherapeuticPrinciple

Represents an evidence-supported Ayurvedic therapeutic principle.

### Herb

Represents an individual herb occurring in evidence sources.

### Formulation

Represents an Ayurvedic formulation described by evidence sources.

### Diet

Represents evidence-supported dietary recommendations or concepts.

### Lifestyle

Represents evidence-supported lifestyle recommendations or concepts.

### Evidence

Represents the provenance supporting a knowledge claim, including
classical literature, modern research, clinical guidance or
practitioner-validated knowledge.

## Relationship Types

### INDICATES

Connects a Symptom to a Roga when evidence supports the association.

Example structure:

Symptom -> INDICATES -> Roga

### ASSOCIATED_WITH_DOSHA

Connects a Roga or relevant clinical concept to a Dosha.

Roga -> ASSOCIATED_WITH_DOSHA -> Dosha

### AFFECTS_DHATU

Represents an evidence-supported relationship involving a Dhatu.

Roga -> AFFECTS_DHATU -> Dhatu

### SUGGESTS_PRINCIPLE

Connects an Ayurvedic reasoning concept to an evidence-supported
therapeutic principle.

Roga/Dosha/Dhatu -> SUGGESTS_PRINCIPLE -> TherapeuticPrinciple

### USES_HERB

Connects a therapeutic principle to an evidence-supported herb candidate.

TherapeuticPrinciple -> USES_HERB -> Herb

### USES_FORMULATION

Connects a therapeutic principle to an evidence-supported formulation.

TherapeuticPrinciple -> USES_FORMULATION -> Formulation

### RECOMMENDS_DIET

Connects a therapeutic principle to an evidence-supported dietary
candidate.

TherapeuticPrinciple -> RECOMMENDS_DIET -> Diet

### RECOMMENDS_LIFESTYLE

Connects a therapeutic principle to an evidence-supported lifestyle
candidate.

TherapeuticPrinciple -> RECOMMENDS_LIFESTYLE -> Lifestyle

### SUPPORTED_BY

Associates a knowledge claim or graph relationship with provenance from
an Evidence record.

## Provenance Rule

A clinically meaningful relationship must not be added to the finalized
knowledge graph solely from developer assumptions.

Each relationship must be traceable to one or more evidence records.

Evidence may originate from:

- Classical Ayurvedic literature
- Modern peer-reviewed research
- Recognized clinical or institutional guidance
- Practitioner validation collected under the approved research process

## Initial Scope Boundary

Ontology v1.0 focuses on Ayurvedic reasoning relevant to anemia/Pandu.

Component 2 does not consume raw images or wearable sensor signals.

Component 2 does not independently perform patient-specific safety
classification.

Component 2 produces evidence-grounded Ayurvedic interpretations,
candidate recommendations, reasoning confidence, evidence references,
and conflict/uncertainty information for downstream review.


## Claim-Based Evidence Architecture

### Claim Node

A Claim represents an evidence-backed statement
connecting two Ayurvedic knowledge concepts.

Properties:

- claim_id: string
- subject_id: string
- predicate: string
- object_id: string
- statement: string
- confidence: float | null
- verification_status: string
- created_at: datetime
- updated_at: datetime

Confidence is null until an explicit scoring
method has been defined and evaluated.

### Additional Relationships

SUBJECT_OF:
Concept -> Claim

OBJECT_OF:
Claim -> Concept

SUPPORTS:
Evidence -> Claim

CONTRADICTS:
Evidence -> Claim

### Claim Verification Status

- unverified
- literature_supported
- practitioner_verified
- disputed

### Provenance Rules

1. Every accepted claim must reference evidence.
2. Claims without evidence remain unverified.
3. Contradictory evidence must be preserved.
4. Practitioner feedback must be traceable.
5. Evidence confidence must not be fabricated.
6. Conflicting claims must not be silently deleted.