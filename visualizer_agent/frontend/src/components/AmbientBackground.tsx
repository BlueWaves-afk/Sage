// Intentionally a no-op. Enterprise dashboards read best on a flat, solid
// background — the earlier glowing-blob + grid-texture treatment read as an
// "AI-generated concept" rather than an industrial tool, per design review.
// Kept as a component (rather than deleting the import sites) so re-enabling
// a subtle background later is a one-line change.
export default function AmbientBackground(_props: { variant?: "default" | "alert" }) {
  return null;
}
