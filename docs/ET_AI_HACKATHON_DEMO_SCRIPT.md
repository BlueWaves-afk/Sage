# SAGE — ET AI Hackathon 2.0 Demo Video Script

## Honest Verdict

**Current evidence-backed score: 85/100. Likely rank: top 3–5, with a credible podium path.**

SAGE is unusually complete for a hackathon prototype: it implements all five suggested solution areas,
connects them in one autonomous workflow, exposes assumptions and provenance, and runs as a deployed
multi-tenant product. It is not honestly a guaranteed winner. The principal weaknesses are a 59.3%
live risk-crossing precision ledger, no realized scenario-impact outcomes yet, proxy-based historical AIS
calibration data, a single-node EC2 deployment, and a latest idle-state procurement result that can be
empty. A disciplined golden-path recording can present the strongest reproducible evidence without
concealing those limitations.

| Criterion | Weight | Score | Evidence-backed assessment |
|---|---:|---:|---|
| Innovation | 25 | **23** | Synthesis-first bitemporal knowledge graph, four-system agent architecture, graph-grounded copilot, and mitigation re-simulation form a differentiated closed loop. |
| Business Impact | 25 | **20** | The system converts a disruption into ranked procurement and reserve actions in about 74 seconds. Avoided cost is modelled rather than realized, and no user pilot is documented. |
| Technical Excellence | 20 | **17** | GBM fusion with Platt scaling and LOCO-5 validation, ARIO/Monte Carlo/Leontief modelling, TOPSIS/routing, Bellman reserve optimization, explicit assumptions, and provenance are real implementations. Live precision and outcome validation remain immature. |
| Scalability | 15 | **12** | India and Japan run through isolated context bundles and graph namespaces; sensory workers are stateless and HPA-ready. Production is still one EC2 host and Japan's graph is much thinner. |
| User Experience | 15 | **13** | Polished command center, digital twin, evidence drawers, scenario lab, response planner, cited copilot, cold-start recovery, and clear offline states. Voice is mock in the deployed environment. |
| **Total** | **100** | **85** | **Top 3–5 quality today; roughly 88–91 perceived points if the recording executes cleanly.** |

## Why This Sequence Wins

The evaluation focus asks for five things in one sentence. The recording answers them in the same order:

1. **Detection lead time and accuracy** — begin the held-out Hormuz replay and show LOCO-5 AUC.
2. **Procurement quality and executability** — show ranked suppliers with route, grade, landed cost,
   lead time, compatibility, and rationale.
3. **Scenario fidelity** — show explicit sourced assumptions, Monte Carlo ranges, cascade, and sensitivity.
4. **Geospatial evidence depth** — show the live knowledge graph, shipping lanes, corridor risk, and source
   evidence drawer.
5. **End-to-end response time** — return to the pipeline timer after it completes at about 74 seconds.

The key production choice is to start **Demo Mode at 00:18**. Its real autonomous pipeline runs while the
video demonstrates calibration and evidence. This avoids a dead 74-second wait and proves the workflow
without a fabricated edit.

## Four-Minute Master Script

### 00:00–00:18 — The Decision Gap

**Screen:** Landing page, then click **Launch Command Center**.

**Voice-over:**

> India imports roughly 88 percent of its crude, and a major share transits one chokepoint: the Strait of
> Hormuz. Existing tools describe a crisis after it happens. SAGE detects the precursor signals, simulates
> the economic cascade, and produces executable procurement and reserve actions before the disruption
> becomes a shortage.

**Rubric hit:** Business impact; problem relevance; anticipatory rather than reactive response.

### 00:18–00:32 — Start the End-to-End Clock

**Screen:** In **Command Center**, click **⚡ Demo Mode**. Keep the pipeline ribbon and Agent Trace Feed
visible long enough to show AIS, news, price, and sanctions/GDELT activity beginning.

**Voice-over:**

> This is a replay of the held-out 2026 Hormuz pre-crisis window. I am starting it now so the on-screen
> timer measures the complete response. Four sensory agents ingest vessel anomalies, geopolitical news,
> sanctions intelligence, and commodity price regime shifts. These are fused into one calibrated corridor
> risk score; crossing the action threshold triggers the response autonomously.

**Do not say:** “live 2026 crisis.” It is an explicitly labelled replay using demo inputs.

### 00:32–00:58 — Prove Accuracy, Not Just AI

**Screen:** Open **Simulation Lab → Learning**. Frame **Mean LOCO AUC**, the five crisis bars, and the
reliability curve. Do not dwell on full-data AUC.

**Voice-over:**

> This is not an LLM guessing a risk level. System One uses a gradient-boosted fusion model with Platt
> calibration. Leave-one-crisis-out validation across five historical disruptions produces a mean AUC of
> 0.8409, including 0.8333 when the 2026 Hormuz episode is held out. The live prediction ledger remains
> visible separately, so false positives are inspectable rather than hidden.

**Rubric hit:** Detection accuracy; technical excellence; transparent evaluation.

### 00:58–01:22 — Prove Geospatial Evidence Depth

**Screen:** Open **Global Intelligence**. Keep **Routes**, flows, and graph nodes enabled. Click **Strait of
Hormuz**, then open one source/evidence item or wiki assessment.

**Voice-over:**

> Every score is grounded in a bitemporal knowledge graph, not a flat dashboard. The digital twin connects
> chokepoints, suppliers, routes, refineries, strategic reserves, and evidence. Clicking Hormuz reveals the
> underlying graph facts and synthesized assessment. Raw signals are never written directly into semantic
> memory; SAGE reconciles sources first, preserving provenance and reducing contradictory noise.

**Rubric hit:** Geospatial evidence depth; knowledge graph; RAG; innovation.

### 01:22–01:42 — Show the Measured Autonomous Handoff

**Screen:** Return to **Command Center**. Frame the completed pipeline ribbon, response-time strip,
Hormuz action state, and recommendation cards. If still running, hold on the Agent Trace Feed until it
finishes; do not cut out the timer.

**Voice-over:**

> The risk crossed into action without an analyst pressing “run scenario.” The same production trigger has
> now completed sensing, synthesis, scenario modelling, procurement, and reserve optimization. On this EC2
> deployment, the rolling measured response is about 74 seconds from signal to recommendation—turning a
> multi-hour coordination process into a traceable machine workflow.

**Rubric hit:** Demonstrated end-to-end response time.

### 01:42–02:14 — Make Scenario Fidelity Explicit

**Screen:** Open **Simulation Lab → Impact**, then **Cascade** and **Sensitivity**. On Sensitivity, click
**Run Sensitivity Analysis** only if it has been pre-tested within the recording window. Show the sourced
assumptions and tornado chart; keep displayed values readable.

**Voice-over:**

> System Two models the physical and economic cascade using an adaptive regional input-output model,
> Monte Carlo uncertainty, a Leontief sector cascade, and agent-based refinery behaviour. Crucially, every
> consequential assumption is explicit, sourced, unit-labelled, and testable—from closure severity and
> rerouting delay to refinery utilization and elasticity. The tornado chart perturbs major assumptions by
> plus or minus 20 percent, showing judges exactly which conclusions are robust and which are sensitive.

**Do not claim:** proven scenario forecast accuracy. No realized scenario outcomes are logged yet.

### 02:14–02:48 — Prove Procurement Is Executable

**Screen:** Open **Response Planner**. Select the top-ranked supplier and frame its route, grade, landed
cost, lead time, compatibility score, TOPSIS score, rationale, and the route geography if visible.

**Voice-over:**

> System Three does not return “buy more oil.” It ranks executable alternatives using landed cost, delivery
> time, corridor risk, supplier reliability, available volume, refinery-grade compatibility, tanker and port
> constraints. Each recommendation names the supplier, crude grade, route, price, lead time, and reason for
> its rank. TOPSIS makes the trade-offs inspectable, while the routing solver checks the physical path.

**Rubric hit:** Quality and executability of procurement alternatives.

### 02:48–03:10 — Close the Policy Loop

**Screen:** Scroll to **Strategic Reserve Drawdown Schedule**. Show the daily bars, three-day buffer badge,
constraint status, and policy memo.

**Voice-over:**

> System Four then co-optimizes strategic reserves against the residual supply gap. A Bellman dynamic
> program chooses daily hold or draw actions, while a constrained policy protects the minimum buffer and a
> real-options layer values flexibility under uncertainty. The result is a day-by-day schedule and a cited
> policy memo—not another alert for a policymaker to interpret.

### 03:10–03:28 — Demonstrate Mitigation Value

**Screen:** Return to **Simulation Lab → Impact** and click **Run with SAGE Mitigations**. Show the
before/after base gap, mitigated gap, percentage reduction, and procurement/SPR offsets.

**Voice-over:**

> Most systems stop at a recommendation. SAGE feeds its chosen procurement reallocation and reserve draw
> back into the simulator. This re-run quantifies the residual gap and shows the contribution of each
> mitigation, closing the loop from intelligence to action to measured policy value.

**Rubric hit:** Innovation; business impact; full end-to-end response.

### 03:28–03:46 — Show Grounded Bedrock Copilot

**Screen:** Open **Strategic Copilot** and click the suggestion **Why is the Strait of Hormuz critical for
India?** While Bedrock responds, keep the graph-search indicator visible. Show the route badge, latency,
inline citations, and click one source to open its wiki drawer.

**Voice-over:**

> For decision-makers, the same graph is available through a Bedrock-powered copilot. It routes multi-hop
> questions through graph PPR and simpler retrieval through vector and BM25 search. Answers carry numbered,
> clickable graph and wiki citations. If the knowledge base is unavailable, the interface says offline—it
> never invents a fallback answer.

### 03:46–04:00 — Scalability and Final Claim

**Screen:** Use the region switcher from **India** to **Japan**, briefly showing the Japan graph, then end
on the architecture diagram or SAGE logo with the five systems highlighted.

**Voice-over:**

> The engine is country-agnostic: switching from India to Japan loads an isolated context bundle, graph,
> provenance set, and policy configuration without changing agent code. SAGE is not a crisis dashboard. It
> is a persistent national energy resilience system—detect, explain, simulate, procure, reserve, and learn,
> in one evidence-backed loop.

## Recording Preflight

Run this checklist immediately before recording:

1. Confirm `http://44.213.136.64/health` returns `status: ok` and `kb_ready: true`.
2. Select **India** and hard-refresh `/command`.
3. Verify the graph renders and the top bar says **LIVE**, not **OFFLINE**.
4. Open **Learning** and confirm **Mean LOCO AUC 0.8409** renders.
5. Ask the Copilot question once to warm Bedrock, then refresh the page so the recorded thread starts empty.
6. Run Demo Mode once in a rehearsal and verify **Response Planner** contains ranked alternatives afterward.
7. Refresh, wait at least 90 seconds for the demo button state to reset, then begin the real take.
8. Start Demo Mode at 00:18 and do not run another scenario while its autonomous pipeline is active.
9. Read the response-time value shown in the take. Say “about 74 seconds” only if it remains near that value.
10. Keep the browser at 100% zoom, hide bookmarks, silence notifications, and record at 1080p or higher.

## Claims Safe to Say

- All five suggested solution areas are implemented and connected end to end.
- Four sensory streams cover AIS, news/GDELT, sanctions, and commodity prices.
- The deployed fusion model reports mean LOCO-5 AUC **0.8409**.
- The held-out 2026 Hormuz fold reports AUC **0.8333**.
- The historical replay demonstrates **5 days 7 hours** of warning relative to the documented disruption
  boundary; describe this as replay lead time, not live foresight.
- Scenario assumptions are explicit, sourced, unit-labelled, and testable.
- Procurement evaluates landed cost, lead time, risk, reliability, volume, route, and grade compatibility.
- Reserve optimization emits a day-by-day constrained drawdown policy.
- The deployed workflow currently measures roughly **74 seconds** signal-to-recommendation.
- India and Japan context bundles are live with isolated data and graph namespaces.
- Copilot answers use AWS Bedrock and expose graph/wiki citations and retrieval route.

## Claims Not Safe to Say

- **Do not say “20–25 seconds.”** The live rolling median is approximately 73.7 seconds.
- **Do not say “36 alternatives” or hard-code a supplier count.** The latest idle run can be empty; use the
  count visibly produced by Demo Mode.
- **Do not say “72 nodes and 97 edges.”** The live graph changes; read the on-screen count if needed.
- **Do not claim actual savings.** The `$1.25–1.46B` realistic-execution estimate is modelled decision value
  under documented scenario assumptions, not realized savings.
- **Do not claim scenario forecast accuracy.** There are currently no realized outcomes for scenario MAPE.
- **Do not call historical AIS calibration a complete live archive.** It uses documented event-timeline
  proxies alongside sampled/interpolated GDELT features.
- **Do not claim Kubernetes is running.** The repository contains an HPA-ready deployment design; production
  is Docker Compose on a single EC2 host.
- **Do not demo voice as production speech recognition.** The deployed health endpoint reports mock voice mode.
- **Do not call the replay live data.** It is a deterministic, labelled crisis replay through the real pipeline.

## Judge Q&A

**How is this more than a dashboard?**  
The action-band crossing invokes scenario, procurement, and reserve agents automatically; recommendations
are then fed back into the scenario to quantify residual risk.

**Where does the LLM sit?**  
AWS Bedrock Nova models handle extraction, synthesis, rationales, policy prose, and copilot answers. Risk
fusion, ARIO simulation, TOPSIS ranking, routing, and Bellman optimization remain explicit computational
models rather than LLM arithmetic.

**How do you prevent hallucinations?**  
Raw signals pass through deterministic triage and synthesis before graph ingestion. Copilot answers are
grounded in graph/wiki retrieval, expose citations, and return an explicit offline state when retrieval fails.

**How was accuracy tested?**  
The fusion model uses leave-one-crisis-out validation over five disruptions. Mean AUC is 0.8409; the held-out
2026 Hormuz fold is 0.8333. The live ledger separately tracks confirmed and expired threshold crossings.

**What is your biggest current limitation?**  
Scenario outcome validation needs real elapsed outcomes and institutional users. The UI already supports
analyst logging, bounded corridor calibration, and transparent MAPE once those observations accumulate.

**Can it scale beyond India?**  
Country facts, sources, narratives, policy thresholds, and provenance are packaged as context bundles.
India and Japan already run through the same code with isolated graph and Redis namespaces.

## Evidence Map

The audit covered all **408 tracked files** by repository inventory, including **125 Markdown documents**,
**97 Python files**, **42 TSX files**, and **61 test functions**. The strongest implementation anchors are:

- Autonomous demo and production-equivalent action trigger: `visualizer_agent/api_gateway/main.py`
- End-to-end LangGraph response workflow: `orchestration/graph.py`
- Signal fusion and prediction feedback: `knowledge/fusion.py`, `knowledge/feedback.py`
- Synthesis-first graph write path: `knowledge/api/write.py`, `knowledge/synthesis.py`
- ARIO, Monte Carlo, Leontief, and ABM scenario models: `scenario_agent/`
- TOPSIS, grade compatibility, and route optimization: `alt_procurement_agent/`
- Bellman/CMDP/real-options reserve planning: `reserve_optim_agent/`
- Digital twin and evidence UX: `visualizer_agent/frontend/src/`
- Context-bundle portability: `knowledge/context/`, `data/*.context/`
- Calibration evidence: `docs/CALIBRATION_REPORT.md`
- Explicit assumptions and sensitivity: `docs/ASSUMPTIONS.md`
- Business-impact caveats and timing: `docs/IMPACT.md`
- Deployment and scaling boundaries: `docs/DEPLOY_EC2.md`, `docs/SCALABILITY.md`

## Final Positioning

The most credible winning message is not “we predicted the future perfectly.” It is:

> **SAGE turns uncertain, conflicting early-warning signals into a sourced and testable national energy
> decision—then proves the value of that decision by simulating the mitigated outcome.**

That claim is differentiated, aligned word-for-word with the evaluation focus, and implemented in the
deployed product.
