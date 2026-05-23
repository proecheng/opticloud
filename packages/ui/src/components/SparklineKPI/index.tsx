"use client";
/** SparklineKPI (Tier 1). UX-DR1 + FR B7 7d/30d trends + UX-DR5 aria-label. */
import { useA11y } from "../../hooks/useA11y";

export interface SparklineKPIProps {
  values: number[];
  label: string;
  ariaLabel: string;
  /** Optional unit (e.g. "Credits", "ms", "req"). */
  unit?: string;
  /** Width × height in px. */
  width?: number;
  height?: number;
}

export function SparklineKPI({
  values,
  label,
  ariaLabel,
  unit,
  width = 120,
  height = 40,
}: SparklineKPIProps): JSX.Element {
  const a11y = useA11y({
    ariaLabel,
    ariaDescription: `${label} trend: ${values.length} data points, last value ${values[values.length - 1] ?? 0}${unit ? ` ${unit}` : ""}`,
  });
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values
    .map((v, i) => `${i * step},${height - ((v - min) / range) * height}`)
    .join(" ");

  return (
    <div
      {...a11y.attrs}
      className="inline-flex flex-col items-start"
      data-testid="sparkline-kpi"
    >
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-lg font-semibold text-primary">
          {values[values.length - 1] ?? 0}
          {unit && <span className="ml-1 text-xs text-muted-foreground">{unit}</span>}
        </span>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`${label} trend`}
          focusable="false"
        >
          <polyline
            points={points}
            fill="none"
            stroke="#2D5BA8"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  );
}
