"use client";
/** /console/routing-history — public-safe optimization provider routing history (Story 8.C.2). */

import Link from "next/link";
import { useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import {
  getOptimization,
  OptiCloudClientError,
  type GetOptimizationResponse,
  type RoutingHistory,
  type RoutingHistoryRoute,
} from "@/lib/api";

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    return `${err.title}: ${err.detail}`;
  }
  if (err && typeof err === "object" && "title" in err && "detail" in err) {
    const payload = err as { title?: unknown; detail?: unknown };
    if (typeof payload.title === "string" && typeof payload.detail === "string") {
      return `${payload.title}: ${payload.detail}`;
    }
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function fieldValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
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

function RouteSummary({
  title,
  route,
}: {
  title: string;
  route: RoutingHistoryRoute | null;
}): JSX.Element {
  if (!route) {
    return (
      <EmptyState
        ariaLabel={`routing-history.${title}.empty`}
        title={`${title} 未执行`}
        description="该任务当前没有对应的已执行 route。"
      />
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Metric label={`${title} Provider`} value={route.provider_id} />
      <Metric label="Solver" value={route.selected_solver} />
      <Metric label="Kind" value={route.provider_kind} />
      <Metric label="Task" value={route.task_type} />
      <Metric label="Requested" value={fieldValue(route.requested_solver)} />
      <Metric label="Reason" value={route.routing_reason} />
    </div>
  );
}

function AttemptsTable({ history }: { history: RoutingHistory }): JSX.Element {
  if (history.attempts.length === 0) {
    return (
      <EmptyState
        ariaLabel="routing-history.attempts.empty"
        title="暂无 attempt"
        description="队列中或尚未执行的任务只显示 planned primary route。"
      />
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[840px] text-sm">
        <thead className="bg-muted">
          <tr>
            {[
              "#",
              "role",
              "provider",
              "solver",
              "status",
              "retryable",
              "terminal",
              "seconds",
              "reason",
            ].map((header) => (
              <th key={header} className="px-3 py-2 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {history.attempts.map((attempt) => {
            const terminal = attempt.attempt === history.summary.terminal_attempt;
            return (
              <tr key={`${attempt.attempt}-${attempt.role}`} className="border-t border-border">
                <td className="px-3 py-2 align-top">{attempt.attempt}</td>
                <td className="px-3 py-2 align-top">{attempt.role}</td>
                <td className="px-3 py-2 align-top">{attempt.provider_id}</td>
                <td className="px-3 py-2 align-top">{attempt.selected_solver}</td>
                <td className="px-3 py-2 align-top">{attempt.status}</td>
                <td className="px-3 py-2 align-top">{String(attempt.retryable)}</td>
                <td className="px-3 py-2 align-top">{terminal ? "terminal" : "-"}</td>
                <td className="px-3 py-2 align-top">{attempt.solve_seconds}</td>
                <td className="px-3 py-2 align-top">{attempt.routing_reason}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function RoutingHistoryPage(): JSX.Element {
  const [apiKey, setApiKey] = useState("");
  const [optimizationId, setOptimizationId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GetOptimizationResponse | null>(null);

  const loadRoutingHistory = async (): Promise<void> => {
    const key = apiKey.trim();
    const optId = optimizationId.trim();
    if (!key) {
      setFormError("请输入 API key。");
      return;
    }
    if (!optId) {
      setFormError("请输入 Optimization ID。");
      return;
    }
    setFormError(null);
    setError(null);
    setLoading(true);
    try {
      setResult(await getOptimization(key, optId));
    } catch (err) {
      setResult(null);
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  const history = result?.routing_history;

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
            <Link href="/console/providers" className="text-muted-foreground hover:text-foreground">
              Providers
            </Link>
            <Link href="/console/routing-history" className="font-medium text-foreground">
              Routing History
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
            <h1 className="text-2xl font-bold">Provider Routing History</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              查询单个 optimization 的 primary route、executed route 和 fallback attempt history。
            </p>
          </div>
          <StatusCard
            variant="info"
            title="安全边界"
            description="本页只展示 public-safe routing 字段，不展示请求、账单、错误诊断或内部 metadata。"
            ariaLabel="routing-history.scope"
          />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-md border border-border bg-background p-4">
            <div className="text-sm font-semibold">查询</div>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">API key</span>
                <input
                  aria-label="API key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="sk-..."
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Optimization ID</span>
                <input
                  aria-label="Optimization ID"
                  value={optimizationId}
                  onChange={(event) => setOptimizationId(event.target.value)}
                  placeholder="UUID"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <button
                type="button"
                onClick={() => void loadRoutingHistory()}
                disabled={loading}
                className="min-h-touch w-full rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "加载中..." : "加载 routing history"}
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
            title="凭据不持久化"
            description="API key 和 optimization ID 只保存在当前页面内存中。"
            ariaLabel="routing-history.credential-boundary"
          />
        </aside>

        <section className="space-y-5">
          {loading && <LoadingShimmer variant="card" />}
          {error && (
            <StatusCard
              variant="error"
              title="查询失败"
              description={error}
              ariaLabel="routing-history.error"
            />
          )}
          {result && (
            <StatusCard
              variant="info"
              title={`status=${result.status}`}
              description={`optimization=${result.optimization_id}`}
              ariaLabel="routing-history.optimization-status"
            />
          )}

          {result && !history && (
            <EmptyState
              ariaLabel="routing-history.empty"
              title="暂无 routing history"
              description="该历史任务没有可公开展示的 provider route metadata。"
            />
          )}

          {history && (
            <>
              <Section title="Summary" subtitle="单次 optimization 的 fallback 执行摘要。">
                <div className="grid gap-3 md:grid-cols-5">
                  <Metric label="Attempts" value={`attempts=${history.summary.attempt_count}`} />
                  <Metric label="Fallback" value={String(history.summary.fallback_used)} />
                  <Metric
                    label="Terminal"
                    value={`terminal=${fieldValue(history.summary.terminal_status)}`}
                  />
                  <Metric label="Exhausted" value={String(history.summary.exhausted)} />
                  <Metric label="Seconds" value={String(history.summary.solve_seconds)} />
                </div>
              </Section>

              <Section title="Primary Route">
                <RouteSummary title="Primary" route={history.primary_route} />
              </Section>

              <Section title="Executed Route">
                <RouteSummary title="Executed" route={history.executed_route} />
              </Section>

              <Section title="Attempt Timeline" subtitle="primary/fallback attempt 顺序。">
                <AttemptsTable history={history} />
              </Section>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
