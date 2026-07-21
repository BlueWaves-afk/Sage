import { useNavigate } from "react-router-dom";
import { useState } from "react";
import Globe from "../components/Globe";
import { useTheme } from "../theme";
import {
  IconLogo,
  IconShield,
  IconSun,
  IconMoon,
} from "../components/icons";
import "./landing.css";

export default function Landing() {
  const nav = useNavigate();
  const { theme, toggle } = useTheme();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");

  return (
    <div className="landing">
      {/* ── Top Header Bar ── */}
      <header className="landing-top">
        <div className="landing-brand">
          <span className="landing-brand-name">SAGE</span>
          <span className="landing-online-pill">
            <span className="landing-online-dot" />
            ONLINE
          </span>
        </div>
        <div className="landing-top-right">
          <span className="trust-tag">
            Secure <b>•</b> Trusted <b>•</b> Intelligent
          </span>
          <button
            className="landing-theme-btn press"
            onClick={toggle}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <IconSun width={16} height={16} /> : <IconMoon width={16} height={16} />}
          </button>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="landing-hero">
        <div className="landing-logo-wrap">
          <IconLogo width={80} height={100} className="landing-logo-icon" />
        </div>
        <h1 className="landing-title">SAGE</h1>
        <p className="landing-eyebrow">
          SYNTHESIS-FIRST AGENTIC GRAPH-ENHANCED ARCHITECTURE
        </p>
        <p className="landing-sub">
          AI-Driven Energy Supply Chain Resilience
        </p>
      </section>

      {/* ── Map / Network Visualization ── */}
      <section className="landing-map-section">
        <div className="landing-map-panel">
          <span className="landing-map-label">
            SAG<span className="landing-map-label-dim">E</span>
          </span>
          <Globe size={400} />
        </div>
      </section>

      {/* ── Feature Buttons ── */}
      <section className="landing-features-row">
        <button className="landing-feat-btn" onClick={() => nav("/command")}>
          LIVE DATA-STREAM
        </button>
        <span className="landing-feat-sep">•</span>
        <button className="landing-feat-btn" onClick={() => nav("/intelligence")}>
          KNOWLEDGE GRAPH
        </button>
        <span className="landing-feat-sep">•</span>
        <button className="landing-feat-btn" onClick={() => nav("/simulation")}>
          AI SIMULATION
        </button>
        <span className="landing-feat-sep">•</span>
        <button className="landing-feat-btn" onClick={() => nav("/response")}>
          AUTONOMOUS DECISIONS
        </button>
      </section>

      {/* ── Login Section (scroll-below, auth disabled for now) ── */}
      <section className="landing-login-section">
        <div className="landing-login-card">
          <h2 className="landing-login-title">Secure Platform Access</h2>

          <div className="landing-login-field">
            <label className="landing-login-label">USERNAME</label>
            <input
              type="text"
              className="landing-login-input"
              placeholder="Enter identification code"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="landing-login-field">
            <label className="landing-login-label">EMAIL ADDRESS</label>
            <input
              type="email"
              className="landing-login-input"
              placeholder="government@domain.gov"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {/* Auth bypassed — direct entry to Command Center */}
          <button
            className="landing-access-btn"
            onClick={() => nav("/command")}
          >
            Access Platform
            <IconShield width={16} height={16} />
          </button>

          <div className="landing-auth-notice">
            <IconShield width={12} height={12} />
            AUTHORIZED PERSONNEL ONLY
          </div>
        </div>
      </section>

      {/* ── Bottom Status Bar ── */}
      <footer className="landing-bottom-bar">
        <div className="landing-bottom-main">
          <div className="landing-bottom-left">
            <span className="landing-bottom-frame">frame</span>
          </div>
          <div className="landing-bottom-marquee">
            <div className="landing-marquee-track">
              <span>
                OBSERVE &nbsp;•&nbsp; UNDERSTAND &nbsp;•&nbsp; SIMULATE
                &nbsp;•&nbsp; DECIDE &nbsp;&nbsp;&nbsp;&nbsp;
              </span>
              <span>
                OBSERVE &nbsp;•&nbsp; UNDERSTAND &nbsp;•&nbsp; SIMULATE
                &nbsp;•&nbsp; DECIDE &nbsp;&nbsp;&nbsp;&nbsp;
              </span>
            </div>
          </div>
          <div className="landing-bottom-right-status">
            <span className="landing-status-label">SAGE SYSTEM STATUS:</span>
            <span className="landing-status-value">OPTIMIZED</span>
          </div>
        </div>
        <div className="landing-bottom-sub">
          <span className="landing-bottom-tech">
            Geospatial Engine 2.7 &nbsp;&nbsp; AIS Sub-mesh &nbsp;&nbsp;
            Sanction API
          </span>
          <span className="landing-bottom-copy">
            © 2026 SAGE NATIONAL ENERGY SECURITY • SECURE • TRUSTED • SOVEREIGN
          </span>
        </div>
      </footer>
    </div>
  );
}
