import { useCountUp } from "../hooks/useCountUp";

// Animates the numeric part of a value on mount, preserving prefix/suffix.
// e.g. prefix="$" value={82.45} decimals={2} suffix="" → "$82.45" counting up.
export default function AnimatedNumber({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 1100,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}) {
  const shown = useCountUp(value, duration, decimals);
  return (
    <span className="tabular">
      {prefix}
      {shown}
      {suffix}
    </span>
  );
}
