import { useEffect, useState } from "react";
import { useTheme } from "../../theme";
import { IconUser, IconLogo, IconSun, IconMoon } from "../icons";
import { apiPrefix } from "../../api/region";
import RegionSwitcher from "./RegionSwitcher";
import "./layout.css";

interface Props {
  title: string;
  live?: boolean;
}

function useDemoStatus() {
  const [demo, setDemo] = useState<{ active: boolean; crisis?: string | null } | null>(null);
  useEffect(() => {
    const check = () =>
      fetch(`${apiPrefix()}/api/demo/status`)
        .then((r) => r.json())
        .then(setDemo)
        .catch(() => {});
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);
  return demo;
}

export default function TopBar({ title, live }: Props) {
  const demo = useDemoStatus();
  const { theme, toggle } = useTheme();
  const status = live == null ? "CONNECTING" : live ? "ONLINE" : "OFFLINE";
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="brand" style={{ display: "flex", alignItems: "center", paddingRight: "4px" }}>
          <IconLogo width={18} height={23} />
        </span>
        <span className={`online-pill${live ? "" : " offline"}`}>
          <span className="online-dot" />
          {status}
        </span>
        <span className="topbar-divider" />
        <span className="topbar-title">{title}</span>
        {demo?.active && (
          <span className="replay-chip">
            REPLAY · {demo.crisis ?? "Historical crisis"}
          </span>
        )}
      </div>
      <div className="topbar-right">
        <RegionSwitcher />
        <span className="trust-tag">
          Secure <b>•</b> Trusted <b>•</b> Sovereign
        </span>
        <button
          className="theme-btn press"
          onClick={toggle}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          style={{
            background: "rgba(15, 31, 46, 0.1)",
            border: "1px solid rgba(15, 31, 46, 0.2)",
            color: "var(--text-0)",
            width: "32px",
            height: "32px",
            borderRadius: "4px",
            display: "grid",
            placeItems: "center",
            cursor: "pointer"
          }}
        >
          {theme === "dark" ? <IconSun width={16} height={16} /> : <IconMoon width={16} height={16} />}
        </button>
        <div className="operator">
          <div className="operator-avatar">
            <IconUser width={16} height={16} />
          </div>
        </div>
      </div>
    </header>
  );
}
