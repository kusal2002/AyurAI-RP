import torch
import torch.nn as nn


class NaiveContextModel(nn.Module):
    """M3 Baseline: Naive Context Model.

    Directly concatenates graph interaction embedding (h_graph) with the
    patient context vector (x_patient) into a multi-layer perceptron.
    Serves as the intermediate ablation baseline to determine if simply
    appending patient features improves performance over generic graph learning.
    """

    def __init__(self, graph_dim: int = 32, patient_dim: int = 16, hidden_dim: int = 32, num_classes: int = 3):
        super(NaiveContextModel, self).__init__()
        in_dim = graph_dim + patient_dim

        self.mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, num_classes),
        )

    def forward(self, h_graph: torch.Tensor, x_patient: torch.Tensor) -> torch.Tensor:
        """Concatenates features along dimension 1 and computes class logits."""
        combined = torch.cat([h_graph, x_patient], dim=1)
        logits = self.mlp(combined)
        return logits
