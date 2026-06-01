"use client";
/** InvoiceCard (Tier 2, Story 5.D.7).
 *
 * Presentation-only billing statement card. Parents own API calls, auth, PDF
 * download object URLs, routing, and persistence.
 */

import { Download } from "lucide-react";
import type { ReactNode } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface InvoiceCardBilingualText {
  zh: string;
  en: string;
}

export interface InvoiceCardSubscription {
  plan_code: string;
  plan_label: string;
  plan_label_zh: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
}

export interface InvoiceCardUsageSummary {
  window_days: 7 | 30;
  actual_spend: string;
  currency: string;
  label: InvoiceCardBilingualText;
}

export interface InvoiceCardLineItem {
  id: string;
  created_at: string;
  kind: string;
  bucket: string;
  label: InvoiceCardBilingualText;
  direction: "credit" | "debit";
  direction_label: InvoiceCardBilingualText;
  amount: string;
  source_amount: string;
  currency: string;
  details?: Record<string, string>;
}

export interface InvoiceCardInvoice {
  period: string;
  period_start: string;
  period_end: string;
  status: "final" | "provisional";
  status_label: InvoiceCardBilingualText;
  net_credit_movement: string;
  actual_spend: string;
  currency: string;
  line_item_count: number;
  title: InvoiceCardBilingualText;
  tax_disclaimer: InvoiceCardBilingualText;
  owner_user_id_suffix: string;
  subscription: InvoiceCardSubscription;
  credit_subtotal: string;
  debit_subtotal: string;
  trend_contract: "invoice_summary";
  usage_summary: InvoiceCardUsageSummary[];
  line_items: InvoiceCardLineItem[];
}

export interface InvoiceCardProps {
  invoice: InvoiceCardInvoice;
  isDownloading?: boolean;
  onDownloadPdf?: () => Promise<void> | void;
  className?: string;
  ariaLabel?: string;
}

export function InvoiceCard({
  invoice,
  isDownloading = false,
  onDownloadPdf,
  className,
  ariaLabel = "billing.invoice_card",
}: InvoiceCardProps): JSX.Element {
  const a11y = useA11y({ ariaLabel, role: "region" });
  return (
    <article
      {...a11y.attrs}
      ref={a11y.ref}
      className={cn("rounded-md border border-border bg-background text-foreground", className)}
      data-testid="invoice-card"
    >
      <header className="flex flex-col gap-3 border-b border-border p-5 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-md border border-primary bg-primary/5 px-2 py-1 text-xs font-semibold text-primary"
              data-testid="invoice-status"
            >
              {invoice.status_label.zh} / {invoice.status_label.en}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{invoice.period}</span>
          </div>
          <h2 className="mt-3 break-words text-xl font-semibold">{invoice.title.zh}</h2>
          <p className="mt-1 break-words text-sm text-muted-foreground">{invoice.title.en}</p>
          <p className="mt-2 break-words text-sm font-medium text-warning">
            {invoice.tax_disclaimer.zh} / {invoice.tax_disclaimer.en}
          </p>
        </div>
        {onDownloadPdf && (
          <button
            type="button"
            disabled={isDownloading}
            onClick={() => void onDownloadPdf()}
            className="inline-flex min-h-touch w-fit items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="下载 PDF"
            data-testid="invoice-download"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {isDownloading ? "下载中..." : "下载 PDF"}
          </button>
        )}
      </header>

      <div className="space-y-5 p-5">
        <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="净 Credits 变动" value={money(invoice.net_credit_movement)} />
          <Metric label="实际用量支出" value={money(invoice.actual_spend)} />
          <Metric label="收入小计" value={money(invoice.credit_subtotal)} />
          <Metric label="支出小计" value={money(invoice.debit_subtotal)} />
        </dl>

        <dl className="grid gap-3 border-t border-border pt-4 text-sm md:grid-cols-2">
          <Field
            label="账期"
            value={`${formatDate(invoice.period_start)} - ${formatDate(invoice.period_end)}`}
          />
          <Field label="用户后缀" value={invoice.owner_user_id_suffix || "-"} mono />
          <Field
            label="计划"
            value={`${invoice.subscription.plan_label_zh} / ${invoice.subscription.plan_label}`}
          />
          <Field
            label="计划周期"
            value={`${formatDate(invoice.subscription.current_period_start)} - ${formatDate(
              invoice.subscription.current_period_end,
            )}`}
          />
        </dl>

        {invoice.usage_summary.length > 0 && (
          <section className="border-t border-border pt-4" aria-label="账单用量摘要">
            <h3 className="text-base font-semibold">用量摘要</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {invoice.usage_summary.map((summary) => (
                <div
                  key={summary.window_days}
                  className="min-w-0 border-l-2 border-primary/40 pl-3"
                >
                  <div className="break-words text-sm font-medium">
                    {summary.label.zh} / {summary.label.en}
                  </div>
                  <div className="mt-2 break-words text-2xl font-semibold">
                    {money(summary.actual_spend)}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <section aria-label="账单明细">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold">账单明细</h3>
            <span className="text-xs text-muted-foreground">
              {invoice.line_items.length} / {invoice.line_item_count} rows
            </span>
          </div>
          {invoice.line_items.length === 0 ? (
            <div
              className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground"
              data-testid="invoice-empty-line-items"
            >
              当前账期暂无明细。
            </div>
          ) : (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="min-w-full text-left text-sm" data-testid="invoice-line-items">
                <thead className="bg-muted text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">日期</th>
                    <th className="px-4 py-3 font-medium">项目</th>
                    <th className="px-4 py-3 font-medium">方向</th>
                    <th className="px-4 py-3 text-right font-medium">金额</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.line_items.map((item) => (
                    <tr key={item.id} className="border-t border-border">
                      <td className="whitespace-nowrap px-4 py-3">{formatDate(item.created_at)}</td>
                      <td className="min-w-[220px] max-w-[34rem] px-4 py-3">
                        <div className="break-words font-medium">
                          {item.label.zh} / {item.label.en}
                        </div>
                        <div className="mt-1 break-words text-xs text-muted-foreground">
                          {item.kind}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        {item.direction_label.zh} / {item.direction_label.en}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-mono">
                        {money(item.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </article>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(date);
}

function money(value: string | null | undefined): string {
  const amount = value ?? "0.00";
  return amount.startsWith("-") ? `-¥${amount.slice(1)}` : `¥${amount}`;
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 break-words font-medium", mono && "font-mono text-xs")}>
        {value}
      </dd>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-xl font-semibold">{value}</dd>
    </div>
  );
}
