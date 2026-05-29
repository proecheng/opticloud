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
  /** Label display locale. Defaults to Chinese-only to preserve existing compact UI. */
  locale?: "zh-CN" | "en-US" | "mixed";
  /** Chinese label (i18n: confidence.high/mid/low). */
  labelZh?: string;
  /** English label. */
  labelEn?: string;
  /** Back-compatible single reasoning text (UX-DR1 + EP4). */
  reasoning?: string;
  /** Chinese bounded Critic reasoning. */
  reasoningZh?: string;
  /** English bounded Critic reasoning. */
  reasoningEn?: string;
  /** Compact mode for inline display. */
  compact?: boolean;
}

function tierFromScore(score: number): "high" | "mid" | "low" {
  if (score >= 0.85) return "high";
  if (score >= 0.6) return "mid";
  return "low";
}

const tierLabels: Record<"high" | "mid" | "low", { zh: string; en: string }> = {
  high: { zh: "高置信", en: "High confidence" },
  mid: { zh: "中置信", en: "Medium confidence" },
  low: { zh: "低置信请人工 review", en: "Low confidence; human review recommended" },
};

const tierStyles: Record<"high" | "mid" | "low", string> = {
  high: "bg-confidence-high/10 border-confidence-high text-confidence-high",
  mid: "bg-confidence-mid/10 border-confidence-mid text-confidence-mid",
  low: "bg-confidence-low/10 border-confidence-low text-confidence-low",
};

export function ConfidenceLabel({
  score,
  locale = "zh-CN",
  labelZh,
  labelEn,
  reasoning,
  reasoningZh,
  reasoningEn,
  compact = false,
}: ConfidenceLabelProps): JSX.Element {
  const boundedScore = normalizeScore(score);
  const scoreText = boundedScore.toFixed(2);
  const tier = tierFromScore(boundedScore);
  const labels = tierLabels[tier];
  const zh = labelZh ?? labels.zh;
  const en = labelEn ?? labels.en;
  const displayLabel = formatLabel({ locale, zh, en });
  const description = formatReasoning({ reasoning, reasoningZh, reasoningEn });
  const a11y = useA11y({
    ariaLabel: `Confidence: ${scoreText} - ${en}`,
    ariaDescription: description,
  });

  return (
    <>
      <span
        {...a11y.attrs}
        className={cn(
          "inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium",
          tierStyles[tier],
          compact ? "px-1" : "",
        )}
        data-testid="confidence-label"
        data-tier={tier}
      >
        <span className="shrink-0 font-mono">{scoreText}</span>
        <span className="min-w-0 truncate">{displayLabel}</span>
      </span>
      {description && (
        <span
          id={`${a11y.id}-desc`}
          className={compact ? "sr-only" : "ml-2 text-xs text-muted-foreground"}
        >
          {description}
        </span>
      )}
    </>
  );
}

function normalizeScore(score: number): number {
  if (!Number.isFinite(score) || score < 0 || score > 1) {
    return 0;
  }
  return score;
}

function formatLabel({
  locale,
  zh,
  en,
}: {
  locale: NonNullable<ConfidenceLabelProps["locale"]>;
  zh: string;
  en: string;
}): string {
  if (locale === "en-US") {
    return en;
  }
  if (locale === "mixed") {
    return `${zh} / ${en}`;
  }
  return zh;
}

function formatReasoning({
  reasoning,
  reasoningZh,
  reasoningEn,
}: Pick<ConfidenceLabelProps, "reasoning" | "reasoningZh" | "reasoningEn">): string | undefined {
  const zh = reasoningZh?.trim();
  const en = reasoningEn?.trim();
  const fallback = reasoning?.trim();
  if (zh && en) {
    return `${zh} / ${en}`;
  }
  return zh || en || fallback || undefined;
}
