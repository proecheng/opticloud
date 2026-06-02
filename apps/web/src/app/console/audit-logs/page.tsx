"use client";
/** /console/audit-logs — self-service user audit history (Story 8.A.5). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuditLogTable, StatusCard, type AuditLogTimeRange } from "@opticloud/ui";

import {
  listMyAuditLogs,
  OptiCloudClientError,
  type UserAuditLogItem,
  type UserAuditLogFilters,
  type UserAuditLogsResponse,
} from "@/lib/api";

type PageState = {
  items: UserAuditLogItem[];
  nextCursor: string | null;
  from: string | null;
  to: string | null;
  loading: boolean;
  error: string | null;
};

const DEFAULT_LIMIT = 50;

const initialState: PageState = {
  items: [],
  nextCursor: null,
  from: null,
  to: null,
  loading: false,
  error: null,
};

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 401) return "登录状态已失效，请重新登录。";
    if (err.status === 422) return `筛选条件无效：${err.detail}`;
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

export default function AuditLogsPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [state, setState] = useState<PageState>(initialState);
  const requestSequenceRef = useRef(0);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const loadPage = useCallback(
    async (token: string, filters: UserAuditLogFilters): Promise<void> => {
      const requestId = requestSequenceRef.current + 1;
      requestSequenceRef.current = requestId;
      setState((current) => ({
        ...current,
        loading: true,
        error: null,
        items: filters.cursor ? current.items : [],
        nextCursor: filters.cursor ? current.nextCursor : null,
      }));
      try {
        const response = await listMyAuditLogs(token, filters);
        if (requestId !== requestSequenceRef.current) return;
        setState({
          items: response.items,
          nextCursor: response.next_cursor,
          from: response.from,
          to: response.to,
          loading: false,
          error: null,
        });
      } catch (err) {
        if (requestId !== requestSequenceRef.current) return;
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
    void loadPage(jwt, { limit: DEFAULT_LIMIT });
  }, [jwt, loadPage]);

  const handleApplyTimeRange = (range: AuditLogTimeRange): void => {
    if (!jwt) return;
    void loadPage(jwt, {
      limit: DEFAULT_LIMIT,
      from: range.from,
      to: range.to,
      cursor: undefined,
    });
  };

  const handleLoadNext = (cursor: string): void => {
    if (!jwt) return;
    void loadPage(jwt, {
      limit: DEFAULT_LIMIT,
      from: state.from,
      to: state.to,
      cursor,
    });
  };

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
            <Link href="/console/repro" className="text-muted-foreground hover:text-foreground">
              Repro
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
              href="/console/billing/invoices"
              className="text-muted-foreground hover:text-foreground"
            >
              账单
            </Link>
            <Link
              href="/console/audit-logs"
              className="font-medium text-foreground hover:text-primary"
            >
              审计日志
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">审计日志</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              查看当前账号的关键安全、API Key、数据导出和系统活动记录。
            </p>
          </div>
          <div className="text-sm text-muted-foreground">
            {state.loading ? "正在同步..." : state.from && state.to ? "时间窗已同步" : "等待数据"}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <StatusCard
            variant="info"
            title="数据边界"
            description="这里只显示当前登录用户自己的审计日志；metadata 已由后端脱敏，前端会再次隐藏疑似敏感字段。"
            ariaLabel="audit-logs.scope"
          />
          <div className="rounded-md border border-border bg-background p-4 text-sm">
            <div className="font-medium">分页策略</div>
            <p className="mt-2 text-muted-foreground">
              下一页使用后端返回的 opaque cursor；调整时间范围会重新加载第一页。
            </p>
          </div>
        </aside>

        <AuditLogTable
          items={state.items}
          nextCursor={state.nextCursor}
          from={state.from}
          to={state.to}
          isLoading={state.loading}
          error={state.error}
          onApplyTimeRange={handleApplyTimeRange}
          onLoadNext={handleLoadNext}
          ariaLabel="console.audit_logs.table"
        />
      </section>
    </main>
  );
}
