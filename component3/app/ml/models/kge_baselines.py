"""Knowledge Graph Embedding (KGE) Baselines: ComplEx and RotatE.

Implements standard benchmark scoring functions for link prediction
comparisons as outlined in proposal SO3 and Table 1.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class ComplExModel(nn.Module):
    """ComplEx Embedding Model (Trouillon et al., ICML 2016).

    Embeds entities and relations in the complex domain C.
    Score: Re(<h, r, conj(t)>)
    """

    def __init__(self, num_entities: int, num_relations: int = 2, embedding_dim: int = 64):
        super(ComplExModel, self).__init__()
        self.embedding_dim = embedding_dim
        self.ent_re = nn.Embedding(num_entities, embedding_dim)
        self.ent_im = nn.Embedding(num_entities, embedding_dim)
        self.rel_re = nn.Embedding(num_relations, embedding_dim)
        self.rel_im = nn.Embedding(num_relations, embedding_dim)

        nn.init.xavier_uniform_(self.ent_re.weight.data)
        nn.init.xavier_uniform_(self.ent_im.weight.data)
        nn.init.xavier_uniform_(self.rel_re.weight.data)
        nn.init.xavier_uniform_(self.rel_im.weight.data)

    def forward(self, head_idx: torch.Tensor, rel_idx: torch.Tensor, tail_idx: torch.Tensor) -> torch.Tensor:
        h_re = self.ent_re(head_idx)
        h_im = self.ent_im(head_idx)
        r_re = self.rel_re(rel_idx)
        r_im = self.rel_im(rel_idx)
        t_re = self.ent_re(tail_idx)
        t_im = self.ent_im(tail_idx)

        # Real part of Hermitian inner product
        score = (
            (h_re * r_re - h_im * r_im) * t_re
            + (h_re * r_im + h_im * r_re) * t_im
        ).sum(dim=-1)
        return score


class RotatEModel(nn.Module):
    """RotatE Embedding Model (Sun et al., ICLR 2019).

    Models relations as rotations in complex space: t = h \circ r
    Score: - ||h \circ r - t||
    """

    def __init__(self, num_entities: int, num_relations: int = 2, embedding_dim: int = 64):
        super(RotatEModel, self).__init__()
        self.embedding_dim = embedding_dim
        self.ent_re = nn.Embedding(num_entities, embedding_dim)
        self.ent_im = nn.Embedding(num_entities, embedding_dim)
        self.rel_phase = nn.Embedding(num_relations, embedding_dim)

        nn.init.xavier_uniform_(self.ent_re.weight.data)
        nn.init.xavier_uniform_(self.ent_im.weight.data)
        nn.init.uniform_(self.rel_phase.weight.data, -3.14159, 3.14159)

    def forward(self, head_idx: torch.Tensor, rel_idx: torch.Tensor, tail_idx: torch.Tensor) -> torch.Tensor:
        h_re = self.ent_re(head_idx)
        h_im = self.ent_im(head_idx)
        phase = self.rel_phase(rel_idx)
        r_re = torch.cos(phase)
        r_im = torch.sin(phase)

        t_re = self.ent_re(tail_idx)
        t_im = self.ent_im(tail_idx)

        # Rotation: h * r
        hr_re = h_re * r_re - h_im * r_im
        hr_im = h_re * r_im + h_im * r_re

        # Distance to target
        diff_re = hr_re - t_re
        diff_im = hr_im - t_im
        score = -torch.norm(torch.stack([diff_re, diff_im], dim=-1), p=2, dim=-1).sum(dim=-1)
        return score
