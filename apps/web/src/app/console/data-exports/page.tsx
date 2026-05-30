"use client";
/** /console/data-exports — PIPL self-service data export portal (Story 5.C.5). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusCard } from "@opticloud/ui";

import {
  type DataExportFormat,
  type DataExportStatusResponse,
  downloadDataExport,
  getDataExportStatus,
  OptiCloudClientError,
  requestDataExport,
} from "@/lib/api";

type ExportState = {
  status: DataExportStatusResponse | null;
  loading: boolean;
  downloading: boolean;
  error: string | null;
};

const emptyState: ExportState = {
  status: null,
  loading: false,
  downloading: false,
  error: null,
};

const formats: Array<{ format: DataExportFormat; label: string; description: string }> = [
  {
    format: "json",
    label: "JSON",
    description: "Portable structured package for audit, migration, and support review.",
  },
  {
    format: "csv",
    label: "CSV",
    description: "Spreadsheet-friendly zip package with one manifest and section CSV files.",
  },
];

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatBytes(value: number | null): string {
  if (value === null) return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 409) return "导出仍在处理中，请稍后刷新状态。";
    if (err.status === 410) return "导出包已过期，请重新发起请求。";
    if (err.status === 404) return "导出请求不可用。";
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function isTerminal(status: DataExportStatusResponse | null): boolean {
  return (
    status?.status === "completed" || status?.status === "failed" || status?.status === "expired"
  );
}

function shouldPoll(status: DataExportStatusResponse | null): boolean {
  return status?.status === "queued" || status?.status === "processing";
}

function statusLabel(status: DataExportStatusResponse | null): string {
  if (!status) return "未请求";
  const labels: Record<DataExportStatusResponse["status"], string> = {
    queued: "排队中",
    processing: "处理中",
    completed: "可下载",
    failed: "失败",
    expired: "已过期",
  };
  return labels[status.status];
}

function saveBlobDownload(download: { blob: Blob; filename: string }): void {
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

export default function DataExportsConsolePage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<DataExportFormat>("json");
  const [exportsByFormat, setExportsByFormat] = useState<Record<DataExportFormat, ExportState>>({
    json: emptyState,
    csv: emptyState,
  });

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const setFormatState = useCallback(
    (format: DataExportFormat, updater: (state: ExportState) => ExportState): void => {
      setExportsByFormat((current) => ({
        ...current,
        [format]: updater(current[format]),
      }));
    },
    [],
  );

  const refreshStatus = useCallback(
    async (format: DataExportFormat, exportId: string): Promise<void> => {
      if (!jwt) return;
      try {
        const status = await getDataExportStatus(jwt, exportId);
        setFormatState(format, (state) =>
          state.status?.id === exportId && status.id === exportId
            ? { ...state, status, error: null }
            : state,
        );
      } catch (err) {
        setFormatState(format, (state) =>
          state.status?.id === exportId ? { ...state, error: normalizeError(err) } : state,
        );
      }
    },
    [jwt, setFormatState],
  );

  useEffect(() => {
    const timers = formats
      .map(({ format }) => {
        const current = exportsByFormat[format].status;
        if (!jwt || !current || !shouldPoll(current) || isTerminal(current)) return null;
        return window.setInterval(() => {
          void refreshStatus(format, current.id);
        }, 2000);
      })
      .filter((timer): timer is number => timer !== null);

    return () => {
      timers.forEach((timer) => window.clearInterval(timer));
    };
  }, [exportsByFormat, jwt, refreshStatus]);

  const selectedState = exportsByFormat[selectedFormat];
  const canRequest = useMemo(() => {
    const state = exportsByFormat[selectedFormat];
    return Boolean(jwt) && !state.loading && !shouldPoll(state.status);
  }, [exportsByFormat, jwt, selectedFormat]);

  const handleRequest = async (format: DataExportFormat): Promise<void> => {
    if (!jwt) return;
    setFormatState(format, (state) => ({ ...state, loading: true, error: null }));
    try {
      const status = await requestDataExport(jwt, format);
      setFormatState(format, (state) => ({ ...state, status, loading: false }));
    } catch (err) {
      setFormatState(format, (state) => ({
        ...state,
        loading: false,
        error: normalizeError(err),
      }));
    }
  };

  const handleDownload = async (format: DataExportFormat): Promise<void> => {
    const status = exportsByFormat[format].status;
    if (!jwt || !status || status.status !== "completed") return;
    setFormatState(format, (state) => ({ ...state, downloading: true, error: null }));
    try {
      const download = await downloadDataExport(jwt, status);
      saveBlobDownload(download);
      setFormatState(format, (state) => ({ ...state, downloading: false }));
    } catch (err) {
      if (status.id) await refreshStatus(format, status.id);
      setFormatState(format, (state) => ({
        ...state,
        downloading: false,
        error: normalizeError(err),
      }));
    }
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
              className="font-medium text-foreground hover:text-primary"
            >
              数据导出
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <h1 className="text-2xl font-bold">PIPL 数据导出</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            请求 JSON 或 CSV 数据副本、跟踪处理状态，并通过当前登录态下载已完成包。7 天是
            OptiCloud 产品 SLA。
          </p>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-md border border-border bg-background p-4">
            <div className="text-sm font-medium">导出格式</div>
            <div className="mt-3 grid grid-cols-2 gap-2" role="tablist" aria-label="导出格式">
              {formats.map((item) => (
                <button
                  key={item.format}
                  type="button"
                  role="tab"
                  aria-selected={selectedFormat === item.format}
                  onClick={() => setSelectedFormat(item.format)}
                  className={[
                    "min-h-touch rounded-md border px-3 py-2 text-sm font-semibold",
                    selectedFormat === item.format
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-foreground hover:bg-muted",
                  ].join(" ")}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              当前页面只跟踪本会话请求；刷新后可再次点击同一格式，后端会返回仍有效的活跃请求。
            </p>
          </div>

          <StatusCard
            variant="info"
            title="通知状态"
            description="邮件通知由后续通知基础设施处理；当前 Console 下载会保留 Authorization。"
            ariaLabel="data-exports.notification-scope"
          />
        </aside>

        <section className="space-y-5">
          <div className="rounded-md border border-border bg-background p-5">
            <div className="flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">
                  {selectedFormat === "json" ? "JSON 导出" : "CSV 导出"}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {formats.find((item) => item.format === selectedFormat)?.description}
                </p>
              </div>
              <button
                type="button"
                disabled={!canRequest}
                onClick={() => void handleRequest(selectedFormat)}
                className="min-h-touch w-fit rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {selectedState.loading ? "请求中..." : `请求 ${selectedFormat.toUpperCase()}`}
              </button>
            </div>

            {selectedState.error && (
              <div className="mt-4">
                <StatusCard
                  variant="error"
                  title="导出操作失败"
                  description={selectedState.error}
                  ariaLabel="data-exports.error"
                />
              </div>
            )}

            <StatusPanel
              state={selectedState}
              onRefresh={() => {
                const current = selectedState.status;
                if (current) void refreshStatus(selectedFormat, current.id);
              }}
              onDownload={() => void handleDownload(selectedFormat)}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {formats.map(({ format }) => (
              <CompactFormatPanel
                key={format}
                format={format}
                state={exportsByFormat[format]}
                onSelect={() => setSelectedFormat(format)}
              />
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function StatusPanel({
  state,
  onRefresh,
  onDownload,
}: {
  state: ExportState;
  onRefresh: () => void;
  onDownload: () => void;
}): JSX.Element {
  const status = state.status;
  const canDownload = status?.status === "completed" && !state.downloading;
  return (
    <div className="mt-5">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm text-muted-foreground">当前状态</div>
          <div className="mt-1 text-xl font-semibold">{statusLabel(status)}</div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!status}
            onClick={onRefresh}
            className="min-h-touch rounded-md border border-border px-3 py-2 text-sm font-semibold hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            刷新
          </button>
          <button
            type="button"
            disabled={!canDownload}
            onClick={onDownload}
            className="min-h-touch rounded-md bg-success px-3 py-2 text-sm font-semibold text-white hover:bg-success/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {state.downloading ? "下载中..." : "下载"}
          </button>
        </div>
      </div>

      <dl className="grid gap-3 text-sm md:grid-cols-2">
        <Field label="请求 ID" value={status?.id ?? "-"} mono />
        <Field label="格式" value={status?.format?.toUpperCase() ?? "-"} />
        <Field label="请求时间" value={formatDate(status?.requested_at ?? null)} />
        <Field label="SLA 截止" value={formatDate(status?.sla_deadline_at ?? null)} />
        <Field label="完成时间" value={formatDate(status?.completed_at ?? null)} />
        <Field label="过期时间" value={formatDate(status?.expires_at ?? null)} />
        <Field label="包大小" value={formatBytes(status?.package_bytes ?? null)} />
        <Field label="SHA-256" value={status?.package_sha256 ?? "-"} mono />
      </dl>

      {status?.status === "failed" && (
        <p className="mt-4 rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
          {status.last_error ?? "导出失败，请稍后重新请求。"}
        </p>
      )}
      {status?.status === "expired" && (
        <p className="mt-4 rounded-md border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
          导出包已过期，请重新发起同一格式请求。
        </p>
      )}
      {shouldPoll(status) && (
        <p className="mt-4 rounded-md border border-border bg-muted p-3 text-sm text-muted-foreground">
          导出正在准备中，页面会自动刷新此请求状态。
        </p>
      )}
    </div>
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

function CompactFormatPanel({
  format,
  state,
  onSelect,
}: {
  format: DataExportFormat;
  state: ExportState;
  onSelect: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="rounded-md border border-border bg-background p-4 text-left hover:bg-muted"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="font-semibold">{format.toUpperCase()}</div>
        <span className="rounded bg-muted px-2 py-1 text-xs font-medium">
          {statusLabel(state.status)}
        </span>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        {state.status ? formatDate(state.status.requested_at) : "本会话尚未请求"}
      </div>
    </button>
  );
}
