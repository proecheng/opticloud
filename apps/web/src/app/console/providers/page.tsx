"use client";
/** /console/providers — Provider Marketplace v2 read-only aggregate surface (Story 7.B.9). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import {
  getProviderKpiDashboard,
  getProviderRevenuePayoutDashboard,
  getProviderRouteShareDashboard,
  listProviderApplications,
  listProviderMonthlyRevenueShareBatches,
  listProviderVersionUpdates,
  OptiCloudClientError,
  type ProviderApplicationResponse,
  type ProviderKpiDashboardResponse,
  type ProviderMonthlyRevenueShareBatchResponse,
  type ProviderRevenuePayoutDashboardResponse,
  type ProviderRouteShareDashboardResponse,
  type ProviderVersionUpdateResponse,
} from "@/lib/api";

type SectionKey = "applications" | "route" | "kpi" | "revenue" | "versions" | "monthly";

interface ProviderConsoleData {
  applications: ProviderApplicationResponse[];
  route: ProviderRouteShareDashboardResponse | null;
  kpi: ProviderKpiDashboardResponse | null;
  revenue: ProviderRevenuePayoutDashboardResponse | null;
  versions: ProviderVersionUpdateResponse[];
  monthly: ProviderMonthlyRevenueShareBatchResponse[];
}

type ProviderConsoleErrors = Partial<Record<SectionKey, string>>;

const emptyData: ProviderConsoleData = {
  applications: [],
  route: null,
  kpi: null,
  revenue: null,
  versions: [],
  monthly: [],
};

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 404) return "该 Provider Console 数据不可用。";
    if (err.status === 409) return "后端检测到存储漂移，已拒绝返回不可信数据。";
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function fieldValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function countMapText(values: object): string {
  return Object.entries(values)
    .map(([key, value]) => `${key}:${value}`)
    .join(" · ");
}

function firstCurrencyTotal(
  totals:
    | ProviderRevenuePayoutDashboardResponse["currency_totals"]
    | ProviderMonthlyRevenueShareBatchResponse["currency_totals"],
): string {
  const first = totals[0];
  if (!first) return "0.0000";
  return `${first.provider_revenue_amount} ${first.currency}`;
}

function DataError({
  title,
  error,
}: {
  title: string;
  error: string | undefined;
}): JSX.Element | null {
  if (!error) return null;
  return (
    <StatusCard
      variant="error"
      title={title}
      description={error}
      ariaLabel={`provider-console.error.${title}`}
    />
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-border bg-background p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-lg font-semibold">{value}</dd>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="space-y-3 rounded-md border border-border bg-background p-4">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function SafeTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: string[][];
}): JSX.Element {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[560px] text-sm">
        <thead className="bg-muted">
          <tr>
            {headers.map((header) => (
              <th key={header} className="px-3 py-2 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={row.join("|") || rowIndex} className="border-t border-border">
              {row.map((cell, cellIndex) => (
                <td key={`${rowIndex}-${cellIndex}`} className="px-3 py-2 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ProviderConsolePage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [providerId, setProviderId] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const [periodMonth, setPeriodMonth] = useState("");
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [data, setData] = useState<ProviderConsoleData>(emptyData);
  const [errors, setErrors] = useState<ProviderConsoleErrors>({});

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const selectedApplication = useMemo(() => {
    if (applicationId.trim()) {
      return data.applications.find((item) => item.application_id === applicationId.trim()) ?? null;
    }
    return data.applications[0] ?? null;
  }, [applicationId, data.applications]);

  const loadProviderConsole = async (): Promise<void> => {
    if (!jwt) return;
    const provider = providerId.trim();
    const tenant = tenantId.trim() || undefined;
    const period = periodMonth.trim() || undefined;
    if (!provider) {
      setFormError("请输入 Provider ID。");
      return;
    }

    setFormError(null);
    setLoading(true);
    setErrors({});
    const baseFilters = { tenantId: tenant };

    const [applicationsResult, routeResult, kpiResult, revenueResult, monthlyResult] =
      await Promise.allSettled([
        listProviderApplications(jwt, {
          tenantId: tenant,
          requestedProviderId: provider,
          status: undefined,
        }),
        getProviderRouteShareDashboard(jwt, provider, baseFilters),
        getProviderKpiDashboard(jwt, provider, baseFilters),
        getProviderRevenuePayoutDashboard(jwt, provider, {
          tenantId: tenant,
          periodMonth: period,
        }),
        listProviderMonthlyRevenueShareBatches(jwt, {
          tenantId: tenant,
          periodMonth: period,
        }),
      ]);

    const nextData: ProviderConsoleData = {
      applications: applicationsResult.status === "fulfilled" ? applicationsResult.value : [],
      route: routeResult.status === "fulfilled" ? routeResult.value : null,
      kpi: kpiResult.status === "fulfilled" ? kpiResult.value : null,
      revenue: revenueResult.status === "fulfilled" ? revenueResult.value : null,
      versions: [],
      monthly: monthlyResult.status === "fulfilled" ? monthlyResult.value : [],
    };
    const nextErrors: ProviderConsoleErrors = {};
    if (applicationsResult.status === "rejected") {
      nextErrors.applications = normalizeError(applicationsResult.reason);
    }
    if (routeResult.status === "rejected") nextErrors.route = normalizeError(routeResult.reason);
    if (kpiResult.status === "rejected") nextErrors.kpi = normalizeError(kpiResult.reason);
    if (revenueResult.status === "rejected") {
      nextErrors.revenue = normalizeError(revenueResult.reason);
    }
    if (monthlyResult.status === "rejected") {
      nextErrors.monthly = normalizeError(monthlyResult.reason);
    }

    const versionApplicationId = applicationId.trim() || nextData.applications[0]?.application_id;
    if (versionApplicationId) {
      try {
        nextData.versions = await listProviderVersionUpdates(jwt, versionApplicationId, {
          tenantId: tenant,
          requestedProviderId: provider,
        });
      } catch (err) {
        nextErrors.versions = normalizeError(err);
      }
    }

    setData(nextData);
    setErrors(nextErrors);
    setLoading(false);
  };

  const route = data.route;
  const kpi = data.kpi;
  const revenue = data.revenue;

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
            <Link href="/console/providers" className="font-medium text-foreground hover:text-primary">
              Providers
            </Link>
            <Link
              href="/console/billing/invoices"
              className="text-muted-foreground hover:text-foreground"
            >
              账单
            </Link>
            <Link
              href="/console/audit-logs"
              className="text-muted-foreground hover:text-foreground"
            >
              审计日志
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Provider Console</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              只读聚合 Provider Marketplace v2 合同：route-share、shadow KPI、收入/待结算、版本更新和月度分润批次。
            </p>
          </div>
          <StatusCard
            variant="info"
            title="只读范围"
            description="本页不执行上线、结算、审批、路由变更或 Provider 身份绑定。"
            ariaLabel="provider-console.read-only-scope"
          />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-md border border-border bg-background p-4">
            <div className="text-sm font-semibold">筛选</div>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Provider ID</span>
                <input
                  aria-label="Provider ID"
                  value={providerId}
                  onChange={(event) => setProviderId(event.target.value)}
                  placeholder="provider-alpha"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Tenant ID</span>
                <input
                  aria-label="Tenant ID"
                  value={tenantId}
                  onChange={(event) => setTenantId(event.target.value)}
                  placeholder="可选 UUID"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Application ID</span>
                <input
                  aria-label="Application ID"
                  value={applicationId}
                  onChange={(event) => setApplicationId(event.target.value)}
                  placeholder="可选；空时使用第一个匹配 application"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">月份</span>
                <input
                  aria-label="月份"
                  value={periodMonth}
                  onChange={(event) => setPeriodMonth(event.target.value)}
                  placeholder="2026-06"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <button
                type="button"
                onClick={() => void loadProviderConsole()}
                disabled={!jwt || loading}
                className="min-h-touch w-full rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "加载中..." : "加载 Provider Console"}
              </button>
              {formError && (
                <div className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
                  {formError}
                </div>
              )}
            </div>
          </div>

          <StatusCard
            variant="warning"
            title="Provider 身份边界"
            description="当前后端尚无 public Provider ownership；本页要求显式输入 Provider ID。"
            ariaLabel="provider-console.identity-boundary"
          />
        </aside>

        <section className="space-y-5">
          {loading && <LoadingShimmer variant="card" />}

          <Section title="Application" subtitle="安全字段摘要，不展示 metadata/cosign/evaluation_profile。">
            <DataError title="Application 加载失败" error={errors.applications} />
            {selectedApplication ? (
              <div className="grid gap-3 md:grid-cols-3">
                <Metric label="名称" value={selectedApplication.display_name} />
                <Metric label="组织" value={selectedApplication.organization_name} />
                <Metric label="状态" value={selectedApplication.status} />
                <Metric label="Application ID" value={selectedApplication.application_id} />
                <Metric label="Provider ID" value={selectedApplication.requested_provider_id} />
                <Metric label="Provider kind" value={selectedApplication.provider_kind} />
                <Metric label="Scope" value={selectedApplication.scope_source} />
                <Metric label="Submitted" value={formatDate(selectedApplication.submitted_at)} />
                <Metric label="Updated" value={formatDate(selectedApplication.updated_at)} />
              </div>
            ) : (
              <EmptyState
                ariaLabel="provider-console.application.empty"
                title="未找到 Provider application"
                description="可以继续查看 route/KPI/revenue 等 provider_id 级别只读投影。"
              />
            )}
          </Section>

          <Section title="Route Share" subtitle="声明式灰度阶段份额，不代表真实生产流量。">
            <DataError title="Route-share 加载失败" error={errors.route} />
            {route ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <Metric label="Rollouts" value={String(route.total_rollouts)} />
                  <Metric label="最高阶段" value={`${route.highest_current_stage_percent}%`} />
                  <Metric label="Timeline" value={String(route.timeline.length)} />
                  <Metric label="状态" value={countMapText(route.status_counts)} />
                </div>
                {route.current_rollouts.length > 0 ? (
                  <SafeTable
                    headers={["rollout", "run", "status", "stage", "updated"]}
                    rows={route.current_rollouts.map((item) => [
                      item.rollout_id,
                      item.run_id,
                      item.status,
                      `${item.current_stage_percent}%`,
                      formatDate(item.updated_at),
                    ])}
                  />
                ) : (
                  <EmptyState
                    ariaLabel="provider-console.route.empty"
                    title="暂无 route-share"
                    description="该 Provider 当前没有匹配的灰度 rollout 投影。"
                  />
                )}
              </>
            ) : (
              !errors.route && (
                <EmptyState
                  ariaLabel="provider-console.route.not-loaded"
                  title="暂无 route-share"
                  description="输入 Provider ID 后加载。"
                />
              )
            )}
          </Section>

          <Section title="Shadow KPI" subtitle="Shadow validation 指标，不代表生产成功率。">
            <DataError title="KPI 加载失败" error={errors.kpi} />
            {kpi ? (
              <>
                <div className="grid gap-3 md:grid-cols-5">
                  <Metric label="Runs" value={String(kpi.total_runs)} />
                  <Metric label="Samples" value={String(kpi.aggregate.sample_count)} />
                  <Metric label="Success rate" value={kpi.aggregate.success_rate} />
                  <Metric label="P95 ratio" value={kpi.aggregate.p95_latency_ratio} />
                  <Metric label="状态" value={countMapText(kpi.run_status_counts)} />
                </div>
                {kpi.run_metrics.length > 0 ? (
                  <SafeTable
                    headers={["run", "benchmark", "status", "violations", "updated"]}
                    rows={kpi.run_metrics.map((item) => [
                      item.run_id,
                      item.benchmark_suite,
                      item.status,
                      item.threshold_violations.length === 0
                        ? "none"
                        : item.threshold_violations.join(", "),
                      formatDate(item.updated_at),
                    ])}
                  />
                ) : (
                  <EmptyState
                    ariaLabel="provider-console.kpi.empty"
                    title="暂无 KPI"
                    description="该 Provider 当前没有匹配的 shadow validation 指标。"
                  />
                )}
              </>
            ) : (
              !errors.kpi && (
                <EmptyState
                  ariaLabel="provider-console.kpi.not-loaded"
                  title="暂无 KPI"
                  description="输入 Provider ID 后加载。"
                />
              )
            )}
          </Section>

          <Section title="收入/待结算" subtitle="Read-model payout projection，不代表银行打款或税务结算。">
            <DataError title="收入/待结算加载失败" error={errors.revenue} />
            {revenue ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <Metric label="Entries" value={String(revenue.total_entries)} />
                  <Metric label="Provider revenue" value={firstCurrencyTotal(revenue.currency_totals)} />
                  <Metric label="状态" value={countMapText(revenue.status_counts)} />
                  <Metric label="Period" value={revenue.period_month ?? "-"} />
                </div>
                {revenue.period_summaries.length > 0 && (
                  <SafeTable
                    headers={["period", "entries", "provider revenue", "pending", "held"]}
                    rows={revenue.period_summaries.map((item) => [
                      item.period_month,
                      String(item.entry_count),
                      `${item.provider_revenue_amount} ${item.currency}`,
                      `${item.pending_payout_amount} ${item.currency}`,
                      `${item.held_payout_amount} ${item.currency}`,
                    ])}
                  />
                )}
                {revenue.entries.length > 0 ? (
                  <SafeTable
                    headers={["entry", "algo", "status", "provider amount", "recognized"]}
                    rows={revenue.entries.map((item) => [
                      item.entry_id,
                      item.k_algo,
                      item.status,
                      `${item.provider_revenue_amount} ${item.currency}`,
                      formatDate(item.recognized_at),
                    ])}
                  />
                ) : (
                  <EmptyState
                    ariaLabel="provider-console.revenue.empty"
                    title="暂无收入/待结算"
                    description="该 Provider 当前没有匹配的 payout entry。"
                  />
                )}
              </>
            ) : (
              !errors.revenue && (
                <EmptyState
                  ariaLabel="provider-console.revenue.not-loaded"
                  title="暂无收入/待结算"
                  description="输入 Provider ID 后加载。"
                />
              )
            )}
          </Section>

          <Section title="版本更新" subtitle="Review approval 不代表部署或 live catalog 变更。">
            <DataError title="版本更新加载失败" error={errors.versions} />
            {data.versions.length > 0 ? (
              <SafeTable
                headers={["update", "version", "kind", "status", "review", "updated"]}
                rows={data.versions.map((item) => [
                  item.version_update_id,
                  `${item.current_version} -> ${item.proposed_version}`,
                  item.change_kind,
                  item.status,
                  fieldValue(item.review_notes_ref),
                  formatDate(item.updated_at),
                ])}
              />
            ) : (
              <EmptyState
                ariaLabel="provider-console.versions.empty"
                title="暂无版本更新"
                description="未找到可用于查询 version updates 的 application，或该 application 暂无版本更新。"
              />
            )}
          </Section>

          <Section title="月度分润批次" subtitle="Calculation lifecycle，不代表已支付、已开票或已纳税。">
            <DataError title="月度分润批次加载失败" error={errors.monthly} />
            {data.monthly.length > 0 ? (
              <SafeTable
                headers={["batch", "period", "status", "entries", "provider revenue", "checksum"]}
                rows={data.monthly.map((item) => [
                  item.batch_id,
                  item.period_month,
                  item.status,
                  `${item.entry_count} / ${item.provider_count}`,
                  firstCurrencyTotal(item.currency_totals),
                  item.calculation_checksum.slice(-10),
                ])}
              />
            ) : (
              <EmptyState
                ariaLabel="provider-console.monthly.empty"
                title="暂无月度分润批次"
                description="该范围内没有 monthly revenue-share batch。"
              />
            )}
          </Section>
        </section>
      </section>
    </main>
  );
}
