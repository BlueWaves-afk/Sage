import { useNavigate } from "react-router-dom";
import MapView from "../components/MapView";
import PipelineBar from "../components/PipelineBar";
import { Panel, Badge, Meter, OfflineHint } from "../components/ui/ui";
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

const KPIS = [
  { label: "Threat Level", value: "MEDIUM", tone: "c-amber" },
  { label: "Brent Crude", value: "$82.45", tone: "", up: true },
  { label: "SPR Coverage", value: "94.2%", tone: "" },
  { label: "Active Alerts", value: "12", tone: "c-amber", warn: true },
  { label: "Monitoring Sources", value: "1,402", tone: "", sub: "ACTIVE" },
  { label: "Mode", value: "LIVE", tone: "c-cyan" },
];

export default function CommandCenter() {
  const nav = useNavigate();
  const { data: risk, live } = useApi(api.riskScores);

  return (
    <div className="cc">
      {/* KPI row */}
      <div className="cc-kpis">
        {KPIS.map((k) => (
          <div key={k.label} className="cc-kpi card">
            <span className="label-sm">{k.label}</span>
            <div className={`cc-kpi-value ${k.tone}`}>
              {k.value}
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
              <MapView nodes={risk ?? []} />
              <div className="cc-map-overlay">
                <div className="cc-bottlenecks">
                  <div className="label-sm">Maritime Bottlenecks</div>
                  <Row name="Hormuz" status="NOMINAL" tone="green" />
                  <Row name="Red Sea" status="CONTESTED" tone="amber" />
                  <Row name="Malacca" status="NOMINAL" tone="green" />
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
              right={<Badge tone="cyan">Confidence: 94%</Badge>}
            >
              <div className="label-sm">Narrative Summary</div>
              <p className="cc-narrative">
                "Geopolitical tension in the Red Sea has reached a critical threshold. SAGE models
                predict a 12% increase in Brent Crude volatility over the next 48 hours. Strategic
                pivoting of tankers is underway."
              </p>
              <div className="label-sm cc-brief-sec">Threat Assessment</div>
              <div className="cc-threat">
                <span>
                  Supply Disruption <b className="c-red">HIGH</b>
                </span>
                <Meter value={0.82} tone="red" />
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
          <div className="cc-recs">
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
    </div>
  );
}

function Row({ name, status, tone }: { name: string; status: string; tone: string }) {
  return (
    <div className="cc-bottleneck-row">
      <span className="cc-bottleneck-name">{name}</span>
      <Badge tone={tone as "green" | "amber"}>{status}</Badge>
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
    <button className={`cc-rec card cc-rec-${tone}`} onClick={onClick}>
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
