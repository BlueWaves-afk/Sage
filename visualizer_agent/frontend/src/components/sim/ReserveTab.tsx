import { Badge } from "../ui/ui";
import { RichText } from "../RichText";
import SprBarChart from "./SprBarChart";
import type { SprSchedule } from "../../api/types";

interface Props {
  spr: SprSchedule;
  onWikilink: (entity: string) => void;
}

export default function ReserveTab({ spr, onWikilink }: Props) {
  return (
    <div className="sim-tab-content">
      {/* Constraint strip */}
      <div className="sim-kpi-strip">
        <div className="sim-kpi">
          <div className="sim-kpi-label">Buffer Satisfied</div>
          <div className="sim-kpi-value">
            <Badge tone={spr.constraint_satisfied ? "cyan" : "red"}>
              {spr.constraint_satisfied ? "YES" : "NO"}
            </Badge>
          </div>
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">P(above buffer)</div>
          <div className="sim-kpi-value">{(spr.prob_above_buffer * 100).toFixed(1)}<span className="sim-kpi-unit">%</span></div>
        </div>
        {spr.lagrange_multiplier != null && (
          <div className="sim-kpi">
            <div className="sim-kpi-label">Lagrange λ</div>
            <div className="sim-kpi-value mono">{spr.lagrange_multiplier.toFixed(4)}</div>
          </div>
        )}
        {spr.option_value_of_waiting != null && (
          <div className="sim-kpi">
            <div className="sim-kpi-label">Option Value</div>
            <div className="sim-kpi-value c-amber">${spr.option_value_of_waiting.toFixed(2)}<span className="sim-kpi-unit">/bbl</span></div>
          </div>
        )}
      </div>

      {/* SPR bar chart */}
      <div className="sim-section">
        <div className="label-sm">
          Daily SPR Plan
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            Draw = amber · Hold = grey · Refill = teal
          </span>
        </div>
        <SprBarChart plan={spr.daily_plan} />
      </div>

      {/* Policy memo */}
      {spr.policy_memo && (
        <div className="sim-section">
          <div className="label-sm">Policy Memo</div>
          <RichText text={spr.policy_memo} onWikilink={onWikilink} />
        </div>
      )}
    </div>
  );
}
