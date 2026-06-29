# SAGE — System 2: ARIO Disruption Scenario Modeller
## Design Specification

**System:** 2 of 5  
**Owner:** Scenario Agent  
**Status:** Ready to implement — KB interface fully locked  
**Companion specs:**
- [`SAGE_Schema_and_Contracts_Spec.md`](./SAGE_Schema_and_Contracts_Spec.md) — normative contracts (C5, C7)
- [`SAGE_Knowledge_Base_Spec.md`](./SAGE_Knowledge_Base_Spec.md) — KB architecture
- [`SAGE_Deployment_Guide.md`](./SAGE_Deployment_Guide.md) — container & GPU config

---

## 1. Purpose & Scope

System 2 answers the question: **"If a corridor is blocked right now, what is the day-by-day impact on India's oil supply, refinery feedstocks, SPR cover, and import prices?"**

It implements the **Adaptive Regional Input-Output (ARIO)** model (Hallegatte 2008) over India's crude supply chain graph, then outputs a `ScenarioOutputData` object to the KB that drives System 3 (procurement) and System 4 (SPR optimisation).

**Two execution paths:**

| Path | Trigger | Latency | Model |
|---|---|---|---|
| **Sandbox (anticipatory)** | HIGH signal + score 0.45–0.70 | ≤ 150ms | GNN surrogate (PyTorch, GPU) |
| **Cold live (confirmed)** | score ≥ 0.70, no pre-staged scenario | ~2,500ms | Full ARIO propagation (CPU/NumPy) |
| **Promotion (pre-staged)** | score ≥ 0.70, sandbox already ran | ~50ms | Reload + refresh params only |

System 2 does **not** compute risk scores (System 1's job) and does **not** rank procurement routes (System 3's job). It computes the supply shock magnitude and cascade timeline that all downstream systems depend on.

---

## 2. Architecture Diagram

```
[orchestration/triggers.py]
        │
        ├─ _fast_path()  ──────────────────────────────────→  promote_pending() [KB]
        │                                                         │
        └─ _cold_pipeline()  ──→  run_scenario()               [scenario_agent/runner.py]
                                        │
                    ┌───────────────────┼──────────────────────┐
                    │                   │                        │
             [graph_builder.py]  [parameters.py]         [ario.py or gnn_surrogate.py]
             KB → ARIO matrix    India IO coefficients    Propagation engine
                    │                   │                        │
                    └───────────────────┴────────────────────────┘
                                        │
                                ScenarioOutputData
                                        │
                              write_scenario() [KB API]
                                        │
                         [orchestration/triggers.py picks up]
                         → runs System 3 + System 4 in parallel
```

---

## 3. File Structure

```
scenario_agent/
├── __init__.py
├── runner.py           # Entry point: run_scenario() called by triggers.py
├── ario.py             # ARIO propagation — day-by-day NumPy loop
├── gnn_surrogate.py    # PyTorch GraphSAGE model for sandbox fast path
├── graph_builder.py    # Converts KB SubgraphView → ARIO matrix form
├── parameters.py       # All hardcoded India IO constants, labeled + sourced
└── models.py           # Internal dataclasses (ARIOState, NodeVector, etc.)
```

---

## 4. Knowledge Base Interface

### 4.1 What System 2 reads

```python
from knowledge.api.read import get_subgraph, get_spr_state, get_risk_scores
from knowledge.api.write import write_scenario

# Call 1 — supply chain subgraph centred on disrupted entity
# hops=3 ensures: Corridor → Port → Refinery → SPRCavern (FEEDS_RESERVE)
subgraph: SubgraphView = await get_subgraph(trigger_entity, hops=3)

# Call 2 — SPR live fill levels (guaranteed fresh, independent of subgraph hops)
spr_state: list[SPRCavernView] = await get_spr_state()

# Call 3 — risk scores (to derive shock magnitude from current score)
risk_scores: list[RiskScoreView] = await get_risk_scores()
```

### 4.2 Data extracted from subgraph nodes

| Node type | Fields used | Used for |
|---|---|---|
| `Corridor` | `throughput_mbpd`, `choke_severity` | Baseline supply flow + shock fraction |
| `Feeds` edge | `throughput_share_pct` | What fraction of the downstream port's crude transits this corridor |
| `Port` | `congestion` | Throughput friction multiplier |
| `Supplies` edge | `throughput_share_pct` | What fraction of this refinery's crude arrives via this port |
| `Refinery` | `capacity_mbpd`, `inventory_days` | Daily processing capacity + buffer days before stockout |
| `SPRCavern` | `current_fill_mmt`, `capacity_mmt` | Emergency buffer available |
| `FeedsReserve` edge | (existence) | Links refinery ↔ which SPR cavern it draws from |

### 4.3 Subgraph data extraction — exact field access

```python
# In graph_builder.py — extract ARIO inputs from SubgraphView
def extract_supply_chain(subgraph: SubgraphView, trigger_entity: str) -> ARIOInputs:
    corridors  = [n for n in subgraph.nodes if n.entity_type == "Corridor"
                  and n.display_name == trigger_entity]
    ports      = [n for n in subgraph.nodes if n.entity_type == "Port"]
    refineries = [n for n in subgraph.nodes if n.entity_type == "Refinery"]
    caverns    = [n for n in subgraph.nodes if n.entity_type == "SPRCavern"]

    feeds_edges    = [e for e in subgraph.edges if e.edge_type == "FEEDS"]
    supplies_edges = [e for e in subgraph.edges if e.edge_type == "SUPPLIES"]

    # Per-port corridor share (FEEDS edge attribute)
    port_corridor_share: dict[str, float] = {}
    for e in feeds_edges:
        port_uuid = e.target_uuid
        port_corridor_share[port_uuid] = e.attributes.get("throughput_share_pct") or 0.42

    # Per-refinery port share (SUPPLIES edge attribute)
    refinery_port_share: dict[str, float] = {}
    for e in supplies_edges:
        ref_uuid = e.target_uuid
        refinery_port_share[ref_uuid] = e.attributes.get("throughput_share_pct") or 0.70

    return ARIOInputs(
        corridors=corridors,
        ports=ports,
        refineries=refineries,
        caverns=caverns,
        port_corridor_share=port_corridor_share,
        refinery_port_share=refinery_port_share,
    )
```

### 4.4 Fallback values when KB attributes are None

The KB may not have throughput_share_pct set for all edges on first run. Use calibrated India-specific defaults (see §8) rather than crashing:

```python
# graph_builder.py
FALLBACK_HORMUZ_PORT_SHARE   = 0.42   # IEA 2025: 42% of India crude via Hormuz
FALLBACK_PORT_REFINERY_SHARE = 0.70   # PPAC 2025: weighted average port→refinery share
FALLBACK_INVENTORY_DAYS      = 18.0   # PPAC 2024: India average crude stock cover
FALLBACK_CAPACITY_MBPD       = 0.30   # smaller refinery default if missing
FALLBACK_CHOKE_SEVERITY      = 0.95   # Hormuz — only triggered for Hormuz anyway
```

---

## 5. ARIO Model — Full Specification

### 5.1 Model summary

ARIO (Adaptive Regional Input-Output) extends the Leontief IO model to handle supply-side bottlenecks dynamically. At each day `t`:

1. **Shock input:** the upstream supply reduction fraction `ρ(t)` for each affected node
2. **Production bottleneck:** each sector's output is limited by the minimum of demand-driven capacity and resource availability
3. **Demand propagation:** reduced output in sector `j` reduces demand for inputs from sector `i` by the IO coefficient `a_ij`
4. **Adaptive behaviour:** firms over-order (ratio `α`) to hedge against expected shortage; this amplifies the initial shock
5. **Recovery:** capacity recovers at rate `μ` per day once the shock lifts

### 5.2 Equations

```
# Supply gap (day 0)
gap_mbpd(t=0) = throughput_mbpd × choke_severity × shock_fraction(risk_score)

# shock_fraction: nonlinear mapping from risk score to blockage fraction
# score 0.70 → 30% blockage, score 0.90 → 75%, score 1.0 → 95%
shock_fraction(s) = 0.0 if s < 0.70 else min(0.95, (s - 0.70) / 0.30 * 0.65 + 0.30)

# Per-refinery feedstock gap (day t)
refinery_gap_mbpd(r, t) = (
    gap_mbpd(t)
    × port_corridor_share[port(r)]
    × refinery_port_share[r]
)

# SPR draw (day t)
spr_draw_mmt(t) = min(
    refinery_gap_mbpd(t) × 0.137 × drawdown_efficiency,   # mbpd → mmt/day
    MAX_DAILY_DRAW_MMT,                                     # ISPRL operational limit
    remaining_spr_above_buffer,                             # never below 3-day buffer
)

# Remaining SPR (day t+1)
spr_fill(t+1) = spr_fill(t) - spr_draw_mmt(t)

# Days cover remaining (scalar output)
days_cover(t) = spr_fill(t) / india_daily_consumption_mmt

# Price impact (USD/bbl)
price_impact = -gap_mbpd / (INDIA_DAILY_CONSUMPTION_MBPD × PRICE_ELASTICITY_SR)

# Indirect economic cascade (GDP proxy)
direct_impact_bn_usd  = gap_mbpd × 365 / gap_duration_days × BRENT_PRICE_USD × 0.159
gdp_proxy_impact_pct  = (direct_impact_bn_usd × INDIRECT_MULTIPLIER) / INDIA_GDP_BN_USD × 100
```

### 5.3 Day-by-day propagation loop

```python
# ario.py
async def run_ario(inputs: ARIOInputs, params: ARIOParams) -> ARIOResult:
    """
    Full ARIO propagation. Returns per-day vectors.
    Runtime: O(horizon × n_refineries). At 30 days, 5 refineries: ~0.3ms.
    """
    horizon        = params.horizon_days           # default 30
    spr_fill       = params.initial_spr_fill_mmt   # from get_spr_state()
    feedstock_gaps = []                            # per-day list[float] → ScenarioOutputData
    spr_fills      = []
    days_cover_arr = []

    shock          = _compute_initial_shock(inputs, params)
    recovery_rate  = params.capacity_recovery_rate_per_day   # 0.05 = 5%/day

    for t in range(horizon):
        # Shock decays as capacity recovers (or is held constant for blockade scenario)
        effective_shock = shock * max(0.0, 1.0 - recovery_rate * t)

        # Aggregate refinery feedstock gap today (sum across all refineries)
        day_gap_mbpd = sum(
            _refinery_gap(r, effective_shock, inputs)
            for r in inputs.refineries
            if r.attributes.get("inventory_days", FALLBACK_INVENTORY_DAYS) < t
            # Refineries whose inventory is exhausted start feeling the gap
        )
        day_gap_mbpd = max(0.0, day_gap_mbpd)

        # SPR compensates (up to operational limit and minimum buffer)
        spr_draw  = _spr_draw(day_gap_mbpd, spr_fill, params)
        spr_fill  = max(0.0, spr_fill - spr_draw)
        days_cover = spr_fill / params.india_daily_consumption_mmt

        feedstock_gaps.append(round(day_gap_mbpd, 4))
        spr_fills.append(round(spr_fill, 4))
        days_cover_arr.append(round(days_cover, 2))

        if spr_fill <= 0 and day_gap_mbpd > 0:
            break  # SPR exhausted — scenario terminates early

    total_gap    = sum(feedstock_gaps)
    price_impact = _price_impact(max(feedstock_gaps), params)
    gdp_proxy    = _gdp_proxy(total_gap, len(feedstock_gaps), params)

    return ARIOResult(
        feedstock_gap_timeline=feedstock_gaps,
        gap_mbpd=round(max(feedstock_gaps), 4),
        gap_duration_days=float(len(feedstock_gaps)),
        price_impact_low=round(price_impact * 0.7, 2),
        price_impact_high=round(price_impact * 1.4, 2),
        spr_depletion_days=round(days_cover_arr[-1] if days_cover_arr else 0.0, 1),
        gdp_proxy_impact_pct=round(gdp_proxy, 3),
    )
```

### 5.4 SPR draw logic

```python
def _spr_draw(gap_mbpd: float, current_fill_mmt: float, params: ARIOParams) -> float:
    """
    Calculate how much to draw from SPR today.
    - Convert gap from mbpd to mmt/day: gap_mbpd × 0.137 (1 mbl ≈ 0.137 mmt)
    - Cap at ISPRL operational drawdown rate: 0.1 MMT/day (ISPRL 2025)
    - Cap at what remains above the 3-day strategic buffer
    """
    gap_mmt_per_day = gap_mbpd * 0.137
    buffer_floor    = params.india_daily_consumption_mmt * params.spr_buffer_days  # 3 days
    available       = max(0.0, current_fill_mmt - buffer_floor)
    draw            = min(gap_mmt_per_day, available, params.max_daily_draw_mmt)
    return max(0.0, draw)
```

---

## 6. GNN Surrogate — Sandbox Fast Path

### 6.1 Purpose

When a HIGH signal arrives and risk is in the `elevated` band (0.45–0.70), the sandbox forks a speculative scenario **before** the actual threshold crossing. This must complete in ≤150ms so it does not block the ingest loop. Full ARIO takes ~2,500ms. The GNN surrogate is a trained approximator that accepts the supply-chain graph and returns approximate ARIO outputs in a single forward pass on the T4 GPU.

### 6.2 Architecture

```python
# gnn_surrogate.py
import torch
import torch.nn as nn
from torch_geometric.nn import SAGEConv

class ARIOSurrogate(nn.Module):
    """
    3-layer GraphSAGE that maps supply-chain graph → (gap_mbpd, price_impact_mid, spr_days).

    Input node features (10 per node):
        [throughput_mbpd, choke_severity, capacity_mbpd, inventory_days,
         current_fill_mmt, capacity_mmt, congestion, risk_score,
         throughput_share, node_type_onehot_4bit]

    Edge features (2 per edge):
        [throughput_share_pct, edge_type_onehot_4bit (truncated to 2)]

    Output (graph-level regression, 3 scalars via global mean pool + MLP):
        [gap_mbpd, price_impact_mid_usd_bbl, spr_depletion_days]
    """
    def __init__(self, in_channels: int = 10, hidden: int = 64, out_channels: int = 3):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden)
        self.conv2 = SAGEConv(hidden, hidden)
        self.conv3 = SAGEConv(hidden, hidden // 2)
        self.head  = nn.Sequential(
            nn.Linear(hidden // 2, 32),
            nn.ReLU(),
            nn.Linear(32, out_channels),
        )

    def forward(self, x, edge_index, batch):
        from torch_geometric.nn import global_mean_pool
        import torch.nn.functional as F
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = F.relu(self.conv3(x, edge_index))
        x = global_mean_pool(x, batch)
        return self.head(x)
```

### 6.3 Training procedure

**Training data generation:**
1. Seed the ARIO model with 500 randomised supply-chain parameter combinations (Monte Carlo over the India parameter distributions)
2. For each seed: vary `choke_severity` ∈ [0.3, 1.0], `throughput_share_pct` ∈ [0.20, 0.65], `inventory_days` ∈ [10, 30], `risk_score` ∈ [0.5, 1.0]
3. Run full ARIO → record `(gap_mbpd, price_impact_mid, spr_depletion_days)` as labels
4. Train ARIOSurrogate with MSELoss, AdamW, LR=1e-3, batch_size=32, epochs=200

**Training script location:** `scenario_agent/train_surrogate.py`  
**Trained model saved to:** `scenario_agent/surrogate_weights.pt` (committed to repo; re-train monthly)

**Target accuracy:** R² > 0.95 on held-out 20% split for all three outputs.

### 6.4 Inference path

```python
# gnn_surrogate.py
_model: ARIOSurrogate | None = None
_device: torch.device | None = None

def _load_model() -> tuple[ARIOSurrogate, torch.device]:
    global _model, _device
    if _model is None:
        weights_path = Path(__file__).parent / "surrogate_weights.pt"
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model  = ARIOSurrogate().to(device)
        model.load_state_dict(torch.load(weights_path, map_location=device))
        model.eval()
        _model, _device = model, device
    return _model, _device

async def gnn_predict(inputs: ARIOInputs, risk_score: float) -> ARIOResult:
    """
    Single forward pass → approximate ARIO outputs. ≤150ms on T4 GPU.
    Called only from sandbox path (score 0.45–0.70).
    """
    model, device = _load_model()
    data          = _build_pyg_graph(inputs, risk_score, device)

    with torch.no_grad():
        out = model(data.x, data.edge_index, data.batch)  # shape (1, 3)

    gap_mbpd, price_mid, spr_days = out[0].cpu().tolist()
    gap_mbpd  = max(0.0, gap_mbpd)
    price_mid = max(0.0, price_mid)
    spr_days  = max(0.0, spr_days)

    return ARIOResult(
        feedstock_gap_timeline=[gap_mbpd] * int(spr_days),   # approximate daily profile
        gap_mbpd=round(gap_mbpd, 3),
        gap_duration_days=round(spr_days, 1),
        price_impact_low=round(price_mid * 0.7, 2),
        price_impact_high=round(price_mid * 1.4, 2),
        spr_depletion_days=round(spr_days, 1),
        gdp_proxy_impact_pct=None,   # not output by surrogate; set None for speculative
    )
```

---

## 7. Hardcoded India Parameters

All parameters are **labeled, sourced, and editable**. They appear in `ScenarioOutputData.assumptions` so judges can audit every number. They live in `scenario_agent/parameters.py`.

```python
# scenario_agent/parameters.py
from dataclasses import dataclass

@dataclass(frozen=True)
class IndiaEnergyParams:
    # ── Supply volumes ─────────────────────────────────────────────────────────
    daily_consumption_mbpd:    float = 5.15     # PPAC Monthly Review, March 2025
    import_dependence_pct:     float = 0.882    # PPAC Annual Report 2024-25
    hormuz_india_share_pct:    float = 0.42     # IEA Oil Market Report, Feb 2025
    bab_el_mandeb_share_pct:   float = 0.08     # IEA, same source (Houthi diversion)

    # ── Unit conversion ────────────────────────────────────────────────────────
    mbpd_to_mmt_per_day:       float = 0.137    # 1 million bbl = 0.137 MMT (Brent density)

    # ── SPR (ISPRL 2025 technical data) ───────────────────────────────────────
    spr_total_capacity_mmt:    float = 5.33     # Vizag 1.33 + Mangaluru 1.50 + Padur 2.50
    spr_initial_fill_mmt:      float = 5.00     # approximate current fill (ISPRL Q1 2025)
    spr_buffer_days:           float = 3.0      # strategic minimum — never draw below this
    max_daily_draw_mmt:        float = 0.10     # ISPRL operational drawdown limit, MMT/day

    # ── ARIO model ────────────────────────────────────────────────────────────
    capacity_recovery_rate:    float = 0.05     # 5%/day capacity recovery post-shock
    horizon_days:              int   = 30       # max simulation window
    overordering_alpha:        float = 1.10     # Hallegatte 2008 over-ordering coefficient

    # ── Price elasticity ──────────────────────────────────────────────────────
    price_elasticity_sr:       float = -0.10    # short-run demand elasticity, India: IEA 2022
    brent_price_usd:           float = 75.0     # USD/bbl baseline (updated from live score)

    # ── IO coefficients (MOSPI Input-Output Table 2018-19) ────────────────────
    transport_petroleum_share:    float = 0.18  # Transport sector petroleum cost share
    petrochemicals_crude_share:   float = 0.35  # Petrochemicals crude feedstock share
    power_petroleum_share:        float = 0.08  # Power sector petroleum cost share

    # ── GDP cascade ───────────────────────────────────────────────────────────
    indirect_multiplier:       float = 14.0     # Inoue & Todo (2019) Nature Sustainability
    india_gdp_bn_usd:          float = 3900.0   # World Bank 2024 estimate

INDIA = IndiaEnergyParams()

def build_assumptions_dict(
    params: IndiaEnergyParams,
    live_risk_score: float,
    live_brent_usd: float,
) -> dict:
    """Build the labeled assumptions dict that goes into ScenarioOutputData.assumptions."""
    return {
        "import_dependence_pct":    {"value": params.import_dependence_pct * 100,
                                     "unit": "%", "source": "PPAC Annual Report 2024-25"},
        "hormuz_share_pct":         {"value": params.hormuz_india_share_pct * 100,
                                     "unit": "%", "source": "IEA Oil Market Report Feb 2025"},
        "spr_total_mmt":            {"value": params.spr_total_capacity_mmt,
                                     "unit": "MMT", "source": "ISPRL 2025"},
        "spr_buffer_days":          {"value": params.spr_buffer_days,
                                     "unit": "days", "source": "ISPRL operational policy"},
        "max_daily_spr_draw_mmt":   {"value": params.max_daily_draw_mmt,
                                     "unit": "MMT/day", "source": "ISPRL 2025"},
        "price_elasticity_sr":      {"value": params.price_elasticity_sr,
                                     "unit": "",   "source": "IEA India Demand Model 2022"},
        "io_transport_petroleum":   {"value": params.transport_petroleum_share,
                                     "unit": "cost share", "source": "MOSPI IO Table 2018-19"},
        "io_petrochemicals_crude":  {"value": params.petrochemicals_crude_share,
                                     "unit": "cost share", "source": "MOSPI IO Table 2018-19"},
        "indirect_multiplier":      {"value": params.indirect_multiplier,
                                     "unit": "×", "source": "Inoue & Todo 2019, Nat. Sust."},
        "capacity_recovery_rate":   {"value": params.capacity_recovery_rate * 100,
                                     "unit": "%/day", "source": "Hallegatte 2008, calibrated"},
        "live_risk_score":          {"value": round(live_risk_score, 4),
                                     "unit": "0..1", "source": "System 1 fusion (live)"},
        "live_brent_usd":           {"value": round(live_brent_usd, 2),
                                     "unit": "USD/bbl", "source": "yfinance BZ=F (live)"},
    }
```

---

## 8. Runner — Entry Point

```python
# scenario_agent/runner.py
"""
Entry point called by orchestration/triggers.py.

  await run_scenario(trigger_entity, scenario_id, status="confirmed")   # cold path
  await run_scenario(trigger_entity, scenario_id, status="speculative") # sandbox path

The caller (triggers.py) does NOT need to know which model ran — it calls run_scenario()
and gets back the scenario_id. The scenario result is already in the KB.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from knowledge.api.read import get_subgraph, get_spr_state, get_risk_scores
from knowledge.api.write import write_scenario
from contracts.outputs import ScenarioOutputData

from .graph_builder import extract_supply_chain, build_ario_params
from .ario import run_ario
from .gnn_surrogate import gnn_predict
from .parameters import INDIA, build_assumptions_dict

log = logging.getLogger(__name__)

Status = Literal["confirmed", "speculative"]


async def run_scenario(
    trigger_entity: str,
    scenario_id: str | None = None,
    status: Status = "confirmed",
) -> str:
    """
    Run the ARIO disruption model and write ScenarioOutputData to the KB.
    Returns scenario_id.

    status="confirmed"   → full ARIO propagation (cold path, score ≥ 0.70)
    status="speculative" → GNN surrogate (sandbox path, score 0.45–0.70)
    """
    scenario_id = scenario_id or f"sc-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8]}"
    log.info("[S2] run_scenario start — entity='%s' id=%s status=%s",
             trigger_entity, scenario_id, status)

    # 1. Fetch KB data
    subgraph   = await get_subgraph(trigger_entity, hops=3)
    spr_state  = await get_spr_state()
    risk_views = await get_risk_scores()

    # 2. Derive live risk score and Brent price from KB
    live_score  = _get_entity_risk(risk_views, trigger_entity)
    live_brent  = _get_brent_price(risk_views)  # price sub-agent updates this

    # 3. Build ARIO inputs
    inputs = extract_supply_chain(subgraph, trigger_entity)
    params = build_ario_params(spr_state, live_score, live_brent)

    # 4. Run model
    if status == "speculative":
        result = await gnn_predict(inputs, live_score)
        confidence = max(0.0, (live_score - 0.45) / 0.25)  # linear 0→1 over elevated band
    else:
        result     = await run_ario(inputs, params)
        confidence = min(1.0, live_score)

    # 5. Build output
    assumptions = build_assumptions_dict(INDIA, live_score, live_brent)
    data = ScenarioOutputData(
        scenario_id=scenario_id,
        trigger_entity=trigger_entity,
        status=status,
        confidence=round(confidence, 4),
        gap_mbpd=result.gap_mbpd,
        gap_duration_days=result.gap_duration_days,
        feedstock_gap_timeline=result.feedstock_gap_timeline,
        price_impact_low=result.price_impact_low,
        price_impact_high=result.price_impact_high,
        spr_depletion_days=result.spr_depletion_days,
        gdp_proxy_impact_pct=result.gdp_proxy_impact_pct,
        assumptions=assumptions,
    )

    # 6. Write to KB — creates ScenarioOutput entity + AFFECTS_SCENARIO edge
    episode_ref = await write_scenario(data)
    log.info("[S2] scenario written — id=%s ref=%s gap=%.2fmbpd spr=%.1fd",
             scenario_id, episode_ref, result.gap_mbpd, result.spr_depletion_days)

    return scenario_id


def _get_entity_risk(risk_views: list, entity: str) -> float:
    for v in risk_views:
        if v.entity.lower() == entity.lower():
            return v.score
    return 0.72   # fallback: just above action threshold (why we're running at all)


def _get_brent_price(risk_views: list) -> float:
    """Extract Brent price from RISK_STATE factors if price sub-agent wrote it."""
    for v in risk_views:
        if hasattr(v, "brent_price_usd") and v.brent_price_usd:
            return v.brent_price_usd
    return INDIA.brent_price_usd   # fallback to hardcoded baseline
```

---

## 9. Graph Builder

```python
# scenario_agent/graph_builder.py
from dataclasses import dataclass, field
from typing import Any

from .parameters import INDIA, IndiaEnergyParams

@dataclass
class ARIOInputs:
    corridors:             list[Any]          # SubgraphNode list
    ports:                 list[Any]
    refineries:            list[Any]
    caverns:               list[Any]
    port_corridor_share:   dict[str, float]   # port_uuid → fraction via this corridor
    refinery_port_share:   dict[str, float]   # refinery_uuid → fraction via its port


@dataclass
class ARIOParams:
    initial_spr_fill_mmt:          float
    india_daily_consumption_mmt:   float
    horizon_days:                  int
    capacity_recovery_rate_per_day: float
    overordering_alpha:            float
    spr_buffer_days:               float
    max_daily_draw_mmt:            float
    shock_fraction:                float   # derived from risk_score at call time
    brent_price_usd:               float


def build_ario_params(
    spr_state: list[Any],
    live_risk_score: float,
    live_brent_usd: float,
    params: IndiaEnergyParams = INDIA,
) -> ARIOParams:
    total_fill_mmt = sum(
        (c.current_fill_mmt or 0.0) for c in spr_state
    ) or params.spr_initial_fill_mmt

    daily_consumption_mmt = (
        params.daily_consumption_mbpd * params.mbpd_to_mmt_per_day
    )
    shock = _shock_fraction(live_risk_score)

    return ARIOParams(
        initial_spr_fill_mmt=total_fill_mmt,
        india_daily_consumption_mmt=daily_consumption_mmt,
        horizon_days=params.horizon_days,
        capacity_recovery_rate_per_day=params.capacity_recovery_rate,
        overordering_alpha=params.overordering_alpha,
        spr_buffer_days=params.spr_buffer_days,
        max_daily_draw_mmt=params.max_daily_draw_mmt,
        shock_fraction=shock,
        brent_price_usd=live_brent_usd,
    )


def _shock_fraction(risk_score: float) -> float:
    """
    Map risk score → corridor blockage fraction.
    Nonlinear: 0.70 → 30%, 0.90 → 75%, 1.0 → 95%.
    Below 0.70: no shock (shouldn't be called, but safe).
    """
    if risk_score < 0.70:
        return 0.0
    return min(0.95, (risk_score - 0.70) / 0.30 * 0.65 + 0.30)
```

---

## 10. Internal Data Models

```python
# scenario_agent/models.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ARIOResult:
    """Output of either ARIO propagation or GNN surrogate."""
    feedstock_gap_timeline: list[float]   # per-day gap (mbpd); len = gap_duration_days
    gap_mbpd:               float
    gap_duration_days:      float
    price_impact_low:       float         # USD/bbl
    price_impact_high:      float         # USD/bbl
    spr_depletion_days:     float         # days of SPR cover remaining at end of simulation
    gdp_proxy_impact_pct:   Optional[float] = None   # None for GNN surrogate output
```

---

## 11. Integration Contract (what triggers.py expects)

`triggers.py` calls `run_scenario()` and expects:

```python
# In triggers._cold_pipeline():
from scenario_agent.runner import run_scenario
scenario_id = await run_scenario(
    trigger_entity=entity,
    scenario_id=scenario_id,
    status="confirmed",
)
# After this call:
# - ScenarioOutputData is written to KB via write_scenario()
# - AFFECTS_SCENARIO edge links trigger_entity → ScenarioOutput node
# - Systems 3+4 can immediately call get_subgraph() and find the scenario
```

`runner.py` must:
1. Never raise — catch all exceptions internally; log and return a minimal partial ScenarioOutputData on failure
2. Write to KB before returning — Systems 3+4 rely on the KB being updated
3. Return the `scenario_id` string (not the EpisodeRef) so `triggers.py` can pass it to Systems 3+4

**Failure handling in runner.py:**
```python
async def run_scenario(...) -> str:
    try:
        ...  # main path
        return scenario_id
    except Exception as exc:
        log.error("[S2] run_scenario FAILED — entity='%s' error=%s", trigger_entity, exc)
        # Write a partial result so Systems 3+4 don't hang waiting for a scenario that never arrives
        await _write_partial_scenario(trigger_entity, scenario_id, status, str(exc))
        return scenario_id
```

---

## 12. What System 2 Does NOT Do

These boundaries prevent scope creep and keep System 2 focused:

| Out of scope | Who does it |
|---|---|
| Risk score computation | System 1 (sensory_agent fusion) |
| Procurement route ranking | System 3 (alt_procurement_agent) |
| SPR draw schedule optimisation | System 4 (reserve_optim_agent) |
| Copilot Q&A on scenario | System 5 (copilot_agent) |
| Reading raw AIS/GDELT signals | System 1 only |
| Writing RISK_STATE edges | System 1 / SAGE ingest only |
| Speculative risk on live nodes | Forbidden — `status="speculative"` scenarios are isolated |

---

## 13. GPU Configuration

System 2 runs in the `system2-scenario` Docker container with GPU access.

```yaml
# docker-compose.yml excerpt
system2-scenario:
  build: ./scenario_agent
  depends_on:
    sage-core: { condition: service_healthy }
  environment:
    - REDIS_URL=redis://redis:6379/0
    - FALKORDB_HOST=falkordb
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  volumes:
    - ./scenario_agent/surrogate_weights.pt:/app/surrogate_weights.pt:ro
```

**GPU memory budget:**
- ARIOSurrogate model weights: ~2 MB (tiny — 3 GraphSAGE layers, 64 hidden)
- Inference batch: negligible (single graph, ~10 nodes)
- Resident VRAM: ~50 MB
- Leaves ~15.95 GB of T4 VRAM for other systems

**Startup:** `gnn_surrogate._load_model()` is called lazily on first sandbox invocation. For demo day, pre-warm by calling `run_scenario(trigger_entity="warmup", status="speculative")` in the container healthcheck.

---

## 14. Testing Plan

### Unit tests (`tests/test_scenario_agent/`)

| Test | What it checks |
|---|---|
| `test_shock_fraction.py` | score=0.70→0.30, score=0.90→0.75, score=1.0→0.95, score=0.69→0.0 |
| `test_ario_spr_draw.py` | SPR draw never exceeds operational limit; never draws below buffer floor |
| `test_ario_inventory_gate.py` | Refineries with 18-day inventory don't feel gap until day 18 |
| `test_ario_full_run.py` | 30-day run on synthetic inputs; gap + SPR + price coherent |
| `test_build_assumptions.py` | All keys present; sources non-empty |
| `test_runner_writes_to_kb.py` | Mock KB API; assert write_scenario() called with valid ScenarioOutputData |

### Integration test

```python
# tests/integration/test_s2_e2e.py
async def test_hormuz_scenario():
    """
    Real ARIO run against the seeded KB state from the e2e fixture.
    Hormuz risk_score=0.82 → run_scenario("Strait of Hormuz", status="confirmed")
    Assert: gap_mbpd in [0.5, 3.0], spr_depletion_days > 0, len(feedstock_gap_timeline) > 0
    """
```

### GNN surrogate accuracy test

```python
# tests/test_scenario_agent/test_gnn_accuracy.py
def test_surrogate_vs_ario_r2():
    """
    Run 50 random inputs through both ARIO and surrogate.
    Assert R² > 0.90 for gap_mbpd.
    This test is re-run after every re-training of surrogate_weights.pt.
    """
```

---

## 15. Demo Day Output

On `DEMO_MODE=true`, `runner.py` plays back pre-recorded scenario results from `demo_cache/scenario_sc-20260223.json` instead of running ARIO. The output shape is identical to a live run; the values are the pre-computed golden-path numbers.

**Target demo numbers (Hormuz scenario, Feb 23 2026):**
- `gap_mbpd`: 1.2
- `gap_duration_days`: 14
- `spr_depletion_days`: 6.5 (at 0.1 MMT/day draw rate)
- `price_impact_low`: $8/bbl, `price_impact_high`: $22/bbl
- `gdp_proxy_impact_pct`: 0.42%
- Cold path latency: ~2,500ms
- Sandbox (GNN) latency: ≤150ms on T4

---

## 16. Build Order

| Step | Deliverable | Done when |
|---|---|---|
| 1 | `parameters.py` complete | All 15 constants present, sourced, in `assumptions` dict |
| 2 | `models.py` complete | `ARIOInputs`, `ARIOParams`, `ARIOResult` dataclasses defined |
| 3 | `graph_builder.py` complete | `extract_supply_chain()` runs against mock subgraph; correct fallbacks |
| 4 | `ario.py` complete | 30-day Hormuz run produces coherent timeline; SPR buffer respected |
| 5 | Unit tests pass | All tests in §14 green |
| 6 | `runner.py` writes to KB | `test_runner_writes_to_kb.py` passes with real KB connection |
| 7 | Cold path e2e | `test_s2_e2e.py` green against seeded FalkorDB |
| 8 | GNN surrogate trained | `test_gnn_accuracy.py` passes; R² > 0.90 |
| 9 | Sandbox fast path | GNN called for speculative status; latency < 150ms measured |
| 10 | Demo cache written | `demo_cache/scenario_sc-20260223.json` pre-recorded; plays back correctly |
