"use client";
/** /console/providers — Provider Marketplace v2 read-only aggregate surface (Story 7.B.9). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import { ConsolePageHeader, ConsoleShell } from "@/components/ConsoleShell";
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
type OperationalState = "ready" | "watch" | "blocked/error" | "empty" | "not loaded";

interface ProviderConsoleData {
  applications: ProviderApplicationResponse[];
  route: ProviderRouteShareDashboardResponse | null;
  kpi: ProviderKpiDashboardResponse | null;
  revenue: ProviderRevenuePayoutDashboardResponse | null;
  versions: ProviderVersionUpdateResponse[];
  monthly: ProviderMonthlyRevenueShareBatchResponse[];
}

type ProviderConsoleErrors = Partial<Record<SectionKey, string>>;

interface SubmittedProviderContext {
  providerId: string;
  tenantId?: string;
  applicationId?: string;
  periodMonth?: string;
}

interface OperationalBand {
  title: string;
  state: OperationalState;
  detail: string;
}

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
    <section className="min-w-0 space-y-3 rounded-md border border-border bg-background p-4">
      <div className="min-w-0">
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
    <div className="min-w-0 max-w-full overflow-x-auto rounded-md border border-border">
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

function buildHandoffHref(context: SubmittedProviderContext): string {
  const params = new URLSearchParams();
  params.set("provider_id", context.providerId);
  if (context.tenantId) params.set("tenant_id", context.tenantId);
  if (context.applicationId) params.set("application_id", context.applicationId);
  if (context.periodMonth) params.set("period_month", context.periodMonth);
  return `/console/routing-history?${params.toString()}`;
}

function buildOperationalBands(
  data: ProviderConsoleData,
  errors: ProviderConsoleErrors,
  submittedContext: SubmittedProviderContext | null,
  selectedApplication: ProviderApplicationResponse | null,
): OperationalBand[] {
  if (!submittedContext) {
    return [
      "Application readiness",
      "Route Share rollout",
      "Shadow KPI quality",
      "Revenue/Payout projection",
      "Version Updates lifecycle",
      "Monthly Batches lifecycle",
    ].map((title) => ({
      title,
      state: "not loaded" as const,
      detail: "提交 Provider ID 后加载。",
    }));
  }

  const applicationBand = (): OperationalBand => {
    if (errors.applications) {
      return {
        title: "Application readiness",
        state: "blocked/error",
        detail: errors.applications,
      };
    }
    if (!selectedApplication) {
      return {
        title: "Application readiness",
        state: "empty",
        detail: "没有匹配的 Provider application；该上下文不代表身份绑定。",
      };
    }
    if (selectedApplication.status === "accepted") {
      return {
        title: "Application readiness",
        state: "ready",
        detail: "Application accepted；仍为显式筛选上下文。",
      };
    }
    if (selectedApplication.status === "rejected") {
      return {
        title: "Application readiness",
        state: "blocked/error",
        detail: "Application rejected；需要查看 review lifecycle。",
      };
    }
    return {
      title: "Application readiness",
      state: "watch",
      detail: `Application status=${selectedApplication.status}；不表示 Provider ownership。`,
    };
  };

  const routeBand = (): OperationalBand => {
    if (errors.route) return { title: "Route Share rollout", state: "blocked/error", detail: errors.route };
    if (!data.route || data.route.total_rollouts === 0) {
      return {
        title: "Route Share rollout",
        state: "empty",
        detail: "没有 declared rollout stage/share 投影。",
      };
    }
    const activeOrCompleted = data.route.current_rollouts.some(
      (item) => item.status === "active" || item.status === "completed",
    );
    return {
      title: "Route Share rollout",
      state: activeOrCompleted ? "ready" : "watch",
      detail: `${data.route.total_rollouts} rollout(s), max declared stage ${data.route.highest_current_stage_percent}%。`,
    };
  };

  const kpiBand = (): OperationalBand => {
    if (errors.kpi) return { title: "Shadow KPI quality", state: "blocked/error", detail: errors.kpi };
    if (!data.kpi || data.kpi.total_runs === 0 || data.kpi.aggregate.sample_count === 0) {
      return {
        title: "Shadow KPI quality",
        state: "empty",
        detail: "没有 shadow validation run/sample。",
      };
    }
    const failedRuns = data.kpi.run_status_counts.failed + data.kpi.run_status_counts.cancelled;
    const violationCount = data.kpi.run_metrics.reduce(
      (total, item) => total + item.threshold_violations.length,
      0,
    );
    return {
      title: "Shadow KPI quality",
      state: failedRuns > 0 || violationCount > 0 ? "blocked/error" : "ready",
      detail: `${data.kpi.total_runs} run(s), ${data.kpi.aggregate.sample_count} shadow samples, ${violationCount} threshold violation(s)。`,
    };
  };

  const revenueBand = (): OperationalBand => {
    if (errors.revenue) {
      return { title: "Revenue/Payout projection", state: "blocked/error", detail: errors.revenue };
    }
    if (!data.revenue || data.revenue.total_entries === 0) {
      return {
        title: "Revenue/Payout projection",
        state: "empty",
        detail: "没有 revenue/payout read-model entry。",
      };
    }
    if (data.revenue.status_counts.voided > 0) {
      return {
        title: "Revenue/Payout projection",
        state: "blocked/error",
        detail: `${data.revenue.status_counts.voided} voided projection entry；非银行打款状态。`,
      };
    }
    const pendingOrHeld = data.revenue.status_counts.pending + data.revenue.status_counts.held;
    return {
      title: "Revenue/Payout projection",
      state: pendingOrHeld > 0 ? "watch" : "ready",
      detail: `${data.revenue.total_entries} projection entry(s), pending/held=${pendingOrHeld}。`,
    };
  };

  const versionsBand = (): OperationalBand => {
    if (errors.versions) {
      return { title: "Version Updates lifecycle", state: "blocked/error", detail: errors.versions };
    }
    if (data.versions.length === 0) {
      return {
        title: "Version Updates lifecycle",
        state: "empty",
        detail: "没有 version review lifecycle row。",
      };
    }
    const attention = data.versions.some((item) =>
      ["submitted", "under_review", "rejected"].includes(item.status),
    );
    return {
      title: "Version Updates lifecycle",
      state: attention ? "watch" : "ready",
      detail: `${data.versions.length} review lifecycle row(s)；不代表部署或 live catalog mutation。`,
    };
  };

  const monthlyBand = (): OperationalBand => {
    if (errors.monthly) {
      return { title: "Monthly Batches lifecycle", state: "blocked/error", detail: errors.monthly };
    }
    if (data.monthly.length === 0) {
      return {
        title: "Monthly Batches lifecycle",
        state: "empty",
        detail: "没有 monthly revenue-share batch。",
      };
    }
    if (data.monthly.some((item) => item.status === "cancelled")) {
      return {
        title: "Monthly Batches lifecycle",
        state: "blocked/error",
        detail: "存在 cancelled calculation batch；不代表支付失败。",
      };
    }
    const draftOrReviewed = data.monthly.some(
      (item) => item.status === "draft" || item.status === "reviewed",
    );
    return {
      title: "Monthly Batches lifecycle",
      state: draftOrReviewed ? "watch" : "ready",
      detail: `${data.monthly.length} calculation batch row(s)；不代表付款、开票或纳税。`,
    };
  };

  return [
    applicationBand(),
    routeBand(),
    kpiBand(),
    revenueBand(),
    versionsBand(),
    monthlyBand(),
  ];
}

function issueBands(bands: OperationalBand[]): OperationalBand[] {
  return bands.filter((band) => band.state !== "ready" && band.state !== "not loaded");
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
  const [submittedContext, setSubmittedContext] = useState<SubmittedProviderContext | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const selectedApplication = useMemo(() => {
    if (submittedContext?.applicationId) {
      return (
        data.applications.find((item) => item.application_id === submittedContext.applicationId) ??
        null
      );
    }
    return data.applications[0] ?? null;
  }, [data.applications, submittedContext?.applicationId]);

  const loadProviderConsole = async (): Promise<void> => {
    if (!jwt) return;
    const provider = providerId.trim();
    const tenant = tenantId.trim() || undefined;
    const submittedApplication = applicationId.trim() || undefined;
    const period = periodMonth.trim() || undefined;
    if (!provider) {
      setFormError("请输入 Provider ID。");
      return;
    }

    const nextContext: SubmittedProviderContext = {
      providerId: provider,
      tenantId: tenant,
      applicationId: submittedApplication,
      periodMonth: period,
    };
    setFormError(null);
    setLoading(true);
    setErrors({});
    setData(emptyData);
    setSubmittedContext(nextContext);
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

    const versionApplicationId = submittedApplication || nextData.applications[0]?.application_id;
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
  const operationalBands = buildOperationalBands(data, errors, submittedContext, selectedApplication);
  const openIssues = issueBands(operationalBands);

  return (
    <ConsoleShell active="providers">
      <ConsolePageHeader
        eyebrow="Console / Provider governance"
        title="Provider Console"
        description="只读聚合 Provider Marketplace v2 合同：route-share、shadow KPI、收入/待结算、版本更新和月度分润批次。"
        meta={
          <>
            <span className="inline-flex min-h-touch items-center rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
              只读聚合
            </span>
            <span className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground">
              Provider ID 显式筛选
            </span>
            <span className="inline-flex min-h-touch items-center rounded-md border border-success/30 bg-success/5 px-3 py-1.5 text-xs font-medium text-success">
              不写入浏览器存储
            </span>
          </>
        }
        actions={
          <div className="max-w-sm">
            <StatusCard
              variant="info"
              title="只读范围"
              description="本页不执行上线、结算、审批、路由变更或 Provider 身份绑定。"
              ariaLabel="provider-console.read-only-scope"
            />
          </div>
        }
      />

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4">
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

        <section className="min-w-0 space-y-5">
          {loading && <LoadingShimmer variant="card" />}

          <Section
            title="Tier 3 Operational Overview"
            subtitle="只基于已请求的安全 summary 字段派生，不使用生产流量、付款、部署或身份绑定假设。"
          >
            <SafeTable
              headers={["signal", "state", "detail"]}
              rows={operationalBands.map((band) => [band.title, band.state, band.detail])}
            />
          </Section>

          {submittedContext && (
            <Section
              title="Provider Console open issues"
              subtitle="需要关注的 partial failure、empty 或 watch 状态；不包含 raw payload。"
            >
              {openIssues.length === 0 ? (
                <StatusCard
                  variant="info"
                  title="No open Provider Console issues"
                  description="当前已加载 summary 没有派生出 open issue。"
                  ariaLabel="provider-console.issues.none"
                />
              ) : (
                <ul className="space-y-2 text-sm">
                  {openIssues.map((issue) => (
                    <li
                      key={`${issue.title}-${issue.state}`}
                      className="rounded-md border border-border bg-muted p-3"
                    >
                      <span className="font-medium">
                        {issue.title}: {issue.state}
                      </span>
                      <span className="ml-2 text-muted-foreground">{issue.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          {submittedContext && (
            <Section
              title="Routing History Handoff"
              subtitle="只传递显式筛选上下文；Routing History 仍需手动输入 solver API key 和 optimization ID。"
            >
              <Link
                href={buildHandoffHref(submittedContext)}
                className="inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600"
              >
                打开 Routing History
              </Link>
            </Section>
          )}

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
    </ConsoleShell>
  );
}
