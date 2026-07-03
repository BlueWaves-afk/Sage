import type { ReactNode } from "react";
import "./ui.css";

type Tone = "cyan" | "green" | "amber" | "coral" | "red" | "muted";

const toneClass: Record<Tone, string> = {
  cyan: "c-cyan",
  green: "c-green",
  amber: "c-amber",
  coral: "c-coral",
  red: "c-red",
  muted: "c-muted",
};

/** Titled panel with an uppercase header. */
export function Panel({
  title,
  right,
  children,
  className = "",
  bodyClass = "",
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <div className="panel-head">
          {title && <span className="label">{title}</span>}
          {right}
        </div>
      )}
      <div className={`panel-body ${bodyClass}`}>{children}</div>
    </section>
  );
}

/** KPI stat tile: uppercase label + big value + optional sublabel. */
export function StatCard({
  label,
  value,
  tone = "cyan",
  sub,
  icon,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
  sub?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="statcard card">
      <div className="statcard-label">
        {icon && <span className="statcard-icon">{icon}</span>}
        <span className="label">{label}</span>
      </div>
      <div className={`statcard-value ${toneClass[tone]}`}>{value}</div>
      {sub && <div className="statcard-sub">{sub}</div>}
    </div>
  );
}

export function Badge({
  children,
  tone = "cyan",
  outline = false,
}: {
  children: ReactNode;
  tone?: Tone;
  outline?: boolean;
}) {
  return (
    <span className={`badge badge-${tone}${outline ? " badge-outline" : ""}`}>
      {children}
    </span>
  );
}

/** A labelled progress meter (confidence, fill %, etc.). */
export function Meter({ value, tone = "cyan" }: { value: number; tone?: Tone }) {
  return (
    <div className="meter">
      <div
        className={`meter-fill meter-${tone}`}
        style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }}
      />
    </div>
  );
}

export function OfflineHint({ live }: { live: boolean }) {
  if (live) return null;
  return <span className="offline-hint mono">demo data</span>;
}
