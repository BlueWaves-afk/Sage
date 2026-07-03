import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import KnowledgeGraphMap from "../components/KnowledgeGraphMap";
import WikiDrawer from "../components/WikiDrawer";
import PipelineBar from "../components/PipelineBar";
import AmbientBackground from "../components/AmbientBackground";
import AnimatedNumber from "../components/AnimatedNumber";
import { Panel, Badge, Meter, OfflineHint } from "../components/ui/ui";
import type { GraphNode } from "../api/types";
import { IconRss, IconAnchor, IconChart, IconAlert, IconBot } from "../components/icons";
import { api } from "../api/hooks";
import { useApi } from "../api/hooks";
import { mockIntel } from "../api/mock";
import type { IntelItem } from "../api/types";
import "./command.css";

const INTEL_ICON: Record<IntelItem["source"], typeof IconRss> = {
  REUTERS: IconRss,
  "AIS ALERTS": IconAnchor,
  "PRICE MVT": IconChart,
  "SAGE CORE": IconAlert,
  OFAC: IconAlert,
};
const TONE_CLASS: Record<IntelItem["tone"], string> = {
  info: "c-cyan",
  warn: "c-amber",
  good: "c-green",
  crit: "c-red",
};

type Kpi = {
  label: string;
  value?: string;
  num?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  tone: string;
  up?: boolean;
  warn?: boolean;
  sub?: string;
};


export default function CommandCenter() {
  const nav = useNavigate();
  const { data: graph, live: graphLive } = useApi(api.graph);
  const { data: dash, live } = useApi(api.dashboard);
  const [selected, setSelected] = useState<GraphNode | null>(null);

  // AI Situation Brief narrative: pulled live from the highest-risk entity's
  // reconciled wiki page (its "Current Assessment" paragraph) — not hardcoded.
  const [brief, setBrief] = useState<string | null>(null);
  useEffect(() => {
    const entity = dash?.top_risk_entity;
    if (!entity) return;
    api.wiki(entity).then((env) => {
      const m = env.data.content.match(/##\s*Current Assessment\s*\n([\s\S]*?)(?=\n##|\n---|$)/i);
      setBrief(m ? m[1].trim() : null);
    });
  }, [dash?.top_risk_entity]);

  const threatTone =
    dash?.threat_level === "CRITICAL" ? "c-red" :
    dash?.threat_level === "HIGH" ? "c-coral" :
    dash?.threat_level === "MEDIUM" ? "c-amber" : "c-green";

  const kpis: Kpi[] = useMemo(() => [
    { label: "Threat Level", value: dash?.threat_level ?? "—", tone: threatTone },
    { label: "Brent Crude (EIA ref)", num: dash?.brent_usd_bbl ?? undefined, prefix: "$", decimals: 2, tone: "", up: true, value: dash?.brent_usd_bbl == null ? "—" : undefined },
    { label: "SPR Coverage", num: dash?.spr_coverage_pct ?? undefined, suffix: "%", decimals: 1, tone: "", value: dash?.spr_coverage_pct == null ? "—" : undefined },
    { label: "Active Alerts", num: dash?.active_alerts ?? 0, tone: (dash?.active_alerts ?? 0) > 0 ? "c-amber" : "c-green", warn: (dash?.active_alerts ?? 0) > 0 },
    { label: "Tracked Entities", num: dash?.monitoring_entities ?? 0, tone: "", sub: "KB NODES" },
    { label: "Mode", value: live ? "LIVE" : "OFFLINE", tone: live ? "c-cyan" : "c-muted" },
  ], [dash, live, threatTone]);

  const bottlenecks = dash?.bottlenecks?.slice(0, 3) ?? [];

  return (
    <div className="cc">
      <AmbientBackground />
      {/* KPI row */}
      <div className="cc-kpis stagger">
        {kpis.map((k) => (
          <div key={k.label} className="cc-kpi card lift">
            <span className="label-sm">{k.label}</span>
            <div className={`cc-kpi-value ${k.tone}`}>
              {k.num != null ? (
                <AnimatedNumber value={k.num} prefix={k.prefix} suffix={k.suffix} decimals={k.decimals} />
              ) : (
                k.value
              )}
              {k.up && <span className="c-green cc-kpi-arrow">↗</span>}
              {k.warn && <span className="c-amber cc-kpi-arrow">⚠</span>}
              {k.sub && <span className="cc-kpi-sub">{k.sub}</span>}
            </div>
          </div>
        ))}
      </div>

      <div className="cc-grid">
        {/* Map + AI brief */}
        <div className="cc-main">
          <div className="cc-map-row">
            <div className="cc-map card">
              <KnowledgeGraphMap
                graph={graph ?? { nodes: [], edges: [] }}
                selectedId={selected?.id ?? null}
                onNodeClick={setSelected}
                initialView={{ longitude: 52, latitude: 24, zoom: 3.3 }}
              />
              <div className="cc-map-badge glass mono">
                <span className={`cc-map-badge-dot ${graphLive ? "on" : ""}`} />
                {graph?.nodes.length ?? 0} nodes · {graph?.edges.length ?? 0} edges ·{" "}
                {graphLive ? "LIVE KB" : "DEMO"}
              </div>
              <div className="cc-map-overlay">
                <div className="cc-bottlenecks">
                  <div className="label-sm">Maritime Bottlenecks</div>
                  {bottlenecks.map((b) => (
                    <Row
                      key={b.name}
                      name={b.name.replace("Strait of ", "").replace("Bab-el-Mandeb", "Red Sea")}
                      status={b.status}
                      tone={b.status === "BLOCKED" ? "red" : b.status === "CONTESTED" ? "amber" : "green"}
                    />
                  ))}
                </div>
              </div>
            </div>

            <Panel
              className="cc-brief"
              title={
                <span className="cc-brief-title">
                  <IconBot width={16} height={16} className="c-cyan" /> AI Situation Brief
                </span>
              }
              right={<OfflineHint live={live} />}
            >
              <div className="label-sm">
                Narrative Summary{dash?.top_risk_entity ? ` · ${dash.top_risk_entity}` : ""}
              </div>
              <p className="cc-narrative">
                {brief
                  ? `"${brief}"`
                  : dash?.top_risk_entity
                    ? "Loading reconciled assessment from the knowledge base…"
                    : "No elevated entity — knowledge base nominal."}
              </p>
              <div className="label-sm cc-brief-sec">Threat Assessment</div>
              <div className="cc-threat">
                <span>
                  Supply Disruption{" "}
                  <b className={threatTone}>{dash?.threat_level ?? "—"}</b>
                </span>
                <Meter
                  value={
                    dash?.threat_level === "CRITICAL" ? 0.95 :
                    dash?.threat_level === "HIGH" ? 0.78 :
                    dash?.threat_level === "MEDIUM" ? 0.55 : 0.2
                  }
                  tone={dash?.threat_level === "MEDIUM" ? "amber" : dash?.threat_level === "LOW" ? "green" : "red"}
                />
              </div>
              <div className="label-sm cc-brief-sec">Supporting Evidence</div>
              <div className="cc-evidence">
                <Badge tone="muted" outline>
                  Reuters
                </Badge>
                <Badge tone="muted" outline>
                  AIS Live
                </Badge>
                <Badge tone="muted" outline>
                  OFAC
                </Badge>
              </div>
            </Panel>
          </div>

          {/* Recommendation cards */}
          <div className="cc-recs stagger">
            <RecCard
              title="Alternative Procurement"
              priority="Priority 1"
              tone="cyan"
              body="Re-route 14% of North Sea output to domestic refineries to offset Red Sea delays."
              confidence="88%"
              impact="HIGH"
              impactTone="c-green"
              onClick={() => nav("/response")}
            />
            <RecCard
              title="Strategic Reserve"
              priority="Priority 2"
              tone="muted"
              body="Prepare for 5% SPR draw-down if crude spikes above $92/bbl for > 72 hours."
              confidence="92%"
              impact="MED"
              impactTone="c-amber"
              onClick={() => nav("/response")}
            />
            <RecCard
              title="Supply Chain Risk"
              priority="Priority 1"
              tone="red"
              body="Immediate audit of downstream logistics partners for potential fuel hoarding."
              confidence="74%"
              impact="CRITICAL"
              impactTone="c-red"
              onClick={() => nav("/intelligence")}
            />
          </div>

          <PipelineBar />
        </div>

        {/* Live intelligence rail */}
        <div className="cc-rail">
          <Panel
            className="cc-intel"
            title={
              <span className="cc-intel-title">
                Live Intelligence <span className="cc-live-dot" />
              </span>
            }
            right={<OfflineHint live={live} />}
          >
            <div className="cc-feed">
              {mockIntel.map((item) => {
                const Icon = INTEL_ICON[item.source];
                return (
                  <div key={item.id} className="cc-feed-item">
                    <span className={`cc-feed-bullet ${TONE_CLASS[item.tone]}`} />
                    <div className="cc-feed-body">
                      <div className="cc-feed-head">
                        <span className={`cc-feed-source ${TONE_CLASS[item.tone]}`}>
                          <Icon width={12} height={12} /> {item.source}
                        </span>
                        <span className="cc-feed-time mono">{item.time}</span>
                      </div>
                      <p className="cc-feed-text">{item.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel
            className="cc-copilot"
            title={
              <span className="cc-intel-title">
                <IconBot width={15} height={15} className="c-cyan" /> Strategic Copilot
              </span>
            }
          >
            <p className="cc-copilot-prompt">"How can I assist your strategic assessment today?"</p>
            <div className="cc-copilot-chips">
              <button className="chip" onClick={() => nav("/copilot")}>
                Explain Risk
              </button>
              <button className="chip" onClick={() => nav("/simulation")}>
                Run Simulation
              </button>
              <button className="chip" onClick={() => nav("/copilot")}>
                Draft Brief
              </button>
            </div>
            <button className="cc-copilot-input" onClick={() => nav("/copilot")}>
              Inquire command center…
            </button>
          </Panel>
        </div>
      </div>

      <WikiDrawer node={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function Row({ name, status, tone }: { name: string; status: string; tone: "green" | "amber" | "red" }) {
  return (
    <div className="cc-bottleneck-row">
      <span className="cc-bottleneck-name">{name}</span>
      <Badge tone={tone}>{status}</Badge>
    </div>
  );
}

function RecCard({
  title,
  priority,
  tone,
  body,
  confidence,
  impact,
  impactTone,
  onClick,
}: {
  title: string;
  priority: string;
  tone: "cyan" | "muted" | "red";
  body: string;
  confidence: string;
  impact: string;
  impactTone: string;
  onClick: () => void;
}) {
  return (
    <button className={`cc-rec card lift cc-rec-${tone}`} onClick={onClick}>
      <div className="cc-rec-head">
        <span className="cc-rec-title">{title}</span>
        <Badge tone={tone === "red" ? "red" : tone === "cyan" ? "cyan" : "muted"}>{priority}</Badge>
      </div>
      <p className="cc-rec-body">{body}</p>
      <div className="cc-rec-foot">
        <div>
          <div className="label-sm">Confidence</div>
          <div className="c-cyan cc-rec-metric">{confidence}</div>
        </div>
        <div className="cc-rec-foot-right">
          <div className="label-sm">Impact</div>
          <div className={`cc-rec-metric ${impactTone}`}>{impact}</div>
        </div>
      </div>
    </button>
  );
}
