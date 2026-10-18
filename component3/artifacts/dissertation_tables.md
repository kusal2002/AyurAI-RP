# AyurAI Component 3: Empirical Ablation Benchmarking Report
## Chapter 5: Evaluation & Experimental Results

> **Experimental Cohort:** 500 patient profiles (1,000 paired evaluations)
> **Split:** 70% Train (700) | 15% Validation (150) | 15% Held-Out Test (150)

### Table 5.1: Comparative Performance of Architectural Variants on Held-Out Test Set (N = 150)

| Model Variant | Architecture Description | Context Mechanism | Accuracy | Macro-F1 | PR-AUC | ROC-AUC | Sensitivity | Specificity | Brier Score |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **M1** | Deterministic Rule Engine | Static Dictionary Lookup | 32.7% | 0.3944 | 0.4869 | 0.6439 | 0.5608 | 0.7501 | 0.9693 |
| **M2** | GAT Link Predictor | None (Static Graph Only) | 26.0% | 0.3966 | 0.5788 | 0.6650 | 0.6389 | 0.6921 | 1.4079 |
| **M3** | Concat MLP Baseline | Feature Concatenation $[\mathbf{h} \parallel \mathbf{x}]$ | 73.3% | 0.2821 | 0.7898 | 0.8834 | 0.3333 | 0.6667 | 0.3367 |
| **M4** | Gated Fusion Network | Adaptive Vulnerability Gating $\mathbf{g} \odot (W_h \mathbf{h})$ | 90.7% | **0.8771** | **0.9403** | 0.9640 | 0.8707 | 0.9173 | 0.1549 |

---

### Table 5.2: Per-Class Granular Safety Tier Performance (Test Set N = 150)

| Model | Metric | Safe (Tier 0) | Caution (Tier 1) | High Risk (Tier 2) | Macro Average |
|---|---|:---:|:---:|:---:|:---:|
| **M1** | F1-Score | 0.1935 | 0.3556 | 0.6341 | **0.3944** |
| | Sensitivity | 1.0000 | 0.2182 | 0.4643 | **0.5608** |
| **M2** | F1-Score | 0.8462 | 0.0000 | 0.3436 | **0.3966** |
| | Sensitivity | 0.9167 | 0.0000 | 1.0000 | **0.6389** |
| **M3** | F1-Score | 0.0000 | 0.8462 | 0.0000 | **0.2821** |
| | Sensitivity | 0.0000 | 1.0000 | 0.0000 | **0.3333** |
| **M4** | F1-Score | 0.9167 | 0.9369 | 0.7778 | **0.8771** |
| | Sensitivity | 0.9167 | 0.9455 | 0.7500 | **0.8707** |

---

### Table 5.3: Clinical Vulnerability Subgroup Stratification (Full Cohort N = 1,000)

| Clinical Subgroup | Patient Criteria | Subgroup N | M3 Naive Concat F1 | M4 Context Fusion F1 | Relative Gain (%) | Clinical Significance |
|---|---|:---:|:---:|:---:|:---:|---|
| **Overall Cohort** | All synthetic patient evaluations | 1000 | 0.2846 | **0.8395** | **+195.0%** | Primary dissertation benchmark |
| **Renal Impairment (eGFR < 60)** | Baseline eGFR < 60 mL/min/1.73m² (CKD G3-G5) | 244 | 0.2784 | **0.7327** | **+163.2%** | Critical for renally eliminated herbal calxes & diuretics |
| **Polypharmacy (>= 3 co-medications)** | Active concurrent medications count ≥ 3 | 662 | 0.2891 | **0.7581** | **+162.2%** | Highest risk cohort for competitive metabolic inhibition |
| **Elderly (Age >= 65)** | Patient age ≥ 65 years | 308 | 0.2871 | **0.6579** | **+129.2%** | Reduced pharmacodynamic reserve & renal clearance |