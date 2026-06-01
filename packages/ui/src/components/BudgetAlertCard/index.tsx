"use client";
/** BudgetAlertCard (Tier 2, Story 5.D.7).
 *
 * Presentation-only monthly budget card. Parents own API calls, auth,
 * persistence, and error normalization.
 */

import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  CircleDollarSign,
  PauseCircle,
  Save,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type BudgetAlertStatus = "not_configured" | "disabled" | "active" | "paused";
export type BudgetAlertChannel = "email" | "webhook" | "in_app";
export type BudgetAlertEventType =
  | "billing.budget.configured"
  | "billing.budget.disabled"
  | "billing.budget.alerted"
  | "billing.budget.paused";
type BudgetAlertVisualStatus = BudgetAlertStatus | "warning";

export interface BudgetAlertEventSummary {
  id: string;
  event_type: BudgetAlertEventType;
  period_start: string;
  period_end: string;
  occurred_at: string;
  budget_amount: string;
  actual_spend: string;
  percent_used: string;
  channels: BudgetAlertChannel[];
}

export interface BudgetAlertBudget {
  budget_control_id: string | null;
  enabled: boolean;
  status: BudgetAlertStatus;
  monthly_budget_amount: string | null;
  alert_threshold_ratio: string;
  period_start: string;
  period_end: string;
  actual_spend: string;
  percent_used: string;
  currency: "CNY";
  alert_threshold_reached: boolean;
  paused: boolean;
  paused_at: string | null;
  pause_period_start: string | null;
  recent_events: BudgetAlertEventSummary[];
}

export interface BudgetAlertCardProps {
  budget: BudgetAlertBudget | null;
  amountValue: string;
  onAmountChange: (value: string) => void;
  onSave: () => Promise<void> | void;
  onDisable: () => Promise<void> | void;
  isLoading?: boolean;
  isSaving?: boolean;
  message?: string | null;
  error?: string | null;
  className?: string;
  ariaLabel?: string;
}

interface StatusMeta {
  label: string;
  description: string;
  className: string;
  icon: LucideIcon;
}

const statusMeta: Record<BudgetAlertVisualStatus, StatusMeta> = {
  not_configured: {
    label: "未设置",
    description: "还没有启用月度预算。",
    className: "border-border bg-muted text-muted-foreground",
    icon: CircleDollarSign,
  },
  disabled: {
    label: "未启用",
    description: "预算控制已停用。",
    className: "border-border bg-muted text-muted-foreground",
    icon: XCircle,
  },
  active: {
    label: "启用中",
    description: "预算控制正在生效。",
    className: "border-success bg-success/10 text-success",
    icon: CheckCircle2,
  },
  warning: {
    label: "接近上限",
    description: "本月支出已达到提醒阈值。",
    className: "border-warning bg-warning/10 text-warning",
    icon: AlertTriangle,
  },
  paused: {
    label: "已暂停",
    description: "本月预算已触达上限，新的扣费已暂停。",
    className: "border-danger bg-danger/10 text-danger",
    icon: PauseCircle,
  },
};

export function BudgetAlertCard({
  budget,
  amountValue,
  onAmountChange,
  onSave,
  onDisable,
  isLoading = false,
  isSaving = false,
  message,
  error,
  className,
  ariaLabel = "billing.budget_alert_card",
}: BudgetAlertCardProps): JSX.Element {
  const a11y = useA11y({ ariaLabel, role: "region" });
  const visualStatus = visualStatusFor(budget);
  const meta = statusMeta[visualStatus];
  const StatusIcon = meta.icon;
  const saveDisabled = isSaving || amountValue.trim().length === 0;
  const disableDisabled = isSaving || !budget?.budget_control_id;

  return (
    <section
      {...a11y.attrs}
      ref={a11y.ref}
      className={cn("rounded-md border border-border bg-background p-4 text-foreground", className)}
      data-testid="budget-alert-card"
      data-budget-status={visualStatus}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm text-muted-foreground">月度预算</div>
          <div className="mt-1 break-words text-xl font-semibold">
            {budget?.monthly_budget_amount ? money(budget.monthly_budget_amount) : "未设置"}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            当前账期 {formatDate(budget?.period_start)} - {formatDate(budget?.period_end)}
          </p>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold",
            meta.className,
          )}
          data-testid="budget-status"
          title={meta.description}
        >
          <StatusIcon className="h-3.5 w-3.5" aria-hidden="true" />
          {meta.label}
        </span>
      </header>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Metric label="本月支出" value={money(budget?.actual_spend)} />
        <Metric label="使用比例" value={formatPercent(budget?.percent_used)} />
        <Metric label="提醒阈值" value={formatRatioPercent(budget?.alert_threshold_ratio)} />
        <Metric label="暂停时间" value={formatDateTime(budget?.paused_at)} />
      </dl>

      <div className="mt-4 flex flex-col gap-2">
        <label className="text-sm font-medium" htmlFor={`${a11y.id}-amount`}>
          预算金额
        </label>
        <div className="flex gap-2">
          <input
            id={`${a11y.id}-amount`}
            aria-label="预算金额"
            inputMode="decimal"
            value={amountValue}
            onChange={(event) => onAmountChange(event.target.value)}
            placeholder="100.00"
            disabled={isSaving}
            className="min-h-touch min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={saveDisabled}
            onClick={() => void onSave()}
            className="inline-flex min-h-touch items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="budget-save"
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            保存
          </button>
        </div>
        <button
          type="button"
          disabled={disableDisabled}
          onClick={() => void onDisable()}
          className="min-h-touch rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="budget-disable"
        >
          停用预算
        </button>
      </div>

      <div
        className="mt-3 min-h-[1.25rem] text-sm"
        aria-live="polite"
        aria-atomic="true"
        data-testid="budget-card-message"
      >
        {isLoading && (
          <span className="inline-flex items-center gap-2 text-muted-foreground">
            <Bell className="h-4 w-4" aria-hidden="true" />
            预算加载中...
          </span>
        )}
        {!isLoading && message && (
          <span className="inline-flex items-center gap-2 text-success" role="status">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {message}
          </span>
        )}
        {!isLoading && !message && error && (
          <span className="inline-flex items-center gap-2 text-danger" role="status">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            预算加载失败：{error}
          </span>
        )}
      </div>

      {budget?.recent_events && budget.recent_events.length > 0 && (
        <section className="mt-4 border-t border-border pt-3" aria-label="预算最近事件">
          <div className="text-sm font-medium">最近事件</div>
          <ul className="mt-2 space-y-2 text-xs text-muted-foreground">
            {budget.recent_events.slice(0, 3).map((event) => (
              <li key={event.id} className="min-w-0 break-words">
                <span className="font-medium text-foreground">{eventLabel(event.event_type)}</span>
                {" · "}
                {money(event.actual_spend)}
                {" · "}
                {formatPercent(event.percent_used)}
                {event.channels.length > 0 && (
                  <>
                    {" · "}
                    {event.channels.map(channelLabel).join(", ")}
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}

function money(value: string | null | undefined): string {
  const amount = value ?? "0.00";
  return amount.startsWith("-") ? `-¥${amount.slice(1)}` : `¥${amount}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatPercent(value: string | null | undefined): string {
  const numeric = Number.parseFloat(value ?? "0");
  if (!Number.isFinite(numeric)) return "0%";
  const percent = Math.round(numeric * 100);
  if (percent > 9999) return "9999%+";
  if (percent < -9999) return "-9999%";
  return `${percent}%`;
}

function formatRatioPercent(value: string | null | undefined): string {
  return formatPercent(value);
}

function visualStatusFor(budget: BudgetAlertBudget | null): BudgetAlertVisualStatus {
  if (!budget) return "not_configured";
  if (budget.status === "paused" || budget.paused) return "paused";
  if (budget.status === "active" && budget.alert_threshold_reached) return "warning";
  return budget.status;
}

function eventLabel(value: BudgetAlertEventType): string {
  return {
    "billing.budget.configured": "已配置",
    "billing.budget.disabled": "已停用",
    "billing.budget.alerted": "已提醒",
    "billing.budget.paused": "已暂停",
  }[value];
}

function channelLabel(value: BudgetAlertChannel): string {
  return {
    email: "email",
    webhook: "webhook",
    in_app: "站内",
  }[value];
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-lg font-semibold">{value}</dd>
    </div>
  );
}
