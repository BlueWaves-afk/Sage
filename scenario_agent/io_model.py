"""
Full input-output (Leontief) economic model.

Where ario.py is a single-commodity supply cascade, this is the proper multi-sector
IO model: it propagates an oil shock through the inter-industry linkages of the whole
economy (direct + indirect effects via the Leontief inverse), giving per-sector output
loss, GDP impact, and cost-push inflation.

  Output impact (quantity):  Δx = (I − A)^-1 · d        d = petroleum-dependency × shortfall
  Price impact (cost-push):  Δp = (I − Aᵀ)^-1 · c        c = petroleum-input-coeff × Δprice

The aggregated India IO matrix lives in the context bundle (io/leontief_A.csv,
io/io_sectors.csv), sourced from MOSPI IOTT / IIOA energy-IO. Swap in the full
MOSPI 140-sector table for production — the math is identical, just a bigger matrix.

See data/data.md for provenance.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class SectorIOImpact:
    sector:          str
    output_loss_pct: float      # total (direct+indirect) output loss %
    price_rise_pct:  float      # cost-push price increase %
    va_share:        float


@dataclass
class IOResult:
    sectors:            list[str]
    gdp_loss_pct:       float                 # economy-wide value-added loss %
    inflation_pct:      float                 # final-demand-weighted price rise %
    sector_impacts:     list[SectorIOImpact] = field(default_factory=list)
    output_multipliers: dict = field(default_factory=dict)   # validation: column sums of L


class LeontiefIO:
    def __init__(self, sectors, A, va_share, final_demand, petroleum_coeff):
        self.sectors = sectors
        self.A = np.array(A, dtype=float)
        self.va = np.array(va_share, dtype=float)
        self.fd = np.array(final_demand, dtype=float)
        self.pet = np.array(petroleum_coeff, dtype=float)
        n = len(sectors)
        I = np.eye(n)
        self.L  = np.linalg.inv(I - self.A)          # Leontief inverse (demand-driven, quantity)
        self.Lp = np.linalg.inv(I - self.A.T)        # price model (cost-push)
        self.spectral_radius = max(abs(np.linalg.eigvals(self.A)))

    def output_multipliers(self) -> dict:
        """Column sums of the Leontief inverse — total output per unit final demand."""
        return {s: round(float(m), 3) for s, m in zip(self.sectors, self.L.sum(axis=0))}

    def run(self, petroleum_shortfall_frac: float, petroleum_price_rise_frac: float) -> IOResult:
        """
        petroleum_shortfall_frac : fraction of national petroleum supply lost (0..1)
        petroleum_price_rise_frac: fractional crude/product price increase (e.g. 0.6 = +60%)
        """
        # Quantity: direct sector loss = petroleum dependence × shortfall, amplified by L.
        d = self.pet * petroleum_shortfall_frac
        output_loss = self.L @ d                     # total (direct+indirect) fractional loss
        output_loss = np.clip(output_loss, 0.0, 1.0)

        # Price: cost-push from the petroleum input-cost shock, propagated via (I−Aᵀ)^-1.
        c = self.pet * petroleum_price_rise_frac
        price_rise = self.Lp @ c

        gdp_loss  = float(np.dot(self.va, output_loss) / self.va.sum() * 100.0)
        inflation = float(np.dot(self.fd, price_rise) / self.fd.sum() * 100.0)

        impacts = [
            SectorIOImpact(
                sector=s,
                output_loss_pct=round(float(output_loss[i] * 100.0), 3),
                price_rise_pct=round(float(price_rise[i] * 100.0), 3),
                va_share=round(float(self.va[i]), 3),
            )
            for i, s in enumerate(self.sectors)
        ]
        impacts.sort(key=lambda x: -x.output_loss_pct)

        return IOResult(
            sectors=self.sectors,
            gdp_loss_pct=round(gdp_loss, 3),
            inflation_pct=round(inflation, 3),
            sector_impacts=impacts,
            output_multipliers=self.output_multipliers(),
        )


def load_io(bundle_path: str = "data/india-energy-2026.context") -> LeontiefIO | None:
    """Load the aggregated India IO matrix + sector data from the context bundle."""
    base = Path(bundle_path) / "io"
    a_file, s_file = base / "leontief_A.csv", base / "io_sectors.csv"
    if not (a_file.exists() and s_file.exists()):
        return None

    with s_file.open(newline="", encoding="utf-8") as f:
        srows = list(csv.DictReader(f))
    sectors = [r["sector"] for r in srows]
    va  = [float(r["va_share"]) for r in srows]
    fd  = [float(r["final_demand_share"]) for r in srows]
    pet = [float(r["petroleum_input_coeff"]) for r in srows]

    with a_file.open(newline="", encoding="utf-8") as f:
        arows = list(csv.DictReader(f))
    # rows are input sectors, columns are output sectors; align to `sectors` order
    A = [[float(row[col]) for col in sectors] for row in arows]

    return LeontiefIO(sectors, A, va, fd, pet)
