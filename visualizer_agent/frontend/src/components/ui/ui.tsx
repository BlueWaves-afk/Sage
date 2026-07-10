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
  // There is NO fallback/demo data — when not live, the value simply has no
  // knowledge-base source. Label it honestly as offline, never "demo".
  return <span className="offline-hint mono">offline · no live data</span>;
}

/**
 * Skeleton placeholder — shown wherever a value has no live knowledge-base
 * source yet (loading, backend offline, or awaiting System 1). We deliberately
 * never render fabricated numbers; an empty state animates instead.
 */
export function Skel({
  w = "100%",
  h = 14,
  radius = 6,
  className = "",
}: {
  w?: number | string;
  h?: number | string;
  radius?: number;
  className?: string;
}) {
  return (
    <span
      className={`skeleton ${className}`}
      style={{
        display: "inline-block",
        width: typeof w === "number" ? `${w}px` : w,
        height: typeof h === "number" ? `${h}px` : h,
        borderRadius: radius,
        verticalAlign: "middle",
      }}
    />
  );
}

/** A few skeleton lines + an honest note, for empty data regions. */
export function SkeletonBlock({ note, lines = 3 }: { note?: string; lines?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skel key={i} w={i === lines - 1 ? "62%" : "100%"} h={13} />
      ))}
      {note && (
        <span className="offline-hint mono" style={{ marginTop: 4, alignSelf: "flex-start" }}>
          {note}
        </span>
      )}
    </div>
  );
}

/**
 * Render `children` only when the value is genuinely from the KB (`live`), else
 * a skeleton. `loading` forces the skeleton while a request is in flight.
 */
export function Kb({
  live,
  loading = false,
  skel,
  children,
}: {
  live: boolean;
  loading?: boolean;
  skel?: ReactNode;
  children: ReactNode;
}) {
  if (loading || !live) return <>{skel ?? <Skel w="70%" />}</>;
  return <>{children}</>;
}
