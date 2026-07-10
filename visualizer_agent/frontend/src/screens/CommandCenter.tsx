import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import KnowledgeGraphMap from "../components/KnowledgeGraphMap";
import WikiDrawer from "../components/WikiDrawer";
import { RichText } from "../components/RichText";
import PipelineBar from "../components/PipelineBar";
import AmbientBackground from "../components/AmbientBackground";
import AnimatedNumber from "../components/AnimatedNumber";
import { Panel, Badge, Meter, OfflineHint, Skel, Kb } from "../components/ui/ui";
import type { GraphNode } from "../api/types";
import { IconRss, IconAnchor, IconChart, IconAlert, IconBot } from "../components/icons";
import { api } from "../api/hooks";
import { useApi } from "../api/hooks";
import { useVoice, voiceStore } from "../voice/useVoiceStore";
import type { KpiKey } from "../voice/types";
import "./command.css";

type Kpi = {
  // Key mirrors the voice action taxonomy — a `flash_kpi` action from voice
  // pulses the tile whose `kpiKey` matches. Anything the user might ask about
  // by voice must live under one of the KpiKey values.
  kpiKey?: KpiKey;
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
  const { data: dash, live, loading } = useApi(api.dashboard);
  const { data: proc, live: procLive } = useApi(api.procurement);
  const { data: sched, live: schedLive } = useApi(api.sprSchedule);
  const { data: scen, live: scenLive } = useApi(api.scenario);
  const { data: intel } = useApi(api.intelligence);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [briefLoading, setBriefLoading] = useState(true);
  // Supporting-evidence drill-down: the real source signals behind a risk state.
  const [evSource, setEvSource] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<import("../api/types").IntelSignal[] | null>(null);

  const showEvidence = async (src: string) => {
    const entity = dash?.top_risk_entity;
    if (!entity) return;
    setEvSource(src);
    setEvidence(null);
    const env = await api.evidence(entity, 20);
    const items = (env.data || []).filter(
      (s) => s.source.toLowerCase().startsWith(src.toLowerCase().slice(0, 4)),
    );
    setEvidence(items.length ? items : env.data || []);
  };

  // Opens the wiki drawer for an entity referenced via a [[wikilink]] in narrative
  // text (brief, procurement rationale, SPR memo) — same drawer the map uses.
  const openWikilink = (entity: string) =>
    setSelected({ id: entity, name: entity, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 });

  // AI Situation Brief narrative: pulled live from the highest-risk entity's
  // reconciled wiki page (its "Current Assessment" paragraph) — not hardcoded.
  const [brief, setBrief] = useState<string | null>(null);
  const [briefLive, setBriefLive] = useState(false);
  useEffect(() => {
    const entity = dash?.top_risk_entity;
    if (!entity) {
      setBriefLoading(false);
      return;
    }
    setBriefLoading(true);
    api.wiki(entity).then((env) => {
      const m = env.data?.content.match(/##\s*Current Assessment\s*\n([\s\S]*?)(?=\n##|\n---|$)/i);
      setBrief(m ? m[1].trim() : null);
      setBriefLive(env.live && !!m);
      setBriefLoading(false);
    });
  }, [dash?.top_risk_entity]);

  const threatTone =
    dash?.threat_level === "CRITICAL" ? "c-red" :
    dash?.threat_level === "HIGH" ? "c-coral" :
    dash?.threat_level === "MEDIUM" ? "c-amber" : "c-green";

  const kpis: Kpi[] = useMemo(() => [
    { kpiKey: "threat_level", label: "Threat Level", value: dash?.threat_level ?? "—", tone: threatTone },
    { kpiKey: "brent_usd_bbl", label: "Brent Crude", num: dash?.brent_usd_bbl ?? undefined, prefix: "$", decimals: 2, tone: "", up: true, value: dash?.brent_usd_bbl == null ? "—" : undefined, sub: "EIA REF" },
    { kpiKey: "spr_coverage_pct", label: "SPR Coverage", num: dash?.spr_coverage_pct ?? undefined, suffix: "%", decimals: 1, tone: "", value: dash?.spr_coverage_pct == null ? "—" : undefined },
    { kpiKey: "active_alerts", label: "Active Alerts", num: dash?.active_alerts ?? 0, tone: (dash?.active_alerts ?? 0) > 0 ? "c-amber" : "c-green", warn: (dash?.active_alerts ?? 0) > 0 },
    { kpiKey: "monitoring_entities", label: "Tracked Entities", num: dash?.monitoring_entities ?? 0, tone: "", sub: "KB NODES" },
    { label: "Mode", value: live ? "LIVE" : "OFFLINE", tone: live ? "c-cyan" : "c-muted" },
  ], [dash, live, threatTone]);

  // Voice: which KPI is currently flashing (voice `flash_kpi` action) + which
  // entity the voice bridge asked to open in the drawer.
  const flashedKpi = useVoice((s) => s.flashedKpi);
  const voiceDrawer = useVoice((s) => s.drawerEntity);
  useEffect(() => {
    if (!voiceDrawer) return;
    setSelected({ id: voiceDrawer, name: voiceDrawer, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 });
    // Consume it so the same entity can be re-requested later.
    voiceStore.openDrawer(null);
  }, [voiceDrawer]);

  const bottlenecks = dash?.bottlenecks?.slice(0, 3) ?? [];

  // Recommendation cards read from System 3/4/2 outputs. These are only present
  // once a scenario has run; until then the endpoints 404 (live=false) and the
  // card renders a skeleton rather than a fabricated recommendation.
  const topOption = proc?.ranked?.[0] ?? null;
  const recs = [
    {
      title: "Alternative Procurement",
      priority: "Priority 1",
      tone: "cyan" as const,
      live: procLive,
      body: topOption
        ? `${topOption.supplier} (${topOption.grade}) via ${topOption.route_via} — TOPSIS ${Number(topOption.topsis_score).toFixed(2)}.`
        : "",
      confidence: topOption ? `${Math.round(Number(topOption.topsis_score) * 100)}%` : "",
      impact: "HIGH",
      impactTone: "c-green",
    },
    {
      title: "Strategic Reserve",
      priority: "Priority 2",
      tone: "muted" as const,
      live: schedLive,
      body: sched?.policy_memo ?? "",
      confidence: sched ? `${Math.round((sched.prob_above_buffer ?? 0) * 100)}%` : "",
      impact: sched?.constraint_satisfied === false ? "AT RISK" : "MED",
      impactTone: sched?.constraint_satisfied === false ? "c-red" : "c-amber",
    },
    {
      title: "Supply Chain Risk",
      priority: "Priority 1",
      tone: "red" as const,
      live: scenLive,
      body: scen
        ? `${scen.gap_mbpd.toFixed(2)} mbpd supply gap projected at ${scen.trigger_entity}; price impact up to $${scen.price_impact_high.toFixed(0)}/bbl; SPR cover ${scen.spr_depletion_days.toFixed(0)} days.`
        : "",
      confidence: scen ? `${Math.round((scen.confidence ?? 0) * 100)}%` : "",
      impact: "CRITICAL",
      impactTone: "c-red",
    },
  ];

  return (
    <div className="cc">
      <AmbientBackground />
      {/* KPI row */}
      <div className="cc-kpis stagger">
        {kpis.map((k) => (
          <div
            key={k.label}
            className={`cc-kpi card lift${k.kpiKey && flashedKpi === k.kpiKey ? " cc-kpi-flash" : ""}`}
          >
            <span className="label-sm">{k.label}</span>
            <div className={`cc-kpi-value ${k.tone}`}>
              <Kb live={k.label === "Mode" ? true : live} loading={loading} skel={<Skel w={90} h={24} />}>
                {k.num != null ? (
                  <AnimatedNumber value={k.num} prefix={k.prefix} suffix={k.suffix} decimals={k.decimals} />
                ) : (
                  k.value
                )}
                {k.up && <span className="c-green cc-kpi-arrow">↗</span>}
                {k.warn && <span className="c-amber cc-kpi-arrow">⚠</span>}
                {k.sub && <span className="cc-kpi-sub">{k.sub}</span>}
              </Kb>
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
                  {!live || loading
                    ? [0, 1, 2].map((i) => (
                        <div key={i} className="cc-bottleneck-row">
                          <Skel w={90} h={13} />
                          <Skel w={60} h={16} />
                        </div>
                      ))
                    : bottlenecks.map((b) => (
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
                Narrative Summary{briefLive && dash?.top_risk_entity ? ` · ${dash.top_risk_entity}` : ""}
              </div>
              {briefLoading ? (
                <div className="cc-narrative">
                  <Skel w="100%" h={13} /> <Skel w="96%" h={13} /> <Skel w="70%" h={13} />
                </div>
              ) : briefLive && brief ? (
                <p className="cc-narrative">
                  <RichText text={brief} onWikilink={openWikilink} />
                </p>
              ) : (
                <p className="cc-status-line mono">[STATUS: AWAITING SYNTHESIS]</p>
              )}
              <div className="label-sm cc-brief-sec">Threat Assessment</div>
              <div className="cc-threat">
                <span>
                  Supply Disruption{" "}
                  <Kb live={live} loading={loading} skel={<Skel w={60} h={16} />}>
                    <b className={threatTone}>{dash?.threat_level ?? "—"}</b>
                  </Kb>
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
              <div className="label-sm cc-brief-sec">
                Supporting Evidence
                {dash?.top_risk_entity && (
                  <span className="cc-ev-for mono"> · {dash.top_risk_entity}</span>
                )}
              </div>
              <div className="cc-evidence">
                {!live || loading ? (
                  <>
                    <Skel w={70} h={22} /> <Skel w={70} h={22} /> <Skel w={60} h={22} />
                  </>
                ) : (
                  ["News", "AIS", "Sanctions", "Price"].map((s) => (
                    <button
                      key={s}
                      className={`cc-ev-btn${evSource === s ? " on" : ""}`}
                      onClick={() => showEvidence(s)}
                    >
                      {s}
                    </button>
                  ))
                )}
              </div>
              {evSource && (
                <div className="cc-ev-list">
                  {evidence === null ? (
                    <div className="offline-hint mono">loading {evSource} evidence…</div>
                  ) : evidence.length === 0 ? (
                    <div className="offline-hint mono">
                      No {evSource} signals recorded for this entity yet.
                    </div>
                  ) : (
                    evidence.map((s) => (
                      <div key={s.id} className="cc-ev-item">
                        <span className={`cc-feed-src cc-src-${s.source}`}>{s.source.toUpperCase()}</span>
                        <div className="cc-feed-body">
                          <div className="cc-feed-text">{s.headline}</div>
                          <div className="cc-feed-time mono">
                            {s.recorded_at ? new Date(s.recorded_at).toLocaleString() : ""}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </Panel>
          </div>

          {/* Recommendation cards — from System 2/3/4 outputs (skeleton until run) */}
          <div className="cc-recs stagger">
            {recs.map((r) => (
              <RecCard
                key={r.title}
                title={r.title}
                priority={r.priority}
                tone={r.tone}
                live={r.live}
                body={r.body}
                confidence={r.confidence}
                impact={r.impact}
                impactTone={r.impactTone}
                onClick={() => nav("/response")}
                onWikilink={openWikilink}
              />
            ))}
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
            right={
              <span className="offline-hint mono">
                {intel && intel.length ? `${intel.length} live signals` : "awaiting System 1"}
              </span>
            }
          >
            {/* Real signals ingested by System 1 (news / GDELT / AIS / price /
                sanctions), newest first. Skeleton only while the feed is empty. */}
            <div className="cc-feed">
              {intel && intel.length > 0
                ? intel.map((s) => (
                    <div key={s.id} className="cc-feed-item">
                      <span className={`cc-feed-src cc-src-${s.source}`}>{s.source.toUpperCase()}</span>
                      <div className="cc-feed-body">
                        <div className="cc-feed-text">{s.headline}</div>
                        <div className="cc-feed-time mono">
                          {s.recorded_at ? new Date(s.recorded_at).toLocaleString() : ""}
                        </div>
                      </div>
                    </div>
                  ))
                : [0, 1, 2, 3].map((i) => (
                    <div key={i} className="cc-feed-item">
                      <Skel w={8} h={8} radius={4} className="cc-feed-bullet-skel" />
                      <div className="cc-feed-body">
                        <div className="cc-feed-head">
                          <Skel w={80} h={11} />
                          <Skel w={54} h={11} />
                        </div>
                        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                          <Skel w="100%" h={12} />
                          <Skel w="72%" h={12} />
                        </div>
                      </div>
                    </div>
                  ))}
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
  live,
  body,
  confidence,
  impact,
  impactTone,
  onClick,
  onWikilink,
}: {
  title: string;
  priority: string;
  tone: "cyan" | "muted" | "red";
  live: boolean;
  body: string;
  confidence: string;
  impact: string;
  impactTone: string;
  onClick: () => void;
  onWikilink?: (entity: string) => void;
}) {
  return (
    <button className={`cc-rec card lift cc-rec-${tone}`} onClick={onClick}>
      <div className="cc-rec-head">
        <span className="cc-rec-title">{title}</span>
        <Badge tone={tone === "red" ? "red" : tone === "cyan" ? "cyan" : "muted"}>{priority}</Badge>
      </div>
      {live && body ? (
        <p className="cc-rec-body">
          <RichText text={body} onWikilink={onWikilink} />
        </p>
      ) : (
        <div className="cc-rec-body" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Skel w="100%" h={12} />
          <Skel w="88%" h={12} />
          <span className="offline-hint mono" style={{ marginTop: 4 }}>awaiting scenario run</span>
        </div>
      )}
      <div className="cc-rec-foot">
        <div>
          <div className="label-sm">Confidence</div>
          <div className="c-cyan cc-rec-metric">
            {live && confidence ? confidence : <Skel w={44} h={18} />}
          </div>
        </div>
        <div className="cc-rec-foot-right">
          <div className="label-sm">Impact</div>
          <div className={`cc-rec-metric ${impactTone}`}>
            {live && body ? impact : <Skel w={54} h={18} />}
          </div>
        </div>
      </div>
    </button>
  );
}
