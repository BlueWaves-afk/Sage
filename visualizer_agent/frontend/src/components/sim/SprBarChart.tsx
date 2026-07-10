import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, ReferenceLine, Cell, Legend,
} from "recharts";
import type { SprDay } from "../../api/types";

interface Props { plan: SprDay[]; bufferDays?: number }

const ACTION_COLOR: Record<string, string> = {
  draw:   "#e9c46a",
  hold:   "#4a4a5a",
  refill: "#2dd4bf",
};

export default function SprBarChart({ plan, bufferDays = 3 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <ComposedChart data={plan} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#8892a4" }} label={{ value: "Day", position: "insideBottomRight", offset: -4, fontSize: 10, fill: "#8892a4" }} />
        <YAxis yAxisId="vol" tick={{ fontSize: 10, fill: "#8892a4" }} unit=" MMT" width={52} />
        <YAxis yAxisId="cover" orientation="right" tick={{ fontSize: 10, fill: "#8892a4" }} unit="d" width={36} />
        <Tooltip
          contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
          labelFormatter={(l) => `Day ${l}`}
        />
        <ReferenceLine yAxisId="cover" y={bufferDays} stroke="rgba(231,111,81,0.6)" strokeDasharray="4 2" label={{ value: `${bufferDays}d buffer`, fontSize: 9, fill: "#e76f51", position: "insideTopRight" }} />
        <Bar yAxisId="vol" dataKey="volume_mmt" name="Volume (MMT)" radius={[2, 2, 0, 0]}>
          {plan.map((d) => <Cell key={d.day} fill={ACTION_COLOR[d.action] ?? "#4a4a5a"} />)}
        </Bar>
        <Line yAxisId="cover" dataKey="days_cover_after" stroke="#4bb8d9" strokeWidth={1.5} dot={false} name="Days cover" />
        <Legend wrapperStyle={{ fontSize: 10, color: "#8892a4" }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
