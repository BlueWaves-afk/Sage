# S.A.G.E. — Core Scientific & Machine Learning Methodology

This document outlines the design decisions, mathematical models, and machine learning architectures implemented in S.A.G.E. (System for Anticipatory supply-chain & Geopolitical Resilience).

---

## 1. System 1 (Sensory Agent, Ingestion & Risk Fusion)

### 📊 Bayesian Online Changepoint Detection (BOCD)
* **File:** [prices.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./sensory_agent/prices.py)
* **Why this method:** Standard rolling averages are too laggy, and static threshold rules cause alert fatigue. BOCD detects changes in the underlying generative parameter of a time series in real-time.
* **Details:** We implement a lightweight conjugate Gaussian Normal-Inverse-Gamma online update (Welford's algorithm for running variance) combined with a hazard function. It runs in $O(1)$ time and memory per tick, and only emits signals when the posterior probability of a changepoint $P(r_t = 0)$ crosses $0.60$ or a return's Z-score exceeds $3.5$. This filters out normal price noise and only captures structural shifts.

### 🎭 Local Multilingual Sentiment & Severity Model
* **File:** [sentiment.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./sensory_agent/sentiment.py)
* **Why this model:** `tabularisai/multilingual-sentiment-analysis` was selected to run sentiment classification locally on the agent's machine. Calling a cloud-based LLM (like AWS Bedrock Nova) for every news article or GDELT row is cost-prohibitive at scale.
* **Details:** The model categorises text into 5 classes: `Highly Risky`, `Risky`, `Satisfactory`, `Safe`, and `Completely Safe`. We map these discrete categories to a continuous severity float scale in $[0, 1]$ (e.g. `Highly Risky` $\rightarrow 0.95$) and GDELT-style tone score in $[-8.0, 8.0]$.

### 🌐 H3 Spatial Indexing & Anomaly Clustering
* **File:** [ais.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./sensory_agent/ais.py)
* **Why this format:** Geographic coordinates (Latitude/Longitude) are continuous and hard to query or aggregate. Uber's H3 spatial index quantizes the Earth's surface into hexagonal cells.
* **Details:** We use **H3 Resolution 5** (hexagons of ~252 km²). This is the optimal spatial resolution for major maritime corridors (like the Strait of Hormuz or Bab-el-Mandeb) and port anchorage limits. Anomaly events (e.g. AIS transmission gap $>4$ hours) are mapped to H3 cells. To prevent spamming the ingest queue, we cluster anomalies in the same H3 cell and rate-limit emissions to one cluster signal per cell per 5 minutes.

### 🛡️ Calibrated Risk Fusion (GBM + Platt Scaling + SHAP)
* **File:** [fusion.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./sensory_agent/fusion.py)
* **Why this model:** Weighted sum fallbacks are robust but fail to capture nonlinear feature interactions (e.g., an AIS gap in a corridor is significantly riskier if commodity prices are already stressed). A Gradient Boosting Machine (GBM) learns these non-linear boundaries.
* **Details:**
  * **Calibration:** A raw classification model output is not a probability. We apply **Platt Scaling** (fitting a logistic sigmoid to the classifier's output) to output a calibrated probability of supply chain disruption in $[0, 1]$.
  * **SHAP Explainability:** To display the exact contribution of each channel (AIS, News, Price, Sanctions) on the UI's radar chart, we use **SHAP (SHapley Additive exPlanations)** values. The final risk score decomposes additively:
    $$\text{Score} = \text{Base Rate} + \phi_{\text{ais}} + \phi_{\text{gdelt}} + \phi_{\text{price}} + \phi_{\text{sanctions}}$$
    This ensures mathematically consistent attributions that sum exactly to the final prediction.

---

## 2. System 2 (Scenario Simulation & Cascade Models)

### 📈 Adaptive Regional Input-Output (ARIO) Model
* **File:** [ario.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./scenario_agent/ario.py)
* **Why this method:** Static Input-Output tables (Leontief matrices) only model steady-state flows. They cannot simulate the dynamic, time-varying propagation of supply shocks, stockout timing, or price elasticity adjustments.
* **Details:** ARIO models the economy as a network of sectors. In each time step (daily resolution), refineries and industries draw from inventories. If a corridor is blocked, inventory levels drop. When stocks deplete, production halts, propagating the bottleneck downstream to consumer sectors. S.A.G.E. configures this with a 140-sector Indian economic matrix.

### ⚡ Analytic Fast Path (replaces GNN surrogate)
* **File:** [runner.py](scenario_agent/runner.py)
* **Why this design:** A GNN surrogate was evaluated but rejected for the Hormuz-topology use case. The full ARIO cascade (`scenario_agent/ario.py`) completes in ~20 ms on CPU (fixed-size sector matrix, no gradient computation). A trained surrogate (~13 ms inference) would be *slower* to develop, degrade on out-of-distribution closures near 100%, and introduce a calibration gap vs the analytic ground truth. The dead surrogate code lives in `scenario_agent/gnn/` with a README explaining this reasoning. The analytic path runs at interactive speed (< 40 ms end-to-end including Monte Carlo n=300).

---

## 3. System 3 (Alternative Sourcing & Procurement)

### ⚖️ Multi-Criteria TOPSIS Ranking
* **File:** [rank.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./alt_procurement_agent/rank.py)
* **Why this method:** Ranking alternative suppliers is a multi-dimensional problem (price, sulfur content, API gravity, geographical risk, shipping time).
* **Details:** **TOPSIS** (Technique for Order of Preference by Similarity to Ideal Solution) ranks candidates by choosing the alternative closest to the *Positive Ideal Solution (PIS)* and furthest from the *Negative Ideal Solution (NIS)* using Euclidean distance. This provides a robust, non-arbitrary scoring method.

### 🗺️ Cost-matrix routing (MILP deferred)
* **File:** [routing.py](alt_procurement_agent/routing.py)
* **Why this design:** OR-Tools MILP matters for multi-cargo fleet allocation under shared capacity constraints. For SAGE's per-entity single-cargo procurement problem (one trigger entity, one replacement cargo), the minimum over a small corridor cost-matrix produces the same optimal route as a full MILP — the added complexity buys nothing at this scale. The cost matrix uses Clarkson/Baltic base freight rates + bypass premiums + war-risk insurance + closure exclusion. A drop-in MILP upgrade is documented in `alt_procurement_agent/routing.py` for when multi-cargo fleet allocation is needed.

---

## 4. System 4 (Strategic Petroleum Reserve Optimization)

### 🧠 Stochastic Dynamic Programming (SDP)
* **File:** [sdp.py](file:///Users/rishidas/Documents/Hackathons/ET_AI_Hackathon/S.A.G.E./reserve_optim_agent/sdp.py)
* **Why this method:** Deciding when to release oil from the Strategic Petroleum Reserve (SPR) is a sequential decision-making problem under uncertainty (fluctuating oil prices, future disruption probability, and replenishment lead times).
* **Details:** We solve the **Bellman Equation** over a discrete state space (current SPR inventory, crude price, and risk state):
  $$V(s, p, r) = \max_{a \in \mathcal{A}} \left\{ U(s, p, r, a) + \gamma \sum_{s', p', r'} P(s', p', r' \mid s, p, r, a) V(s', p', r') \right\}$$
  Where action $a$ is to Release, Hold, or Refill. This produces an optimal policy lookup table mapping any state to the optimal action, maximizing energy security while minimizing financial loss.

---

## 5. End-to-End Response Time Measurement

The Command Center shows "Signal → Recommendation: N s" — a measured latency, not an estimate.

### Clock definition

| Boundary | Definition |
|---|---|
| **t₀ — Signal received** | UTC timestamp of the first System-1 agent `done` trace event for the triggering entity in `sage:agent_trace:recent`. This is the moment a live ingested signal (AIS gap, news event, price change, or sanctions hit) has been fully processed into the knowledge base and a risk score update has been committed. |
| **t₁ — Scenario complete** | UTC timestamp of the System-2 `scenario` agent `done` event (ARIO cascade + n=300 Monte Carlo + Leontief IO sectoral impact). |
| **t₂ — Procurement complete** | UTC timestamp of the System-3 `procurement` agent `done` event (TOPSIS multi-criteria ranking over available suppliers and routes). |
| **t_final — Reserve recommendation** | UTC timestamp of the System-4 `reserve` agent `done` event (CMDP Lagrangian + SDP Bellman policy). If System 4 did not fire, `t_final = t₂`. |

**Total latency = t_final − t₀**

### Implementation

`GET /api/response-time` reads the last 200 entries of `sage:agent_trace:recent` (bounded Redis list), groups them into pipeline runs (a run boundary is a System-1 `done` event arriving >60 s after the previous System-1 `done` event), computes per-stage deltas, and returns:

- `last_run` — per-stage breakdown for the most recent completed run
- `rolling_median_s` — median total latency across the last 5 runs
- `runs` — last 5 run summaries

The strip in the Command Center displays `rolling_median_s`; hovering shows the `last_run` breakdown.

### What is NOT included

- Real-world event → SAGE ingest queue latency (source polling intervals: AIS ~30 s, news ~5 min, sanctions ~1 h, price ~60 s)
- Bedrock LLM latency for Nova Micro entity extraction (embedded within each System-1 stage)

### Reproducibility

```bash
# Independent verification from Redis
redis-cli -p 6380 LRANGE sage:agent_trace:recent 0 199 | \
  python3 -c "
import sys, json, statistics
evs = [json.loads(l) for l in sys.stdin if l.strip()]
evs.sort(key=lambda e: e.get('ts',''))
s1 = [e for e in evs if e.get('system')=='1' and e.get('status')=='done']
s4 = [e for e in evs if e.get('system')=='4' and e.get('status')=='done']
if s1 and s4:
    from datetime import datetime
    t0 = datetime.fromisoformat(s1[0]['ts']).timestamp()
    tf = datetime.fromisoformat(s4[-1]['ts']).timestamp()
    print(f'Signal→Reserve: {tf-t0:.1f}s')
"
```
