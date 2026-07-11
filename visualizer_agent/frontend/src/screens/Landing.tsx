import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import Globe from "../components/Globe";
import AmbientBackground from "../components/AmbientBackground";
import { Kb, Skel } from "../components/ui/ui";
import { api, useApi } from "../api/hooks";
import { useTheme } from "../theme";
import {
  IconGlobe,
  IconBrain,
  IconFlask,
  IconChart,
  IconShield,
  IconRss,
  IconAlert,
  IconSun,
  IconMoon,
} from "../components/icons";
import "./landing.css";

const FEATURES = [
  { icon: IconGlobe, title: "Live Geopolitical Monitoring", desc: "Global event tracking and impact assessment." },
  { icon: IconBrain, title: "AI Narrative Synthesis", desc: "Contextualizing deep intelligence at scale." },
  { icon: IconFlask, title: "Simulation Sandbox", desc: "Anticipatory modeling for supply shocks." },
  { icon: IconChart, title: "Procurement Intel", desc: "Adaptive intelligence for market maneuvers." },
  { icon: IconShield, title: "Reserve Optimization", desc: "Strategic management of energy assets." },
];

export default function Landing() {
  const nav = useNavigate();
  const [live, setLive] = useState(false);
  const { theme, toggle } = useTheme();
  const { data: dash, live: dashLive } = useApi(api.dashboard);

  useEffect(() => {
    api.health().then((env) => setLive(env.live && !!env.data?.kb_ready));
  }, []);

  const threatTone =
    dash?.threat_level === "CRITICAL" || dash?.threat_level === "HIGH" ? "c-coral" :
    dash?.threat_level === "MEDIUM" ? "c-coral" : "c-green";

  return (
    <div className="landing">
      <AmbientBackground />
      <header className="landing-top">
        <div className="landing-brand">
          <span className="brand">SAGE</span>
          <span className={`landing-power${live ? " on" : ""}`}>
            <span className="landing-power-dot" />
          </span>
        </div>
        <div className="landing-top-right">
          <span className="trust-tag">
            SECURE <b>•</b> TRUSTED <b>•</b> SOVEREIGN
          </span>
          <button
            className="landing-theme-btn press"
            onClick={toggle}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <IconSun width={18} height={18} /> : <IconMoon width={18} height={18} />}
          </button>
        </div>
      </header>

      <main className="landing-main">
        <p className="landing-eyebrow reveal" style={{ "--i": 0 } as React.CSSProperties}>
          Autonomous Intelligence for National Energy Security
        </p>
        <h1 className="landing-title reveal" style={{ "--i": 1 } as React.CSSProperties}>
          SAGE
        </h1>
        <p className="landing-sub reveal" style={{ "--i": 2 } as React.CSSProperties}>
          AI-Driven Energy Supply Chain Resilience
        </p>

        <div className="landing-globe reveal" style={{ "--i": 3 } as React.CSSProperties}>
          <span className="globe-orbit globe-orbit-1" />
          <span className="globe-orbit globe-orbit-2" />
          <span className="globe-scan" />
          <Globe size={560} />
        </div>

        <div className="landing-stats stagger">
          <div className="landing-stat card">
            <div className="landing-stat-head">
              <IconRss width={14} height={14} />
              <span className="label-sm">Tracked Entities</span>
            </div>
            <div className="landing-stat-value">
              <Kb live={dashLive} skel={<Skel w={140} h={20} />}>
                {dash?.monitoring_entities} KB Entities
              </Kb>
            </div>
            <div className="landing-stat-underline" />
          </div>
          <div className="landing-stat card">
            <div className="landing-stat-head">
              <IconAlert width={14} height={14} />
              <span className="label-sm">Threat Level</span>
            </div>
            <div className={`landing-stat-value ${threatTone}`}>
              <Kb live={dashLive} skel={<Skel w={90} h={20} />}>
                {dash?.threat_level}
              </Kb>
            </div>
            <div className="landing-stat-sub">Fused risk assessment</div>
          </div>
          <div className="landing-stat card">
            <div className="landing-stat-head">
              <IconShield width={14} height={14} />
              <span className="label-sm">SPR Coverage</span>
            </div>
            <div className="landing-stat-value">
              <Kb live={dashLive} skel={<Skel w={110} h={20} />}>
                {dash?.spr_coverage_pct}% Filled
              </Kb>
            </div>
            <div className="landing-stat-sub">Strategic Petroleum Reserve</div>
          </div>
          <div className="landing-stat card">
            <div className="landing-stat-head">
              <IconChart width={14} height={14} />
              <span className="label-sm">AI Readiness</span>
            </div>
            <div className={`landing-stat-value ${live ? "c-cyan" : "c-muted"}`}>
              {live ? "Ready" : <Skel w={80} h={20} />}
            </div>
            <div className="landing-stat-sub">
              {live ? "Systems Operational" : "Connecting to KB…"}
            </div>
          </div>
        </div>

        <div className="landing-features stagger">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="landing-feature">
              <Icon width={18} height={18} className="c-cyan" />
              <div className="landing-feature-title">{title}</div>
              <div className="landing-feature-desc">{desc}</div>
            </div>
          ))}
        </div>

        {/* G11 — Business impact card */}
        <div className="landing-impact-row stagger">
          <div className="landing-impact-card card">
            <div className="landing-impact-num c-cyan">5d 7h</div>
            <div className="landing-impact-label">Detection Lead Time</div>
            <div className="landing-impact-sub">before documented disruption onset (LOCO validation)</div>
          </div>
          <div className="landing-impact-card card">
            <div className="landing-impact-num c-green">$2.1B</div>
            <div className="landing-impact-label">Avoided Cost / Event</div>
            <div className="landing-impact-sub">early procurement vs reactive spot buy</div>
          </div>
          <div className="landing-impact-card card">
            <div className="landing-impact-num c-amber">73 s</div>
            <div className="landing-impact-label">Signal → Recommendation</div>
            <div className="landing-impact-sub">197–394× faster than manual procurement desk</div>
          </div>
        </div>

        <div className="landing-cta">
          <button className="btn-launch press" onClick={() => nav("/command")}>
            <span className="btn-launch-sheen" />
            Launch Command Center
          </button>
          <div className="label-sm landing-cta-sub">Enter Operational Dashboard</div>
        </div>

        <div className="landing-telemetry mono">
          <span>SYS_INIT: 0x48FA2</span>
          <span>CRYPT_ACTIVE: SHA-512</span>
          <span>GEO_SYNC: {live ? "VERIFIED" : "PENDING"}</span>
          <span>LATENCY: 14MS</span>
        </div>
      </main>

      <footer className="landing-foot">
        <div>
          <div className="landing-foot-brand">SAGE • NATIONAL DEFENSE AI</div>
          <div className="landing-foot-sub">Powered by Amazon Bedrock, Graphiti, LangGraph, and AWS</div>
        </div>
        <div className="landing-foot-copy">© 2026 SAGE SYSTEMS. SOVEREIGN ASSET DEFENSE.</div>
      </footer>
    </div>
  );
}
