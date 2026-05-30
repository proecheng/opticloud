"use client";
/** /console/billing/invoices — bilingual billing statement console (Story 5.D.1). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusCard } from "@opticloud/ui";

import {
  type BillingInvoiceListResponse,
  type BillingInvoiceResponse,
  downloadBillingInvoicePdf,
  getBillingInvoice,
  listBillingInvoices,
  OptiCloudClientError,
} from "@/lib/api";

type PageState = {
  list: BillingInvoiceListResponse | null;
  invoice: BillingInvoiceResponse | null;
  loading: boolean;
  downloading: boolean;
  error: string | null;
};

const initialState: PageState = {
  list: null,
  invoice: null,
  loading: false,
  downloading: false,
  error: null,
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-CN", {
    dateStyle: "medium",
  });
}

function money(value: string | null | undefined): string {
  const amount = value ?? "0.00";
  return amount.startsWith("-") ? `-¥${amount.slice(1)}` : `¥${amount}`;
}

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 404) return "该月份账单不可用。";
    if (err.status === 400) return "账单月份格式无效。";
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function saveBlob(download: { blob: Blob; filename: string }): void {
  const href = URL.createObjectURL(download.blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = download.filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(href);
  }
}

export default function BillingInvoicesPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [state, setState] = useState<PageState>(initialState);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const loadInvoice = useCallback(
    async (token: string, period: string): Promise<void> => {
      if (!period) return;
      setState((current) => ({ ...current, invoice: null, loading: true, error: null }));
      try {
        const invoice = await getBillingInvoice(token, period);
        setState((current) => ({ ...current, invoice, loading: false }));
      } catch (err) {
        setState((current) => ({
          ...current,
          loading: false,
          error: normalizeError(err),
        }));
      }
    },
    [],
  );

  useEffect(() => {
    if (!jwt) return;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));

    void listBillingInvoices(jwt)
      .then(async (list) => {
        if (cancelled) return;
        const firstPeriod = list.items[0]?.period ?? "";
        setSelectedPeriod((current) => current || firstPeriod);
        setState((current) => ({ ...current, list, loading: false }));
        if (firstPeriod) await loadInvoice(jwt, firstPeriod);
      })
      .catch((err) => {
        if (cancelled) return;
        setState((current) => ({ ...current, loading: false, error: normalizeError(err) }));
      });

    return () => {
      cancelled = true;
    };
  }, [jwt, loadInvoice]);

  const periods = useMemo(() => state.list?.items.map((item) => item.period) ?? [], [state.list]);

  const handlePeriodChange = (period: string): void => {
    setSelectedPeriod(period);
    if (jwt) void loadInvoice(jwt, period);
  };

  const handleDownload = async (): Promise<void> => {
    if (!jwt || !state.invoice) return;
    setState((current) => ({ ...current, downloading: true, error: null }));
    try {
      const download = await downloadBillingInvoicePdf(jwt, state.invoice.period);
      saveBlob(download);
      setState((current) => ({ ...current, downloading: false }));
    } catch (err) {
      setState((current) => ({
        ...current,
        downloading: false,
        error: normalizeError(err),
      }));
    }
  };

  const invoice = state.invoice;

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/console/excel" className="text-muted-foreground hover:text-foreground">
              Excel
            </Link>
            <Link
              href="/console/data-exports"
              className="text-muted-foreground hover:text-foreground"
            >
              数据导出
            </Link>
            <Link
              href="/console/billing/invoices"
              className="font-medium text-foreground hover:text-primary"
            >
              账单
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">双语账单</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              查看月度 Credits 变动、实际用量支出和双语 PDF billing statement。
            </p>
          </div>
          <div className="min-w-[180px]">
            <label className="block text-sm font-medium" htmlFor="invoice-period">
              账单月份
            </label>
            <select
              id="invoice-period"
              aria-label="账单月份"
              value={selectedPeriod}
              onChange={(event) => handlePeriodChange(event.target.value)}
              className="mt-2 min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {periods.length === 0 ? (
                <option value="">暂无账单</option>
              ) : (
                periods.map((period) => (
                  <option key={period} value={period}>
                    {period}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <StatusCard
            variant="info"
            title="账单性质"
            description="该文件是 OptiCloud billing statement，不是税务发票或发票报销凭证。"
            ariaLabel="billing.invoice.scope"
          />

          <div className="rounded-md border border-border bg-background p-4">
            <div className="text-sm text-muted-foreground">当前月份</div>
            <div className="mt-1 text-xl font-semibold">{invoice?.period ?? "-"}</div>
            <dl className="mt-4 space-y-3 text-sm">
              <Field label="状态" value={invoice?.status_label.zh ?? "-"} />
              <Field label="用户后缀" value={invoice?.owner_user_id_suffix ?? "-"} mono />
              <Field
                label="计划"
                value={
                  invoice
                    ? `${invoice.subscription.plan_label_zh} / ${invoice.subscription.plan_label}`
                    : "-"
                }
              />
              <Field
                label="账期"
                value={
                  invoice
                    ? `${formatDate(invoice.period_start)} - ${formatDate(invoice.period_end)}`
                    : "-"
                }
              />
            </dl>
          </div>
        </aside>

        <section className="space-y-5">
          {state.error && (
            <StatusCard
              variant="error"
              title="账单加载失败"
              description={state.error}
              ariaLabel="billing.invoice.error"
            />
          )}

          {!invoice && !state.loading && !state.error && (
            <StatusCard
              variant="info"
              title="暂无账单"
              description="当前账号还没有可查看的账单月份。"
              ariaLabel="billing.invoice.empty"
            />
          )}

          {invoice && (
            <>
              <div className="rounded-md border border-border bg-background p-5">
                <div className="flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">{invoice.title.zh}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{invoice.title.en}</p>
                    <p className="mt-2 text-sm font-medium text-warning">
                      {invoice.tax_disclaimer.zh} / {invoice.tax_disclaimer.en}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={state.downloading}
                    onClick={() => void handleDownload()}
                    className="min-h-touch w-fit rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {state.downloading ? "下载中..." : "下载 PDF"}
                  </button>
                </div>

                <dl className="mt-5 grid gap-4 text-sm md:grid-cols-4">
                  <Metric label="净 Credits 变动" value={money(invoice.net_credit_movement)} />
                  <Metric label="实际用量支出" value={money(invoice.actual_spend)} />
                  <Metric label="收入小计" value={money(invoice.credit_subtotal)} />
                  <Metric label="支出小计" value={money(invoice.debit_subtotal)} />
                </dl>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {invoice.usage_summary.map((summary) => (
                  <div
                    key={summary.window_days}
                    className="rounded-md border border-border bg-background p-4"
                  >
                    <div className="text-sm font-medium">
                      {summary.label.zh} / {summary.label.en}
                    </div>
                    <div className="mt-2 text-2xl font-semibold">{money(summary.actual_spend)}</div>
                  </div>
                ))}
              </div>

              <div className="overflow-hidden rounded-md border border-border bg-background">
                <div className="border-b border-border px-4 py-3">
                  <h3 className="font-semibold">账单明细</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
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
                          <td className="whitespace-nowrap px-4 py-3">
                            {formatDate(item.created_at)}
                          </td>
                          <td className="min-w-[220px] px-4 py-3">
                            <div className="font-medium">
                              {item.label.zh} / {item.label.en}
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">{item.kind}</div>
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
              </div>
            </>
          )}
        </section>
      </section>
    </main>
  );
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
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={["mt-1 break-words font-medium", mono ? "font-mono text-xs" : ""].join(" ")}>
        {value}
      </dd>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-xl font-semibold">{value}</dd>
    </div>
  );
}
