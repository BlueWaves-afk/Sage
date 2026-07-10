import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, Legend,
} from "recharts";
import type { ScenarioOutput, MonteCarloBands } from "../../api/types";

interface Props {
  scenario: ScenarioOutput;
}

export default function GapFanChart({ scenario }: Props) {
  const timeline = scenario.feedstock_gap_timeline ?? [];
  const mc = (scenario.assumptions?.monte_carlo as unknown as MonteCarloBands) ?? null;

  const data = timeline.map((p50, i) => {
    const row: Record<string, number> = { day: i, p50: +p50.toFixed(3) };
    if (mc) {
      const ratio10 = mc.gap_mbpd.p10 / (mc.gap_mbpd.p50 || 1);
      const ratio90 = mc.gap_mbpd.p90 / (mc.gap_mbpd.p50 || 1);
      row.p10 = +(p50 * ratio10).toFixed(3);
      row.p90 = +(p50 * ratio90).toFixed(3);
      row.band = row.p90 - row.p10;
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#8892a4" }} label={{ value: "Day", position: "insideBottomRight", offset: -4, fontSize: 10, fill: "#8892a4" }} />
        <YAxis tick={{ fontSize: 10, fill: "#8892a4" }} unit=" mbpd" width={58} />
        <Tooltip
          contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
          labelFormatter={(l) => `Day ${l}`}
          formatter={(v: unknown) => [`${Number(v).toFixed(3)} mbpd`]}
        />
        {mc && (
          <Area
            dataKey="p10"
            stroke="none"
            fill="rgba(75,184,217,0.08)"
            stackId="band"
            name="p10"
            dot={false}
            legendType="none"
          />
        )}
        {mc && (
          <Area
            dataKey="band"
            stroke="none"
            fill="rgba(75,184,217,0.14)"
            stackId="band"
            name={`MC p10–p90 (n=${mc.n})`}
            dot={false}
          />
        )}
        <Line dataKey="p50" stroke="#4bb8d9" strokeWidth={2} dot={false} name="Gap (p50)" />
        <Legend wrapperStyle={{ fontSize: 10, color: "#8892a4" }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
