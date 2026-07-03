import { NavLink } from "react-router-dom";
import {
  IconDashboard,
  IconGlobe,
  IconFlask,
  IconShield,
  IconBot,
  IconGear,
} from "../icons";
import "./layout.css";

const NAV = [
  { to: "/command", icon: IconDashboard, label: "Command Center" },
  { to: "/intelligence", icon: IconGlobe, label: "Global Intelligence" },
  { to: "/simulation", icon: IconFlask, label: "Simulation Lab" },
  { to: "/response", icon: IconShield, label: "Response Planner" },
  { to: "/copilot", icon: IconBot, label: "Strategic Copilot" },
];

export default function IconSidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `side-btn${isActive ? " active" : ""}`}
            title={label}
          >
            <Icon />
          </NavLink>
        ))}
      </div>
      <NavLink to="/command" className="side-btn side-gear" title="Settings">
        <IconGear />
      </NavLink>
    </nav>
  );
}
