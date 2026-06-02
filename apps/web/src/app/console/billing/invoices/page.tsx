"use client";
/** /console/billing/invoices — bilingual billing statement console (Story 5.D.1). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BudgetAlertCard, InvoiceCard, SparklineKPI, StatusCard } from "@opticloud/ui";

import {
  type BillingBudgetStatusResponse,
  type BillingInvoiceListResponse,
  type BillingInvoiceResponse,
  type BillingUsageTrendWindow,
  type BillingUsageTrendsResponse,
  downloadBillingInvoicePdf,
  getBillingBudget,
  getBillingInvoice,
  getBillingUsageTrends,
  listBillingInvoices,
  OptiCloudClientError,
  putBillingBudget,
} from "@/lib/api";

type PageState = {
  list: BillingInvoiceListResponse | null;
  invoice: BillingInvoiceResponse | null;
  trends: BillingUsageTrendsResponse | null;
  budget: BillingBudgetStatusResponse | null;
  loading: boolean;
  trendsLoading: boolean;
  budgetLoading: boolean;
  budgetSaving: boolean;
  downloading: boolean;
  error: string | null;
  trendsError: string | null;
  budgetError: string | null;
  budgetMessage: string | null;
};

const initialState: PageState = {
  list: null,
  invoice: null,
  trends: null,
  budget: null,
  loading: false,
  trendsLoading: false,
  budgetLoading: false,
  budgetSaving: false,
  downloading: false,
  error: null,
  trendsError: null,
  budgetError: null,
  budgetMessage: null,
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

function toSparklineValues(window: BillingUsageTrendWindow): number[] {
  return window.points.map((point) => {
    const value = Number.parseFloat(point.actual_spend);
    return Number.isFinite(value) ? value : 0;
  });
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

function normalizeTrendError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 401) return "登录状态已失效，请重新登录。";
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function normalizeBudgetError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 409) return "预算已触发暂停，请提高或停用预算后继续。";
    if (err.status === 422) return "预算金额需要在 ¥1.00 到 ¥9999999.99 之间。";
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

export default function BillingInvoicesPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [budgetAmount, setBudgetAmount] = useState("");
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

  useEffect(() => {
    if (!jwt) return;
    let cancelled = false;
    setState((current) => ({ ...current, trendsLoading: true, trendsError: null }));

    void getBillingUsageTrends(jwt)
      .then((trends) => {
        if (cancelled) return;
        setState((current) => ({ ...current, trends, trendsLoading: false }));
      })
      .catch((err) => {
        if (cancelled) return;
        setState((current) => ({
          ...current,
          trendsLoading: false,
          trendsError: normalizeTrendError(err),
        }));
      });

    return () => {
      cancelled = true;
    };
  }, [jwt]);

  useEffect(() => {
    if (!jwt) return;
    let cancelled = false;
    setState((current) => ({
      ...current,
      budgetLoading: true,
      budgetError: null,
      budgetMessage: null,
    }));

    void getBillingBudget(jwt)
      .then((budget) => {
        if (cancelled) return;
        setBudgetAmount(budget.monthly_budget_amount ?? "");
        setState((current) => ({ ...current, budget, budgetLoading: false }));
      })
      .catch((err) => {
        if (cancelled) return;
        setState((current) => ({
          ...current,
          budgetLoading: false,
          budgetError: normalizeBudgetError(err),
        }));
      });

    return () => {
      cancelled = true;
    };
  }, [jwt]);

  const periods = useMemo(() => state.list?.items.map((item) => item.period) ?? [], [state.list]);
  const trendWindows = useMemo(() => state.trends?.windows ?? [], [state.trends]);

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

  const handleBudgetSave = async (): Promise<void> => {
    if (!jwt) return;
    setState((current) => ({
      ...current,
      budgetSaving: true,
      budgetError: null,
      budgetMessage: null,
    }));
    try {
      const budget = await putBillingBudget(jwt, {
        monthly_budget_amount: budgetAmount.trim(),
        enabled: true,
      });
      setBudgetAmount(budget.monthly_budget_amount ?? "");
      setState((current) => ({
        ...current,
        budget,
        budgetSaving: false,
        budgetMessage: budget.paused ? "预算已达到上限，新的扣费已暂停。" : "预算已更新。",
      }));
    } catch (err) {
      setState((current) => ({
        ...current,
        budgetSaving: false,
        budgetError: normalizeBudgetError(err),
      }));
    }
  };

  const handleBudgetDisable = async (): Promise<void> => {
    if (!jwt) return;
    setState((current) => ({
      ...current,
      budgetSaving: true,
      budgetError: null,
      budgetMessage: null,
    }));
    try {
      const budget = await putBillingBudget(jwt, { enabled: false });
      setBudgetAmount(budget.monthly_budget_amount ?? "");
      setState((current) => ({
        ...current,
        budget,
        budgetSaving: false,
        budgetMessage: "预算控制已停用。",
      }));
    } catch (err) {
      setState((current) => ({
        ...current,
        budgetSaving: false,
        budgetError: normalizeBudgetError(err),
      }));
    }
  };

  const invoice = state.invoice;
  const budget = state.budget;

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
            <Link href="/console/providers" className="text-muted-foreground hover:text-foreground">
              Providers
            </Link>
            <Link
              href="/console/audit-logs"
              className="text-muted-foreground hover:text-foreground"
            >
              审计日志
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

          <BudgetAlertCard
            budget={budget}
            amountValue={budgetAmount}
            onAmountChange={setBudgetAmount}
            onSave={handleBudgetSave}
            onDisable={handleBudgetDisable}
            isLoading={state.budgetLoading}
            isSaving={state.budgetSaving}
            message={state.budgetMessage}
            error={state.budgetError}
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

          <section className="space-y-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">用量趋势</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Credits actual usage spend
                </p>
              </div>
              <div className="text-sm text-muted-foreground">
                {state.trendsLoading ? "加载中..." : state.trends ? "已更新" : "等待数据"}
              </div>
            </div>

            {state.trendsError && (
              <div
                className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
                role="status"
                aria-label="billing.usage_trends.error"
              >
                用量趋势加载失败：{state.trendsError}
              </div>
            )}

            {!state.trendsError && trendWindows.length === 0 && !state.trendsLoading && (
              <div className="mt-4 text-sm text-muted-foreground">暂无趋势数据</div>
            )}

            {trendWindows.length > 0 && (
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {trendWindows.map((window) => (
                  <div
                    key={window.window_days}
                    className="min-w-0 rounded-md border border-border bg-background p-4"
                  >
                    <SparklineKPI
                      label={`${window.label.zh} / ${window.label.en}`}
                      ariaLabel={`billing.usage_trends.${window.window_days}d.actual_spend`}
                      values={toSparklineValues(window)}
                      unit="CNY"
                      width={160}
                      height={48}
                    />
                    <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <Metric label="累计" value={money(window.total_actual_spend)} />
                      <Metric label="日均" value={money(window.average_daily_spend)} />
                    </dl>
                  </div>
                ))}
              </div>
            )}
          </section>

          {invoice && (
            <>
              <InvoiceCard
                invoice={invoice}
                isDownloading={state.downloading}
                onDownloadPdf={handleDownload}
              />
            </>
          )}
        </section>
      </section>
    </main>
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
