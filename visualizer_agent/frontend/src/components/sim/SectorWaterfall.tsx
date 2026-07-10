import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell } from "recharts";
import type { SectorImpact } from "../../api/types";

interface Props { sectors: SectorImpact[] }

function critColor(c: number): string {
  if (c >= 0.8) return "#e63946";
  if (c >= 0.6) return "#e76f51";
  if (c >= 0.4) return "#f4a261";
  return "#e9c46a";
}

export default function SectorWaterfall({ sectors }: Props) {
  const sorted = [...sectors].sort((a, b) => b.shortfall_mbpd - a.shortfall_mbpd);
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, sorted.length * 36)}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 40, left: 80, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 10, fill: "#8892a4" }} unit=" mbpd" />
        <YAxis type="category" dataKey="sector" tick={{ fontSize: 10, fill: "#8892a4" }} width={78} />
        <Tooltip
          contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
          formatter={(v: unknown) => [`${Number(v).toFixed(3)} mbpd`, "Shortfall"]}
        />
        <Bar dataKey="shortfall_mbpd" radius={[0, 3, 3, 0]}>
          {sorted.map((s) => <Cell key={s.sector} fill={critColor(s.criticality)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
