import { useEffect, useState } from "react";
import { IconUser, IconLogo } from "../icons";
import "./layout.css";

interface Props {
  title: string;
  live?: boolean;
}

function useDemoStatus() {
  const [demo, setDemo] = useState<{ active: boolean; crisis?: string | null } | null>(null);
  useEffect(() => {
    const check = () =>
      fetch("/api/demo/status")
        .then((r) => r.json())
        .then(setDemo)
        .catch(() => {});
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);
  return demo;
}

export default function TopBar({ title, live = true }: Props) {
  const demo = useDemoStatus();
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="brand" style={{ display: "flex", alignItems: "center", paddingRight: "4px" }}>
          <IconLogo width={18} height={23} />
        </span>
        <span className={`online-pill${live ? "" : " offline"}`}>
          <span className="online-dot" />
          {live ? "ONLINE" : "OFFLINE"}
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
        <span className="trust-tag">
          Secure <b>•</b> Trusted <b>•</b> Sovereign
        </span>
        <div className="operator">
          <div className="operator-avatar">
            <IconUser width={16} height={16} />
          </div>
        </div>
      </div>
    </header>
  );
}
