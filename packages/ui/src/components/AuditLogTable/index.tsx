"use client";
/** AuditLogTable (Tier 2, Story 8.A.5).
 *
 * Presentation-only audit history surface. Parents own auth, API calls, cursor
 * lifecycle, and routing.
 */

import { ChevronRight, Filter, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type AuditLogMetadata = Record<string, unknown>;

export interface AuditLogTableItem {
  id: string;
  actor: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: AuditLogMetadata;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogTimeRange {
  from?: string;
  to?: string;
}

export interface AuditLogTableProps {
  items: AuditLogTableItem[];
  nextCursor?: string | null;
  from?: string | null;
  to?: string | null;
  isLoading?: boolean;
  error?: string | null;
  onApplyTimeRange?: (range: AuditLogTimeRange) => void;
  onLoadNext?: (cursor: string) => void;
  className?: string;
  ariaLabel?: string;
}

const SENSITIVE_KEY_PATTERN =
  /(^|_)(api_key|key_hash|token|token_hash|authorization|jwt|password|secret|cookie|webhook_url|provider_payload|raw_request|raw_response|otp|pepper)($|_)/i;
const SAFE_METADATA_KEYS = new Set(["webhook_url_configured"]);
const BEARER_PATTERN = /\bBearer\s+[A-Za-z0-9._~+/=-]+/i;
const API_KEY_PATTERN = /\bsk-[A-Za-z0-9_-]{6,}\b/i;
const JWT_PATTERN = /\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/;
const SECRET_VALUE_PATTERN = /\b(secret|password|private[_-]?key|access[_-]?token)\b/i;
const MAX_METADATA_ENTRIES = 6;
const MAX_VALUE_LENGTH = 96;

export function AuditLogTable({
  items,
  nextCursor = null,
  from = null,
  to = null,
  isLoading = false,
  error = null,
  onApplyTimeRange,
  onLoadNext,
  className,
  ariaLabel = "audit-log-table",
}: AuditLogTableProps): JSX.Element {
  const a11y = useA11y({ ariaLabel, role: "region" });
  const [query, setQuery] = useState("");
  const [fromInput, setFromInput] = useState(toDateTimeLocalValue(from));
  const [toInput, setToInput] = useState(toDateTimeLocalValue(to));

  useEffect(() => {
    setFromInput(toDateTimeLocalValue(from));
  }, [from]);

  useEffect(() => {
    setToInput(toDateTimeLocalValue(to));
  }, [to]);

  const rows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) => searchableText(item).includes(normalized));
  }, [items, query]);

  const handleApplyTimeRange = (): void => {
    onApplyTimeRange?.({
      from: dateTimeLocalToIso(fromInput),
      to: dateTimeLocalToIso(toInput),
    });
  };

  const handleClearTimeRange = (): void => {
    setFromInput("");
    setToInput("");
    onApplyTimeRange?.({});
  };

  const handleLoadNext = (): void => {
    if (nextCursor) onLoadNext?.(nextCursor);
  };

  const hasRows = rows.length > 0;
  const hasSourceRows = items.length > 0;

  return (
    <section
      {...a11y.attrs}
      ref={a11y.ref}
      className={cn("rounded-md border border-border bg-background text-foreground", className)}
      data-testid="audit-log-table"
    >
      <header className="border-b border-border p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">审计日志</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              当前页 {rows.length} / {items.length} 条
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            服务端时间窗：{formatDateTime(from)} - {formatDateTime(to)}
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(180px,1fr)_180px_180px_auto_auto]">
          <label className="min-w-0 text-sm font-medium" htmlFor="audit-log-search">
            搜索当前页
            <span className="mt-1 flex min-h-touch items-center gap-2 rounded-md border border-border bg-background px-3 py-2">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <input
                id="audit-log-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="action / actor / resource / metadata"
              />
            </span>
          </label>

          <label className="min-w-0 text-sm font-medium" htmlFor="audit-log-from">
            开始时间
            <input
              id="audit-log-from"
              type="datetime-local"
              value={fromInput}
              onChange={(event) => setFromInput(event.target.value)}
              className="mt-1 min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="min-w-0 text-sm font-medium" htmlFor="audit-log-to">
            结束时间
            <input
              id="audit-log-to"
              type="datetime-local"
              value={toInput}
              onChange={(event) => setToInput(event.target.value)}
              className="mt-1 min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <button
            type="button"
            onClick={handleApplyTimeRange}
            className="inline-flex min-h-touch items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            <Filter className="h-4 w-4" aria-hidden="true" />
            应用时间范围
          </button>

          <button
            type="button"
            onClick={handleClearTimeRange}
            className="min-h-touch rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
          >
            清空时间
          </button>
        </div>
      </header>

      <div className="p-4">
        {isLoading && (
          <div
            className="rounded-md border border-border bg-muted p-4 text-sm text-muted-foreground"
            role="status"
            aria-label="审计日志加载状态"
          >
            加载中...
          </div>
        )}

        {!isLoading && error && (
          <div
            className="rounded-md border border-danger/30 bg-danger/5 p-4 text-sm text-danger"
            role="status"
            aria-label="审计日志错误"
          >
            {error}
          </div>
        )}

        {!isLoading && !error && !hasSourceRows && (
          <div
            className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground"
            role="status"
            aria-label="审计日志空状态"
          >
            暂无审计日志
          </div>
        )}

        {!isLoading && !error && hasSourceRows && !hasRows && (
          <div
            className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground"
            role="status"
            aria-label="审计日志筛选空状态"
          >
            当前筛选无结果
          </div>
        )}

        {!isLoading && !error && hasRows && (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="min-w-full text-left text-sm" aria-label="审计日志表格">
              <thead className="bg-muted text-muted-foreground">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 font-medium" scope="col">
                    时间
                  </th>
                  <th className="px-4 py-3 font-medium" scope="col">
                    动作
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium" scope="col">
                    Actor
                  </th>
                  <th className="px-4 py-3 font-medium" scope="col">
                    Resource
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium" scope="col">
                    来源 IP
                  </th>
                  <th className="px-4 py-3 font-medium" scope="col">
                    User Agent
                  </th>
                  <th className="px-4 py-3 font-medium" scope="col">
                    Metadata
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={item.id} className="border-t border-border align-top">
                    <td className="whitespace-nowrap px-4 py-3">{formatDateTime(item.created_at)}</td>
                    <td className="min-w-[180px] max-w-[20rem] px-4 py-3">
                      <div className="break-words font-medium">{safeText(item.action)}</div>
                      <div className="mt-1 break-all font-mono text-xs text-muted-foreground">
                        {shortId(item.id)}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">{safeText(item.actor)}</td>
                    <td className="min-w-[180px] max-w-[24rem] px-4 py-3">
                      <div className="break-words font-medium">{safeText(item.resource_type)}</div>
                      <div className="mt-1 break-all font-mono text-xs text-muted-foreground">
                        {safeText(item.resource_id)}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">{safeText(item.ip_address)}</td>
                    <td className="min-w-[220px] max-w-[28rem] px-4 py-3">
                      <span className="break-words">{safeText(item.user_agent)}</span>
                    </td>
                    <td className="min-w-[260px] max-w-[34rem] px-4 py-3">
                      <MetadataSummary metadata={item.metadata} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="mt-4 flex flex-col gap-3 text-sm md:flex-row md:items-center md:justify-between">
          <div className="text-muted-foreground">
            {nextCursor ? "还有更多记录" : "已到达当前窗口末尾"}
          </div>
          <button
            type="button"
            disabled={!nextCursor || !onLoadNext}
            onClick={handleLoadNext}
            className="inline-flex min-h-touch w-fit items-center justify-center gap-2 rounded-md border border-border px-4 py-2 font-semibold hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            下一页
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </footer>
      </div>
    </section>
  );
}

function MetadataSummary({ metadata }: { metadata: AuditLogMetadata }): JSX.Element {
  const entries = flattenMetadata(metadata).slice(0, MAX_METADATA_ENTRIES);
  if (entries.length === 0) {
    return <span className="text-muted-foreground">-</span>;
  }
  const remaining = Math.max(0, flattenMetadata(metadata).length - entries.length);
  return (
    <dl className="space-y-2">
      {entries.map((entry) => (
        <div key={entry.path} className="min-w-0">
          <dt className="break-all font-mono text-xs text-muted-foreground">{entry.path}</dt>
          <dd className="mt-0.5 break-words text-sm">{entry.value}</dd>
        </div>
      ))}
      {remaining > 0 && (
        <div className="text-xs text-muted-foreground">还有 {remaining} 项 metadata 未展开</div>
      )}
    </dl>
  );
}

function flattenMetadata(
  value: unknown,
  path = "",
  depth = 0,
): Array<{ path: string; value: string }> {
  if (depth > 3) {
    return [{ path: path || "value", value: summarizeValue(value, path) }];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return [{ path: path || "value", value: "[]" }];
    return value.flatMap((item, index) => flattenMetadata(item, `${path}[${index}]`, depth + 1));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return [{ path: path || "metadata", value: "{}" }];
    return entries.flatMap(([key, nested]) => {
      const nextPath = path ? `${path}.${key}` : key;
      if (isSensitiveKey(key)) {
        return [{ path: nextPath, value: "[REDACTED]" }];
      }
      return flattenMetadata(nested, nextPath, depth + 1);
    });
  }
  return [{ path: path || "value", value: summarizeValue(value, path) }];
}

function summarizeValue(value: unknown, path: string): string {
  const leafKey = path.split(".").pop()?.replace(/\[\d+\]$/, "") ?? path;
  if (isSensitiveKey(leafKey)) return "[REDACTED]";
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") {
    return maskString(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return truncate(JSON.stringify(value));
}

function isSensitiveKey(key: string): boolean {
  return !SAFE_METADATA_KEYS.has(key) && SENSITIVE_KEY_PATTERN.test(key);
}

function maskString(value: string): string {
  if (
    value === "[REDACTED]" ||
    BEARER_PATTERN.test(value) ||
    API_KEY_PATTERN.test(value) ||
    JWT_PATTERN.test(value) ||
    SECRET_VALUE_PATTERN.test(value)
  ) {
    return "[REDACTED]";
  }
  return truncate(value);
}

function searchableText(item: AuditLogTableItem): string {
  return [
    item.actor,
    item.action,
    item.resource_type,
    item.resource_id,
    item.ip_address,
    item.user_agent,
    ...flattenMetadata(item.metadata).flatMap((entry) => [entry.path, entry.value]),
  ]
    .filter((value): value is string => typeof value === "string")
    .join(" ")
    .toLowerCase();
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function toDateTimeLocalValue(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function dateTimeLocalToIso(value: string): string | undefined {
  if (!value.trim()) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
}

function safeText(value: string | null | undefined): string {
  if (!value) return "-";
  return value;
}

function shortId(value: string): string {
  if (value.length <= 12) return value;
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function truncate(value: string): string {
  if (value.length <= MAX_VALUE_LENGTH) return value;
  return `${value.slice(0, MAX_VALUE_LENGTH)}...`;
}
