import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { ProcurementOption } from "../../api/types";

interface Props { option: ProcurementOption }

const DIMS = [
  { key: "grade_compatibility", label: "Grade Fit" },
  { key: "corridor_risk",       label: "Route Safety", invert: true },
  { key: "topsis_score",        label: "TOPSIS" },
];

export default function ScoreBreakdown({ option }: Props) {
  const data = DIMS.map(({ key, label, invert }) => {
    const raw = (option as unknown as Record<string, number>)[key] ?? 0;
    return { axis: label, value: +(invert ? 1 - raw : raw).toFixed(3) };
  });

  return (
    <ResponsiveContainer width="100%" height={160}>
      <RadarChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 20 }}>
        <PolarGrid stroke="rgba(255,255,255,0.12)" />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10, fill: "#8892a4" }} />
        <Radar dataKey="value" stroke="#4bb8d9" fill="rgba(75,184,217,0.18)" strokeWidth={1.5} />
        <Tooltip
          contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
          formatter={(v: unknown) => [Number(v).toFixed(3), "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
