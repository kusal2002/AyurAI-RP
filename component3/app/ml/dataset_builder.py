import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import torch

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class GraphDatasetBuilder:
    """Builds node feature tensors, interaction edge indices,

    and train/val/test splits for GNN in-silico link prediction.
    """

    def __init__(self):
        self._load_raw_data()
        self._build_vocabularies()

    def _load_raw_data(self):
        with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
            self.herbs = json.load(f)
        with open(DATA_DIR / "pharma_drugs.json", "r", encoding="utf-8") as f:
            self.drugs = json.load(f)
        with open(DATA_DIR / "known_interactions.json", "r", encoding="utf-8") as f:
            self.interactions = json.load(f)
        with open(DATA_DIR / "cyp_enzymes.json", "r", encoding="utf-8") as f:
            self.cyp_enzymes = json.load(f)

    def _build_vocabularies(self):
        # Herb mapping
        self.herb_to_idx: Dict[str, int] = {h["common_name"].lower(): idx for idx, h in enumerate(self.herbs)}
        self.idx_to_herb: Dict[int, str] = {idx: h["common_name"] for idx, h in enumerate(self.herbs)}

        # Drug mapping
        self.drug_to_idx: Dict[str, int] = {d["generic_name"].lower(): idx for idx, d in enumerate(self.drugs)}
        self.idx_to_drug: Dict[int, str] = {idx: d["generic_name"] for idx, d in enumerate(self.drugs)}

        # All unique active compounds
        all_compounds = sorted(list({c.lower() for h in self.herbs for c in h.get("active_compounds", [])}))
        self.compound_to_idx = {c: idx for idx, c in enumerate(all_compounds)}

        # All unique drug classes & targets
        all_drug_classes = sorted(list({d["drug_class"].lower() for d in self.drugs}))
        self.drug_class_to_idx = {dc: idx for idx, dc in enumerate(all_drug_classes)}

        all_enzymes = sorted(list({e["enzyme"].lower() for e in self.cyp_enzymes}))
        self.enzyme_to_idx = {e: idx for idx, e in enumerate(all_enzymes)}

    def build_herb_features(self) -> torch.Tensor:
        """Constructs multi-hot feature vectors for each Ayurvedic herb based on active compounds."""
        num_herbs = len(self.herbs)
        dim_compounds = len(self.compound_to_idx)
        # Herb feature dimension = compounds + 5 (indications/properties)
        feat_dim = dim_compounds + 8
        features = np.zeros((num_herbs, feat_dim), dtype=np.float32)

        for idx, h in enumerate(self.herbs):
            for comp in h.get("active_compounds", []):
                c_idx = self.compound_to_idx.get(comp.lower())
                if c_idx is not None:
                    features[idx, c_idx] = 1.0

            # Meta property encodings (Pandu, Shotha, Rasayana, Bhasma calx)
            trad_str = " ".join(h.get("traditional_uses", [])).lower()
            name_str = h["common_name"].lower()
            if "pandu" in trad_str:
                features[idx, dim_compounds + 0] = 1.0
            if "shotha" in trad_str:
                features[idx, dim_compounds + 1] = 1.0
            if "rasayana" in trad_str:
                features[idx, dim_compounds + 2] = 1.0
            if "bhasma" in name_str or "lauha" in name_str or "calx" in h["botanical_name"].lower():
                features[idx, dim_compounds + 3] = 1.0  # Mineral/iron-bearing
            if "pitta" in trad_str:
                features[idx, dim_compounds + 4] = 1.0
            if "deepana" in trad_str or "pachana" in trad_str:
                features[idx, dim_compounds + 5] = 1.0
            if len(h.get("contraindications", [])) > 0:
                features[idx, dim_compounds + 6] = 1.0
            features[idx, dim_compounds + 7] = float(len(h.get("active_compounds", []))) / 10.0

        return torch.tensor(features, dtype=torch.float32)

    def build_drug_features(self) -> torch.Tensor:
        """Constructs multi-hot feature vectors for pharmaceutical drugs based on class, enzymes, and NTI."""
        num_drugs = len(self.drugs)
        dim_classes = len(self.drug_class_to_idx)
        dim_enzymes = len(self.enzyme_to_idx)
        feat_dim = dim_classes + dim_enzymes + 3
        features = np.zeros((num_drugs, feat_dim), dtype=np.float32)

        for idx, d in enumerate(self.drugs):
            # Drug class one-hot
            dc_idx = self.drug_class_to_idx.get(d["drug_class"].lower())
            if dc_idx is not None:
                features[idx, dc_idx] = 1.0

            # Metabolizing enzyme multi-hot
            for enz in d.get("metabolizing_enzymes", []):
                for e_key, e_idx in self.enzyme_to_idx.items():
                    if e_key in enz.lower():
                        features[idx, dim_classes + e_idx] = 1.0

            # Narrow therapeutic index flag
            if d.get("narrow_therapeutic_index", False):
                features[idx, dim_classes + dim_enzymes + 0] = 1.0

            # Renal clearance marker
            enz_str = " ".join(d.get("metabolizing_enzymes", [])).lower()
            if "renal" in enz_str or "unchanged" in enz_str:
                features[idx, dim_classes + dim_enzymes + 1] = 1.0

            features[idx, dim_classes + dim_enzymes + 2] = float(len(d.get("target_receptors", []))) / 5.0

        return torch.tensor(features, dtype=torch.float32)

    def build_interaction_dataset(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """Builds pairs (herb_idx, drug_idx) and binary labels (1.0 for interaction, 0.0 for safe)."""
        pairs = []
        labels = []

        for inter in self.interactions:
            h_name = inter["herb"].lower()
            d_name = inter["drug"].lower()

            h_idx = self.herb_to_idx.get(h_name)
            d_idx = self.drug_to_idx.get(d_name)

            if h_idx is not None and d_idx is not None:
                sev = inter.get("severity", "").lower()
                is_interaction = 0.0 if sev in ["none", "safe"] or "safe" in inter.get("interaction_type", "").lower() else 1.0
                pairs.append([h_idx, d_idx])
                labels.append(is_interaction)

        pairs_tensor = torch.tensor(pairs, dtype=torch.long)
        labels_tensor = torch.tensor(labels, dtype=torch.float32)

        return pairs_tensor, labels_tensor

    def get_splits(
        self, test_ratio: float = 0.20, val_ratio: float = 0.15, seed: int = 42
    ) -> Dict[str, Any]:
        """Generates reproducible train, validation, and test splits."""
        pairs, labels = self.build_interaction_dataset()
        num_samples = len(pairs)
        indices = np.arange(num_samples)

        np.random.seed(seed)
        np.random.shuffle(indices)

        n_test = int(num_samples * test_ratio)
        n_val = int(num_samples * val_ratio)

        test_idx = indices[:n_test]
        val_idx = indices[n_test : n_test + n_val]
        train_idx = indices[n_test + n_val :]

        return {
            "herb_features": self.build_herb_features(),
            "drug_features": self.build_drug_features(),
            "train_pairs": pairs[train_idx],
            "train_labels": labels[train_idx],
            "val_pairs": pairs[val_idx],
            "val_labels": labels[val_idx],
            "test_pairs": pairs[test_idx],
            "test_labels": labels[test_idx],
            "herb_to_idx": self.herb_to_idx,
            "drug_to_idx": self.drug_to_idx,
            "idx_to_herb": self.idx_to_herb,
            "idx_to_drug": self.idx_to_drug,
        }
