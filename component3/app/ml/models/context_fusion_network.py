import torch
import torch.nn as nn
import torch.nn.functional as F


class ContextFusionLayer(nn.Module):
    """Dynamic Context Fusion Layer with Patient Vulnerability Gating.

    Primary research contribution of AyurAI Component 3 (M4 Proposed Model).
    Dynamically modulates graph interaction representations based on patient-specific
    clinical susceptibilities (renal impairment, hepatic clearance, age, polypharmacy).

    Equation:
      g = sigmoid(W_g * x_patient + b_g)           [Vulnerability Gate]
      z = g * (W_h * h_graph) + (1 - g) * h_graph   [Gated Modulation]
    """

    def __init__(self, graph_dim: int = 32, patient_dim: int = 16, hidden_dim: int = 32):
        super(ContextFusionLayer, self).__init__()
        self.graph_dim = graph_dim
        self.patient_dim = patient_dim
        self.hidden_dim = hidden_dim

        # 1. Linear projection of graph embedding
        self.W_h = nn.Linear(graph_dim, hidden_dim)

        # 2. Patient vulnerability gate generator
        self.W_g = nn.Sequential(
            nn.Linear(patient_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Sigmoid(),
        )

        # 3. Residual scale parameter
        self.gamma = nn.Parameter(torch.ones(1) * 0.1)

    def forward(self, h_graph: torch.Tensor, x_patient: torch.Tensor) -> torch.Tensor:
        """Computes gated context modulation."""
        h_proj = self.W_h(h_graph)
        gate = self.W_g(x_patient)

        # Dynamic gating: when patient vulnerability is high (gate -> 1),
        # the amplified projection h_proj dominates.
        z = gate * h_proj + (1.0 - gate) * h_graph
        return z


class ContextFusionNetwork(nn.Module):
    """Full Neural Safety Classification Network (M4 Proposed Model).

    Integrates:
    - GAT In-Silico Interaction Embedding (h_graph)
    - Patient Clinical Context (x_patient) via ContextFusionLayer
    - Produces both 3-class safety logits (Low Risk, Caution, High Risk)
      and a continuous scalar risk score in [0, 1].
    """

    def __init__(
        self,
        graph_dim: int = 32,
        patient_dim: int = 16,
        hidden_dim: int = 32,
        num_classes: int = 3,
        dropout: float = 0.2,
    ):
        super(ContextFusionNetwork, self).__init__()
        self.fusion_layer = ContextFusionLayer(graph_dim, patient_dim, hidden_dim)

        # Joint Cross-Feature Perceptron
        fusion_out_dim = hidden_dim + patient_dim
        self.classifier = nn.Sequential(
            nn.Linear(fusion_out_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, num_classes),
        )

        # Continuous risk score regressor head
        self.risk_head = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, h_graph: torch.Tensor, x_patient: torch.Tensor):
        """Forward pass returning (3-class logits, continuous risk score)."""
        z_fused = self.fusion_layer(h_graph, x_patient)
        combined = torch.cat([z_fused, x_patient], dim=1)

        logits = self.classifier(combined)
        scalar_risk = self.risk_head(z_fused).squeeze(-1)

        return logits, scalar_risk

    def predict_safety(self, h_graph: torch.Tensor, x_patient: torch.Tensor):
        """Inference helper returning class probabilities and risk score."""
        self.eval()
        with torch.no_grad():
            if h_graph.dim() == 1:
                h_graph = h_graph.unsqueeze(0)
            if x_patient.dim() == 1:
                x_patient = x_patient.unsqueeze(0)

            logits, scalar_risk = self.forward(h_graph, x_patient)
            probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()
            risk = scalar_risk.item()

            tier_idx = int(probs.argmax())
            tiers = ["Low Risk", "Caution", "High Risk"]

            return {
                "safety_tier": tiers[tier_idx],
                "confidence": float(probs[tier_idx]),
                "probabilities": {
                    "low_risk": float(probs[0]),
                    "caution": float(probs[1]),
                    "high_risk": float(probs[2]),
                },
                "fused_risk_score": float(risk),
            }
