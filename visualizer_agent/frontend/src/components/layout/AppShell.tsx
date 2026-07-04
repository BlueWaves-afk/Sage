import { Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import IconSidebar from "./IconSidebar";
import TopBar from "./TopBar";
import StatusBar from "./StatusBar";
import VoiceOrbProvider from "../../voice/VoiceOrbProvider";
import { api } from "../../api/hooks";
import "./layout.css";

const TITLES: Record<string, string> = {
  "/command": "National Energy Intelligence Command Center",
  "/intelligence": "Global Intelligence Explorer",
  "/simulation": "Simulation Lab",
  "/response": "Response Planner",
  "/copilot": "Strategic Copilot",
};

export default function AppShell() {
  const { pathname } = useLocation();
  const [live, setLive] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    api.health().then((env) => setLive(env.live && env.data.kb_ready));
  }, []);

  return (
    <div className="shell">
      <IconSidebar />
      <div className="shell-main">
        <TopBar title={TITLES[pathname] ?? "SAGE"} live={live !== false} />
        <div className="shell-content" key={pathname}>
          <Outlet />
        </div>
        <StatusBar live={live} />
      </div>
      <VoiceOrbProvider />
    </div>
  );
}
