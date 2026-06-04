"use client";
/** CapabilityCard (Tier 2, Story 8.C.5).
 *
 * Presentation-only capability card for benchmark-library entries. Parents own
 * API calls, routing, import payload rendering, auth, and persistence.
 */

import {
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  FileInput,
  Tag,
} from "lucide-react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface CapabilityCardDiscount {
  kind: string;
  label_zh: string;
  discount_multiplier: number;
  billing_supported: boolean;
}

export interface CapabilityCardCapability {
  benchmark_id: string;
  suite: string;
  domain: string;
  task_type: string;
  title_zh: string;
  title_en: string;
  source_name: string;
  source_url?: string | null;
  license_note_zh: string;
  import_kind: string;
  target_endpoint: string;
  discount: CapabilityCardDiscount;
  dataset_ref: string;
  sample_payload?: Record<string, unknown>;
}

export interface CapabilityCardProps {
  capability: CapabilityCardCapability;
  isImporting?: boolean;
  onImport?: (benchmarkId: string) => Promise<void> | void;
  className?: string;
  ariaLabel?: string;
}

const suiteLabels: Record<string, string> = {
  ieee: "IEEE",
  cvrplib: "CVRPLIB",
  "or-lib": "OR-Lib",
  m5: "M5",
  uci: "UCI",
  nab: "NAB",
};

function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

function discountPercent(multiplier: number): string {
  if (!Number.isFinite(multiplier)) return "折扣倍率未知";
  return `${Math.round(multiplier * 100)}% Credits`;
}

function importKindLabel(value: string): string {
  if (value === "optimization_request") return "优化 import 模板";
  if (value === "prediction_request") return "预测 import 模板";
  return value;
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 break-words text-sm text-foreground", mono && "font-mono text-xs")}>
        {value}
      </dd>
    </div>
  );
}

export function CapabilityCard({
  capability,
  isImporting = false,
  onImport,
  className,
  ariaLabel,
}: CapabilityCardProps): JSX.Element {
  const a11y = useA11y({
    ariaLabel: ariaLabel ?? `benchmark capability ${capability.benchmark_id}`,
    role: "region",
  });
  const titleId = `${a11y.id}-title`;
  const sourceUrl = safeHttpUrl(capability.source_url);
  const suiteLabel = suiteLabels[capability.suite] ?? capability.suite;
  const billingSupported = capability.discount.billing_supported;

  return (
    <article
      {...a11y.attrs}
      aria-labelledby={titleId}
      className={cn(
        "rounded-md border border-border bg-background p-5 text-foreground",
        "space-y-4",
        className,
      )}
      data-testid="capability-card"
      data-billing-supported={String(billingSupported)}
    >
      <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold">
              <Database className="h-3.5 w-3.5" aria-hidden="true" />
              {suiteLabel}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs">
              {capability.task_type}
            </span>
            <span className="rounded-md border border-border px-2 py-1 text-xs">
              {capability.domain}
            </span>
          </div>
          <h3 id={titleId} className="mt-3 break-words text-lg font-semibold">
            {capability.title_zh}
          </h3>
          <p className="mt-1 break-words text-sm text-muted-foreground">
            {capability.title_en}
          </p>
        </div>

        {onImport && (
          <button
            type="button"
            onClick={() => void onImport(capability.benchmark_id)}
            disabled={isImporting}
            className="inline-flex min-h-touch w-fit items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            data-testid="capability-import"
          >
            <FileInput className="h-4 w-4" aria-hidden="true" />
            {isImporting ? "生成中" : "一键 import"}
          </button>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold",
            billingSupported
              ? "border-success/30 bg-success/10 text-success"
              : "border-warning/30 bg-warning/10 text-warning",
          )}
          data-testid="capability-discount"
        >
          {billingSupported ? (
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {capability.discount.label_zh}
          {" · "}
          {discountPercent(capability.discount.discount_multiplier)}
        </span>
        <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
          <Tag className="h-3.5 w-3.5" aria-hidden="true" />
          {importKindLabel(capability.import_kind)}
        </span>
      </div>

      {!billingSupported && (
        <p className="text-sm text-warning" data-testid="capability-billing-warning">
          可生成预测 import 模板；预测计费折扣未在当前能力中落地。
        </p>
      )}

      <dl className="grid gap-3 border-t border-border pt-4 md:grid-cols-2">
        <Field label="Benchmark ID" value={capability.benchmark_id} mono />
        <Field label="Dataset Ref" value={capability.dataset_ref} mono />
        <Field label="Target Endpoint" value={capability.target_endpoint} mono />
        <Field
          label="Discount Kind"
          value={`${capability.discount.kind} · multiplier=${capability.discount.discount_multiplier}`}
          mono
        />
        <Field
          label="Source"
          value={
            sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex max-w-full items-center gap-1 break-words text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                <span className="min-w-0 break-words">{capability.source_name}</span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              </a>
            ) : (
              capability.source_name
            )
          }
        />
        <Field label="License Note" value={capability.license_note_zh} />
      </dl>
    </article>
  );
}
