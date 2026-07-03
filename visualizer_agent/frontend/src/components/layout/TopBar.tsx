import { IconUser } from "../icons";
import "./layout.css";

interface Props {
  title: string;
  live?: boolean;
}

export default function TopBar({ title, live = true }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="brand">SAGE</span>
        <span className={`online-pill${live ? "" : " offline"}`}>
          <span className="online-dot" />
          {live ? "ONLINE" : "OFFLINE"}
        </span>
        <span className="topbar-divider" />
        <span className="topbar-title">{title}</span>
      </div>
      <div className="topbar-right">
        <span className="trust-tag">
          Secure <b>•</b> Trusted <b>•</b> Sovereign
        </span>
        <div className="operator">
          <div className="operator-meta">
            <span className="operator-name">C.J.Rao</span>
            <span className="operator-role">OPERATOR 07</span>
          </div>
          <div className="operator-avatar">
            <IconUser width={16} height={16} />
          </div>
        </div>
      </div>
    </header>
  );
}
