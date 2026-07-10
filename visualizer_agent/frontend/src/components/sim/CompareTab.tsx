import type { RunSummary, ScenarioOutput } from "../../api/types";

interface Props {
  runs: RunSummary[];
  baseline: ScenarioOutput | null;
}

const COLS: { key: keyof RunSummary | "baseline"; label: string; unit: string }[] = [
  { key: "gap_mbpd",           label: "Peak Gap",      unit: " mbpd" },
  { key: "price_impact_high",  label: "Price High",    unit: " $/bbl" },
  { key: "gdp_proxy_impact_pct", label: "GDP Hit",     unit: "%" },
  { key: "spr_depletion_days", label: "SPR Depletion", unit: " d" },
  { key: "gap_duration_days",  label: "Duration",      unit: " d" },
];

function fmtVal(v: number | null, unit: string): string {
  if (v == null) return "—";
  return `${v.toFixed(2)}${unit}`;
}

export default function CompareTab({ runs, baseline }: Props) {
  const baselineCol = baseline ? {
    label: "Baseline (cached)",
    gap_mbpd: baseline.gap_mbpd,
    price_impact_high: baseline.price_impact_high,
    gdp_proxy_impact_pct: baseline.gdp_proxy_impact_pct,
    spr_depletion_days: baseline.spr_depletion_days,
    gap_duration_days: baseline.gap_duration_days,
  } : null;

  const allCols = [
    ...(baselineCol ? [{ ...baselineCol, isBaseline: true }] : []),
    ...runs.slice(-3).map((r) => ({ ...r, label: r.label, isBaseline: false })),
  ];

  if (allCols.length === 0) {
    return (
      <div className="sim-tab-content">
        <p style={{ color: "var(--text-3)", fontSize: 13 }}>
          Run at least one scenario to populate the comparison view.
        </p>
      </div>
    );
  }

  return (
    <div className="sim-tab-content">
      <div className="sim-section">
        <div className="label-sm">Scenario Comparison (last 3 runs + baseline)</div>
        <div className="sim-table-wrap">
          <table className="sim-table sim-compare-table">
            <thead>
              <tr>
                <th>Metric</th>
                {allCols.map((c, i) => (
                  <th key={i} style={{ color: c.isBaseline ? "var(--text-2)" : "var(--cyan)" }}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COLS.map(({ key, label, unit }) => (
                <tr key={key}>
                  <td style={{ color: "var(--text-2)", fontSize: 11 }}>{label}</td>
                  {allCols.map((col, i) => {
                    const val = (col as unknown as Record<string, number | null>)[key as string];
                    return (
                      <td key={i} className={col.isBaseline ? "" : "c-cyan"}>
                        {fmtVal(typeof val === "number" ? val : null, unit)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sensitivity note when two runs differ by one param */}
      {runs.length >= 2 && (() => {
        const a = runs[runs.length - 2];
        const b = runs[runs.length - 1];
        const dGap = (b.gap_mbpd - a.gap_mbpd).toFixed(3);
        const dDur = b.gap_duration_days - a.gap_duration_days;
        return (
          <div className="sim-callout">
            <span className="label-sm c-amber">Sensitivity note:</span>{" "}
            {a.label} → {b.label}: Δgap {dGap} mbpd · Δduration {dDur}d
          </div>
        );
      })()}
    </div>
  );
}
