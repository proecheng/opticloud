"use client";
/** VoucherCard (Tier 3, Story 6.B.5).
 *
 * Presentation-only card for reproducibility vouchers. Parents own API calls,
 * API keys, routing, and persistence. This component only renders the public
 * voucher contract and fires callbacks.
 */

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  GitBranch,
  Lock,
  Play,
  RotateCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type VoucherStatus = "issued" | "expired" | "revoked" | "rerun_child";

export interface VoucherCardModelVersion {
  provider_id: string;
  name: string;
  version: string;
}

export interface VoucherCardVoucher {
  voucherId: string;
  status: VoucherStatus;
  createdAt: string;
  expiresAt?: string;
  lockedSolver: string;
  lockedModelVersion: VoucherCardModelVersion;
  requestFingerprint: string;
  seedLocked: boolean;
  seed: number | null;
  anonymous?: true;
  rerunOfVoucherId?: string;
  sourceOptimizationId?: string;
  childVoucherId?: string;
}

export interface VoucherCardProps {
  voucher: VoucherCardVoucher;
  canRerun?: boolean;
  isRerunning?: boolean;
  rerunError?: string;
  rerunResult?: {
    childVoucherId: string;
    rerunOfVoucherId: string;
    sourceOptimizationId: string;
  };
  onRerun?: (voucherId: string) => Promise<void> | void;
  onCopyVoucherId?: (voucherId: string) => Promise<void> | void;
  onViewDetails?: (voucherId: string) => void;
  className?: string;
  ariaLabel?: string;
}

const statusMeta: Record<
  VoucherStatus,
  {
    label: string;
    description: string;
    className: string;
    icon: LucideIcon;
  }
> = {
  issued: {
    label: "Issued / 可复现",
    description: "Voucher is active for rerun requests.",
    className: "border-success bg-success/5 text-success",
    icon: CheckCircle2,
  },
  expired: {
    label: "Expired / 已过期",
    description: "Voucher is outside its rerun window.",
    className: "border-warning bg-warning/10 text-warning",
    icon: Clock,
  },
  revoked: {
    label: "Revoked / 已撤销",
    description: "Voucher cannot be rerun.",
    className: "border-danger bg-danger/10 text-danger",
    icon: XCircle,
  },
  rerun_child: {
    label: "Rerun child / 重跑子凭证",
    description: "Voucher was produced by a rerun.",
    className: "border-primary bg-primary/5 text-primary",
    icon: GitBranch,
  },
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function shortFingerprint(value: string): string {
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}...${value.slice(-6)}`;
}

function KeyValue({
  label,
  value,
  mono = false,
  testId,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  testId?: string;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "mt-1 break-words text-sm font-medium text-foreground",
          mono && "font-mono text-xs",
        )}
        data-testid={testId}
      >
        {value}
      </dd>
    </div>
  );
}

export function VoucherCard({
  voucher,
  canRerun = false,
  isRerunning = false,
  rerunError,
  rerunResult,
  onRerun,
  onCopyVoucherId,
  onViewDetails,
  className,
  ariaLabel,
}: VoucherCardProps): JSX.Element {
  const meta = statusMeta[voucher.status];
  const StatusIcon = meta.icon;
  const clipboardSupported =
    typeof navigator !== "undefined" &&
    typeof navigator.clipboard?.writeText === "function";
  const rerunnableStatus = voucher.status === "issued";
  const rerunDisabled = !canRerun || !rerunnableStatus || isRerunning;
  const titleId = `voucher-card-${voucher.voucherId}`;
  const a11y = useA11y({
    ariaLabel: ariaLabel ?? `Reproducibility voucher ${voucher.voucherId}`,
    role: "region",
  });

  const handleCopyVoucherId = async (): Promise<void> => {
    try {
      if (onCopyVoucherId) {
        await onCopyVoucherId(voucher.voucherId);
        return;
      }
      if (clipboardSupported) {
        await navigator.clipboard.writeText(voucher.voucherId);
      }
    } catch {
      // Clipboard or parent callback failures should not break the card.
    }
  };

  return (
    <article
      {...a11y.attrs}
      aria-labelledby={titleId}
      className={cn(
        "rounded-md border border-border bg-background p-4 shadow-sm",
        "space-y-4 text-foreground",
        className,
      )}
      data-testid="voucher-card"
      data-voucher-status={voucher.status}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold",
                meta.className,
              )}
              data-testid="voucher-status"
              title={meta.description}
            >
              <StatusIcon className="h-3.5 w-3.5" aria-hidden="true" />
              {meta.label}
            </span>
            {voucher.anonymous === true && (
              <span
                className="inline-flex items-center gap-1 rounded-md border border-primary bg-primary/5 px-2 py-1 text-xs font-semibold text-primary"
                data-testid="voucher-anonymous"
              >
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Anonymous / 盲审匿名
              </span>
            )}
          </div>
          <h3 id={titleId} className="break-all font-mono text-base font-semibold">
            {voucher.voucherId}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            5-year rerun evidence is based on voucher creation time.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleCopyVoucherId()}
            disabled={!onCopyVoucherId && !clipboardSupported}
            className="inline-flex min-h-touch min-w-touch items-center justify-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
            aria-label={`Copy voucher ${voucher.voucherId}`}
            data-testid="voucher-copy"
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
            Copy
          </button>
          {onViewDetails && (
            <button
              type="button"
              onClick={() => onViewDetails(voucher.voucherId)}
              className="inline-flex min-h-touch items-center justify-center rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
              aria-label={`View voucher ${voucher.voucherId} details`}
              data-testid="voucher-details"
            >
              Details
            </button>
          )}
        </div>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <KeyValue label="Created" value={formatDateTime(voucher.createdAt)} testId="voucher-created" />
        <KeyValue
          label="Expires"
          value={voucher.expiresAt ? formatDateTime(voucher.expiresAt) : "Creation date + 5 years"}
          testId="voucher-expires"
        />
        <KeyValue label="Locked solver" value={voucher.lockedSolver} testId="voucher-solver" />
        <KeyValue
          label="Model version"
          value={`${voucher.lockedModelVersion.provider_id}/${voucher.lockedModelVersion.name}@${voucher.lockedModelVersion.version}`}
          mono
          testId="voucher-model"
        />
        <KeyValue
          label="Request fingerprint"
          value={shortFingerprint(voucher.requestFingerprint)}
          mono
          testId="voucher-fingerprint"
        />
        <KeyValue
          label="Seed lock"
          value={
            <span className="inline-flex items-center gap-1">
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              {voucher.seedLocked ? `Locked (${voucher.seed ?? "null"})` : "Not locked"}
            </span>
          }
          testId="voucher-seed"
        />
      </dl>

      {(voucher.rerunOfVoucherId || voucher.sourceOptimizationId || voucher.childVoucherId) && (
        <div
          className="rounded-md border border-border bg-muted/40 p-3"
          data-testid="voucher-lineage"
        >
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <GitBranch className="h-4 w-4" aria-hidden="true" />
            Rerun lineage
          </div>
          <dl className="grid gap-2 sm:grid-cols-3">
            {voucher.rerunOfVoucherId && (
              <KeyValue
                label="Parent voucher"
                value={voucher.rerunOfVoucherId}
                mono
                testId="voucher-parent"
              />
            )}
            {voucher.sourceOptimizationId && (
              <KeyValue
                label="Source optimization"
                value={voucher.sourceOptimizationId}
                mono
                testId="voucher-source-optimization"
              />
            )}
            {voucher.childVoucherId && (
              <KeyValue
                label="Child voucher"
                value={voucher.childVoucherId}
                mono
                testId="voucher-child"
              />
            )}
          </dl>
        </div>
      )}

      <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div
          className="min-h-[1.5rem] text-sm"
          aria-live="polite"
          aria-atomic="true"
          data-testid="voucher-rerun-status"
        >
          {isRerunning && (
            <span className="inline-flex items-center gap-2 text-primary">
              <RotateCw className="h-4 w-4 animate-spin" aria-hidden="true" />
              Rerun request in progress...
            </span>
          )}
          {!isRerunning && rerunError && (
            <span className="inline-flex items-center gap-2 text-danger">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              {rerunError}
            </span>
          )}
          {!isRerunning && !rerunError && rerunResult && (
            <div className="flex flex-wrap items-center gap-2 text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              <span>
                Child voucher issued:{" "}
                <span className="font-mono" data-testid="voucher-rerun-child-result">
                  {rerunResult.childVoucherId}
                </span>
              </span>
              <span className="font-mono text-xs" data-testid="voucher-rerun-parent-result">
                rerun_of={rerunResult.rerunOfVoucherId}
              </span>
              <span className="font-mono text-xs" data-testid="voucher-rerun-source-result">
                source={rerunResult.sourceOptimizationId}
              </span>
            </div>
          )}
          {!isRerunning && !rerunError && !rerunResult && !rerunnableStatus && (
            <span className="text-muted-foreground">This voucher cannot be rerun.</span>
          )}
        </div>

        <button
          type="button"
          onClick={() => void onRerun?.(voucher.voucherId)}
          disabled={rerunDisabled}
          className={cn(
            "inline-flex min-h-touch items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold",
            rerunDisabled
              ? "cursor-not-allowed bg-muted text-muted-foreground"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
          aria-label={`Rerun voucher ${voucher.voucherId}`}
          data-testid="voucher-rerun"
        >
          {isRerunning ? (
            <RotateCw className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Play className="h-4 w-4" aria-hidden="true" />
          )}
          Rerun
        </button>
      </div>
    </article>
  );
}
