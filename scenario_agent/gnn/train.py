"""
GNN surrogate training script.

Generates training data by running ARIO over a sweep of scenario parameters,
then trains the GNN to approximate the ARIO input→output mapping.
Run once (Week 2) on EC2 g4dn.xlarge T4 GPU. Save weights to gnn/weights/.
"""
from __future__ import annotations

from scenario_agent.ario import ARIOParams, run as run_ario


def generate_training_data(n_samples: int = 10_000) -> list[dict]:
    """
    Monte Carlo sweep over ARIO params. Each sample: (params → ario_result).
    Stub.
    """
    # TODO: sample ARIOParams randomly (disruption_fraction 0.1–1.0, disruption_days 7–90)
    # TODO: run run_ario(params) for each sample
    # TODO: return list of {features: ..., targets: ...}
    return []


def train(output_path: str = "scenario_agent/gnn/weights/cascade_gnn.pt") -> None:
    """Train the GNN surrogate and save weights. Stub."""
    data = generate_training_data()
    # TODO: build DataLoader from data
    # TODO: instantiate CascadeGNN
    # TODO: train with Adam, MSE loss on feedstock_gap + price_impact + spr_depletion
    # TODO: torch.save(model.state_dict(), output_path)
    raise NotImplementedError


if __name__ == "__main__":
    train()
