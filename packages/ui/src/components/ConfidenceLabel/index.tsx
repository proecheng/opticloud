"use client";
/** ConfidenceLabel (Tier 1, Story 0.9 + Story 4.B.4 + CRG14 visual brackets).
 *
 * UX Spec Step 11 + EP4 Critic 视觉化.
 * Visual brackets (CRG14):
 *   ≥0.85 绿  "高置信"
 *   0.6-0.85 黄 "中置信"
 *   <0.6 红    "低置信请人工 review"
 *
 * a11y: aria-label "Confidence: 0.85"; aria-describedby for 中英 reasoning.
 */

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface ConfidenceLabelProps {
  /** Confidence score 0..1 (FR N12). */
  score: number;
  /** Chinese label (i18n: confidence.high/mid/low). */
  labelZh?: string;
  /** English label. */
  labelEn?: string;
  /** Reasoning text (UX-DR1 + EP4). */
  reasoning?: string;
  /** Compact mode for inline display. */
  compact?: boolean;
}

function tierFromScore(score: number): "high" | "mid" | "low" {
  if (score >= 0.85) return "high";
  if (score >= 0.6) return "mid";
  return "low";
}

const tierLabels: Record<"high" | "mid" | "low", { zh: string; en: string }> = {
  high: { zh: "高置信", en: "High Confidence" },
  mid: { zh: "中置信", en: "Mid Confidence" },
  low: { zh: "低置信请人工 review", en: "Low Confidence — Human Review" },
};

const tierStyles: Record<"high" | "mid" | "low", string> = {
  high: "bg-confidence-high/10 border-confidence-high text-confidence-high",
  mid: "bg-confidence-mid/10 border-confidence-mid text-confidence-mid",
  low: "bg-confidence-low/10 border-confidence-low text-confidence-low",
};

export function ConfidenceLabel({
  score,
  labelZh,
  labelEn,
  reasoning,
  compact = false,
}: ConfidenceLabelProps): JSX.Element {
  const tier = tierFromScore(score);
  const labels = tierLabels[tier];
  const zh = labelZh ?? labels.zh;
  const en = labelEn ?? labels.en;
  const a11y = useA11y({
    ariaLabel: `Confidence: ${score.toFixed(2)} — ${en}`,
    ariaDescription: reasoning,
  });

  return (
    <span
      {...a11y.attrs}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium",
        tierStyles[tier],
        compact ? "px-1" : "",
      )}
      data-testid="confidence-label"
      data-tier={tier}
    >
      <span className="font-mono">{score.toFixed(2)}</span>
      <span className="text-balance">{zh}</span>
      {!compact && reasoning && (
        <span id={`${a11y.id}-desc`} className="ml-2 text-muted-foreground">
          ({en})
        </span>
      )}
    </span>
  );
}
