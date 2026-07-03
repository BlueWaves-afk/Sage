import "./ambient.css";

// Slow-drifting aurora blobs + fine grid texture behind content. Purely
// decorative depth — sits at z-index 0, pointer-events none, respects
// reduced-motion (the drift animation is disabled by the global media query).
export default function AmbientBackground({ variant = "default" }: { variant?: "default" | "alert" }) {
  return (
    <div className={`ambient ambient-${variant}`} aria-hidden="true">
      <span className="ambient-blob ambient-blob-1" />
      <span className="ambient-blob ambient-blob-2" />
      <span className="ambient-grid" />
    </div>
  );
}
