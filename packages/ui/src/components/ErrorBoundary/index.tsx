"use client";
/** ErrorBoundary (Tier 1). FG1.3 RFC 7807 errors[] panel + next_action_url. */
import { Component, type ReactNode } from "react";

interface ErrorDetail {
  field_path: string;
  value: unknown;
  constraint: string;
  remediation_hint_key: string;
}

export interface RFC7807ErrorPayload {
  type?: string;
  title: string;
  status: number;
  detail: string;
  errors?: ErrorDetail[];
  next_action_url?: string;
  request_id?: string;
  trace_id?: string;
}

interface ErrorBoundaryProps {
  /** Fallback when child throws. */
  fallback?: ReactNode;
  /** RFC 7807 payload from API response (FG1.3). */
  rfc7807?: RFC7807ErrorPayload;
  children?: ReactNode;
  /** Called when error is caught (logging hook). */
  onError?: (error: Error, info: { componentStack: string }) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    this.props.onError?.(error, { componentStack: info.componentStack ?? "" });
  }

  render(): ReactNode {
    if (this.props.rfc7807) {
      return <RFC7807Panel payload={this.props.rfc7807} />;
    }
    if (this.state.hasError) {
      return this.props.fallback ?? <DefaultFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}

function DefaultFallback({ error }: { error?: Error }): JSX.Element {
  return (
    <div
      role="alert"
      aria-label="error.boundary.fallback"
      className="rounded-lg border border-danger bg-danger/5 p-4 text-sm"
      data-testid="error-boundary-fallback"
    >
      <h3 className="mb-2 font-semibold text-danger">出错了</h3>
      <p className="text-muted-foreground">{error?.message ?? "未知错误，请刷新重试。"}</p>
    </div>
  );
}

/** RFC 7807 panel — FG1.3 errors[] detail rendering. */
export function RFC7807Panel({ payload }: { payload: RFC7807ErrorPayload }): JSX.Element {
  return (
    <div
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      aria-label={`error.rfc7807.${payload.status}`}
      className="rounded-lg border border-danger bg-background p-4"
      data-testid="rfc7807-panel"
      data-status={payload.status}
    >
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="font-semibold text-danger">
          [{payload.status}] {payload.title}
        </h3>
        {payload.trace_id && (
          <code className="font-mono text-xs text-muted-foreground">
            trace: {payload.trace_id}
          </code>
        )}
      </div>
      <p className="text-sm text-foreground">{payload.detail}</p>

      {payload.errors && payload.errors.length > 0 && (
        <ul className="mt-3 space-y-1 rounded bg-muted p-2 text-xs">
          {payload.errors.map((e, i) => (
            <li key={`${e.field_path}-${i}`} className="font-mono">
              <span className="text-primary">{e.field_path}</span>
              <span className="text-muted-foreground"> → </span>
              <span>{e.constraint}</span>
              {e.value !== null && e.value !== undefined && (
                <span className="ml-1 text-muted-foreground">(value: {String(e.value)})</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {payload.next_action_url && (
        <a
          href={payload.next_action_url}
          className="mt-3 inline-block rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary-600"
          data-testid="next-action-url"
        >
          → 下一步操作
        </a>
      )}
    </div>
  );
}
