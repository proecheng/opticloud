"use client";
/** RFC7807ErrorPanel (Tier 2, Story 8.B.4).
 *
 * Presentation-only renderer for RFC 7807 problem details with FG1.3
 * errors[] detail and O7 next_action_url recovery.
 */

import { AlertTriangle, ArrowRight, CircleHelp, ListChecks } from "lucide-react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface RFC7807ErrorDetail {
  field_path: string;
  value?: unknown;
  constraint: string;
  remediation_hint_key: string;
}

export interface RFC7807ErrorPayload {
  type?: string;
  title: string;
  status: number;
  detail: string;
  errors?: RFC7807ErrorDetail[];
  instance?: string;
  request_id?: string;
  trace_id?: string;
  next_action_url?: string;
}

export interface RFC7807ErrorPanelProps {
  payload: RFC7807ErrorPayload;
  remediationMessages?: Record<string, string>;
  nextActionLabel?: string;
  ariaLabel?: string;
  liveRegion?: "polite" | "assertive";
  className?: string;
}

const DEFAULT_NEXT_ACTION_LABEL = "下一步操作";
const VALUE_PREVIEW_LIMIT = 120;

const SENSITIVE_TEXT_PATTERN =
  /(sk-[a-z0-9_-]{4,}|api[_\s-]?key|bearer\s+|authorization|cookie|password|passwd|secret|token|provider[_\s-]?payload|traceback|[a-z]:\\|\/tmp\/|\/var\/)/i;

export function RFC7807ErrorPanel({
  payload,
  remediationMessages = {},
  nextActionLabel = DEFAULT_NEXT_ACTION_LABEL,
  ariaLabel,
  liveRegion = "assertive",
  className,
}: RFC7807ErrorPanelProps): JSX.Element {
  const a11y = useA11y({
    ariaLabel: ariaLabel ?? `error.rfc7807.${payload.status}`,
    liveRegion,
    role: "alert",
  });
  const safeNextActionUrl = safeActionUrl(payload.next_action_url);
  const safeNextActionLabel = nextActionLabel.trim() || DEFAULT_NEXT_ACTION_LABEL;
  const details = payload.errors ?? [];
  const metadata = buildMetadata(payload);

  return (
    <section
      {...a11y.attrs}
      ref={a11y.ref}
      className={cn(
        "rounded-md border border-danger bg-background text-foreground",
        "p-4 shadow-sm",
        className,
      )}
      data-testid="rfc7807-panel"
      data-status={payload.status}
    >
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 text-danger">
            <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
            <h3 className="break-words text-base font-semibold">
              [{payload.status}] {payload.title}
            </h3>
          </div>
          <p className="mt-2 break-words text-sm">{payload.detail}</p>
        </div>
        {safeNextActionUrl && (
          <a
            href={safeNextActionUrl}
            className="inline-flex min-h-touch w-fit shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            data-testid="next-action-url"
          >
            {safeNextActionLabel}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </a>
        )}
      </header>

      {metadata.length > 0 && (
        <dl className="mt-4 grid gap-x-4 gap-y-2 border-t border-border pt-3 text-xs sm:grid-cols-2">
          {metadata.map(({ label, value }) => (
            <div key={label} className="min-w-0">
              <dt className="sr-only">{label}</dt>
              <dd className="break-words font-mono text-muted-foreground">
                {label}: {value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {details.length > 0 && (
        <section className="mt-4 border-t border-border pt-3" aria-label="字段错误详情">
          <div className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
            <ListChecks className="h-4 w-4 text-danger" aria-hidden="true" />
            字段错误
          </div>
          <ul className="space-y-3">
            {details.map((detail, index) => {
              const valuePreview = safeValuePreview(detail.value, detail.field_path);
              return (
                <li
                  key={`${detail.field_path}-${index}`}
                  className="min-w-0 border-l-2 border-danger/60 pl-3"
                >
                  <div className="break-words font-mono text-xs font-semibold text-primary">
                    {detail.field_path}
                  </div>
                  <div className="mt-1 break-words text-sm">{detail.constraint}</div>
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex min-w-0 items-center gap-1 break-words">
                      <CircleHelp className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      {remediationMessages[detail.remediation_hint_key] ??
                        detail.remediation_hint_key}
                    </span>
                    {valuePreview && (
                      <span className="min-w-0 break-words font-mono">
                        value: {valuePreview}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </section>
  );
}

function buildMetadata(payload: RFC7807ErrorPayload): Array<{ label: string; value: string }> {
  const metadata: Array<{ label: string; value?: string }> = [
    { label: "request", value: payload.request_id },
    { label: "trace", value: payload.trace_id },
    { label: "type", value: payload.type },
    { label: "instance", value: payload.instance },
  ];
  return metadata.flatMap((item) =>
    typeof item.value === "string" && item.value.trim()
      ? [{ label: item.label, value: safeTextPreview(item.value) }]
      : [],
  );
}

function safeActionUrl(value: string | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) return trimmed;
  try {
    const url = new URL(trimmed);
    if (url.protocol === "https:") return trimmed;
    if (
      url.protocol === "http:" &&
      (url.hostname === "localhost" || url.hostname === "127.0.0.1")
    ) {
      return trimmed;
    }
  } catch {
    return null;
  }
  return null;
}

function safeValuePreview(value: unknown, fieldPath: string): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (typeof value !== "string") return "复杂值已隐藏";
  if (SENSITIVE_TEXT_PATTERN.test(fieldPath) || SENSITIVE_TEXT_PATTERN.test(value)) {
    return "已隐藏敏感值";
  }
  return safeTextPreview(value);
}

function safeTextPreview(value: string): string {
  if (SENSITIVE_TEXT_PATTERN.test(value)) return "已隐藏敏感值";
  return value.length > VALUE_PREVIEW_LIMIT
    ? `${value.slice(0, VALUE_PREVIEW_LIMIT)}...`
    : value;
}
