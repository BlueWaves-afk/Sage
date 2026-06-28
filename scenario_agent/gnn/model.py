"""
GNN surrogate model — PyTorch.

Trained on ARIO/ABM outputs: learns (scenario_params → subgraph_state) → cascade_outputs.
Online inference target: <150ms on T4 GPU (single forward pass).
Powers both interactive UI sliders AND the Anticipatory Sandbox fork.

Input:  subgraph node features + projected risk parameters
Output: feedstock_gap_timeline, price_impact range, spr_depletion_days
"""
from __future__ import annotations

# TODO: import torch, torch_geometric

class CascadeGNN:
    """
    GNN surrogate. Graph Attention Network over the supply-chain subgraph.
    Stub — implement architecture in Week 2, train on ARIO outputs in Week 2.
    """

    def __init__(self, checkpoint_path: str | None = None):
        # TODO: define GAT layers (input: node features, edge features → cascade output)
        # TODO: load weights from checkpoint_path if provided
        pass

    def forward(self, subgraph: dict, risk_params: dict) -> dict:
        """
        Single forward pass. Input: subgraph dict from get_subgraph() + projected risk params.
        Output: cascade result dict (same shape as ARIOResult).
        Target: <150ms on T4. On CPU: ~800ms (too slow for sandbox fork).
        Stub.
        """
        raise NotImplementedError

    @classmethod
    def load(cls, path: str) -> "CascadeGNN":
        model = cls()
        # TODO: model.load_state_dict(torch.load(path))
        return model
