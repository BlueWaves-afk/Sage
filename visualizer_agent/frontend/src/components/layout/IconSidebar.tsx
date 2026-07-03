import { NavLink } from "react-router-dom";
import {
  IconDashboard,
  IconGlobe,
  IconFlask,
  IconShield,
  IconBot,
  IconGear,
  IconSun,
  IconMoon,
} from "../icons";
import { useTheme } from "../../theme";
import "./layout.css";

const NAV = [
  { to: "/command", icon: IconDashboard, label: "Command Center" },
  { to: "/intelligence", icon: IconGlobe, label: "Global Intelligence" },
  { to: "/simulation", icon: IconFlask, label: "Simulation Lab" },
  { to: "/response", icon: IconShield, label: "Response Planner" },
  { to: "/copilot", icon: IconBot, label: "Strategic Copilot" },
];

export default function IconSidebar() {
  const { theme, toggle } = useTheme();
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
      <div className="sidebar-foot">
        <button
          className="side-btn press"
          onClick={toggle}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <IconSun /> : <IconMoon />}
        </button>
        <NavLink to="/command" className="side-btn" title="Settings">
          <IconGear />
        </NavLink>
      </div>
    </nav>
  );
}
