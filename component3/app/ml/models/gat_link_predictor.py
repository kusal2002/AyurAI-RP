import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphAttentionLayer(nn.Module):
    """Self-contained Graph Attention layer computing attention coefficients

    between heterogeneous herb and drug feature representations.
    """

    def __init__(self, in_features: int, out_features: int, dropout: float = 0.2, alpha: float = 0.2):
        super(GraphAttentionLayer, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.dropout = dropout
        self.alpha = alpha

        self.W = nn.Linear(in_features, out_features, bias=False)
        self.a = nn.Parameter(torch.empty(size=(2 * out_features, 1)))
        nn.init.xavier_uniform_(self.W.weight.data, gain=1.414)
        nn.init.xavier_uniform_(self.a.data, gain=1.414)

        self.leakyrelu = nn.LeakyReLU(self.alpha)

    def forward(self, h_src: torch.Tensor, h_dst: torch.Tensor) -> torch.Tensor:
        """Computes pairwise attention-modulated feature projections."""
        Wh_src = self.W(h_src)
        Wh_dst = self.W(h_dst)

        # Concatenate source and destination features
        a_input = torch.cat([Wh_src, Wh_dst], dim=1)
        e = self.leakyrelu(torch.matmul(a_input, self.a))
        attention = F.softmax(e, dim=0)
        attention = F.dropout(attention, self.dropout, training=self.training)

        h_prime = attention * Wh_dst
        return Wh_src + h_prime


class GATLinkPredictor(nn.Module):
    """Graph Attention Network (GAT) In-Silico Link Predictor for Herb-Drug Interaction (M2 Baseline).

    Encodes heterogeneous herb and drug features and predicts the interaction probability.
    """

    def __init__(
        self,
        herb_in_dim: int,
        drug_in_dim: int,
        hidden_dim: int = 64,
        out_dim: int = 32,
        dropout: float = 0.2,
    ):
        super(GATLinkPredictor, self).__init__()

        # Linear projectors into shared embedding space
        self.herb_proj = nn.Sequential(
            nn.Linear(herb_in_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        self.drug_proj = nn.Sequential(
            nn.Linear(drug_in_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Graph Attention Layers
        self.gat_layer = GraphAttentionLayer(hidden_dim, hidden_dim, dropout=dropout)

        # Interaction Link Classifier Head
        # Concatenates: [h_herb, h_drug, h_herb * h_drug, |h_herb - h_drug|]
        link_in_dim = hidden_dim * 4
        self.link_classifier = nn.Sequential(
            nn.Linear(link_in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, out_dim),
            nn.ReLU(),
            nn.Linear(out_dim, 1),
        )

    def forward(
        self,
        all_herb_feats: torch.Tensor,
        all_drug_feats: torch.Tensor,
        herb_indices: torch.Tensor,
        drug_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass for a batch of (herb, drug) index pairs."""
        # Project all nodes
        h_all_herbs = self.herb_proj(all_herb_feats)
        h_all_drugs = self.drug_proj(all_drug_feats)

        # Extract batch node embeddings
        h_herbs = h_all_herbs[herb_indices]
        h_drugs = h_all_drugs[drug_indices]

        # Cross attention interaction
        h_attended = self.gat_layer(h_herbs, h_drugs)

        # Bilinear interaction features
        prod_feat = h_herbs * h_drugs
        diff_feat = torch.abs(h_herbs - h_drugs)

        combined = torch.cat([h_herbs, h_attended, prod_feat, diff_feat], dim=1)
        logits = self.link_classifier(combined).squeeze(-1)
        return logits

    def predict_probability(
        self,
        all_herb_feats: torch.Tensor,
        all_drug_feats: torch.Tensor,
        herb_idx: int,
        drug_idx: int,
    ) -> float:
        """Inference helper returning interaction probability in [0, 1]."""
        self.eval()
        with torch.no_grad():
            h_idx = torch.tensor([herb_idx], dtype=torch.long)
            d_idx = torch.tensor([drug_idx], dtype=torch.long)
            logits = self.forward(all_herb_feats, all_drug_feats, h_idx, d_idx)
            prob = torch.sigmoid(logits).item()
            return float(prob)
