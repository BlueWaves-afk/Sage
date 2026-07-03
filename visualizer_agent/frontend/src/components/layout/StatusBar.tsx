import "./layout.css";

export default function StatusBar({ live }: { live?: boolean }) {
  return (
    <footer className="statusbar">
      <div className="statusbar-left">
        <span className="label-sm">SAGE SYSTEM STATUS:</span>
        <span className={`status-word ${live === false ? "c-amber" : "c-green"}`}>
          {live === false ? "DEGRADED" : "OPTIMIZED"}
        </span>
        <span className="statusbar-sep" />
        <span className="statusbar-item">Geospatial Engine 2.1</span>
        <span className="statusbar-item">AIS Sub-mesh</span>
        <span className="statusbar-item">Sanction API</span>
      </div>
      <div className="statusbar-right label-sm">
        © 2026 SAGE NATIONAL ENERGY SECURITY • SECURE • TRUSTED • SOVEREIGN
      </div>
    </footer>
  );
}
