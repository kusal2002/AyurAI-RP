# AyurAI Component 3: AI-Based Herb–Drug Interaction and Safety Prediction

**Author:** Ransika A D L — IT23308466  
**Supervisors:** Prof. Samantha Thelijjagoda (Supervisor), Mr. Vishan Jayasinghearachchi (Co-Supervisor), Dr. Jeevanie Thiranagamage (External Supervisor)  
**Research Cluster:** Healthcare AI / Knowledge Graphs / Graph Machine Learning  

---

## 📌 Component Role in AyurAI Pipeline
Component 3 serves as the **Clinical Safety Gate** within the AyurAI decision support workflow:
```
[Component 1: Screening] 
        ↓ (Risk Tier + Confidence + Symptoms)
[Component 2: Ayurvedic GraphRAG] 
        ↓ (Candidate Herbs / Formulations)
[Component 3: Patient-Context Safety Assessment] 🛡️ (YOU ARE HERE)
        ↓ (Low Risk / Caution / High Risk + Evidence + Titration Plan)
[Practitioner Review Dashboard]
        ↓ (Approved Decisions + Audit Trail)
[Component 4: Federated Learning & Sepolia Governance]
```

---

## 🧬 Core Architecture: 4 Interdependent Stages

1. **Stage 1 — Evidence & Rule Retrieval (M1 Safety Floor):**
   * Deterministic rule-based engine that identifies known herb–drug, herb–herb interactions, and clinical contraindications (pregnancy, severe CKD, cardiovascular collisions).
2. **Stage 2 — Graph-Based In-Silico Interaction Prediction (M2 Generic GNN):**
   * Graph link prediction across `Herb -> Active Compound -> CYP Enzyme / Target -> Drug` to predict potential or uncodified interactions.
3. **Stage 3 — Patient-Context Risk Fusion Layer (M4 Proposed Contribution):**
   * Fuses structural interaction scores with patient-specific susceptibility factors: eGFR / CKD stages, hepatic function, age-dependent pharmacodynamics, polypharmacy burden, and anemia severity.
4. **Stage 4 — Explainable Safety Classifier & Titration Advisor:**
   * Synthesizes findings into `Low Risk`, `Caution`, or `High Risk` classifications.
   * Generates step-down titration schedules, dosing time separations (e.g. $\ge 4$ hours), laboratory surveillance orders (eGFR, TSH, Ferritin), and practitioner escalation flags.

---

## 🚀 Running the Microservice

### 1. Install Dependencies
```bash
cd component3
python -m venv venv
venv\Scripts\activate       # On Windows
pip install -r requirements.txt
```

### 2. Start the FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

The interactive OpenAPI / Swagger documentation will be available at:
* **Swagger UI:** `http://localhost:8003/docs`
* **Health Check:** `http://localhost:8003/health`

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/c2/safety-evaluation` | Primary inter-component contract: Receives C2 recommendations + Patient context and outputs complete safety report. |
| `GET` | `/api/v1/safety/herbs` | Returns curated anemia-related Ayurvedic herbs and constituents. |
| `GET` | `/api/v1/safety/drugs` | Returns commonly prescribed pharmaceutical drugs database. |
| `GET` | `/api/v1/safety/known-interactions` | Returns verified interaction rules with PubMed / WHO citations. |
| `GET` | `/api/v1/safety/cyp-pathways` | Returns CYP450 enzyme substrate & inhibitor profiles. |

---

## 🔬 Experimental Baselines for Ablation Study

| Model | Model Name | Description | Role in Experiment |
|---|---|---|---|
| **M1** | Rule-Only | Deterministic rules/lookup for known interactions & contraindications | Safety-floor baseline |
| **M2** | Generic GNN | GAT / Link prediction without patient context | Graph learning baseline |
| **M3** | Naive Context | GAT + patient features concatenated | Context baseline |
| **M4** | **Context Fusion Layer** | **GAT + learned Context Fusion Layer dynamically modulating risk** | **Proposed Model (Primary Research Contribution)** |
