import torch
import torch.nn as nn


class AnemiaModel(nn.Module):
    """Small classifier: 10 input features -> 3 risk tiers (Low, Moderate, High).

    Only Linear layers are used, which Opacus supports for per-sample
    gradients. (BatchNorm would mix samples and is not allowed under DP.)
    """

    def __init__(self, num_features=10, num_classes=3):
        super().__init__()
        self.fc1 = nn.Linear(num_features, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, num_classes)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)
