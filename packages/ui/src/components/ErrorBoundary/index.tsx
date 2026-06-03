"use client";
/** ErrorBoundary (Tier 1). FG1.3 RFC 7807 errors[] panel + next_action_url. */
import { Component, type ReactNode } from "react";

import {
  RFC7807ErrorPanel,
  type RFC7807ErrorPayload,
} from "../RFC7807ErrorPanel";

export { RFC7807ErrorPanel as RFC7807Panel };
export type { RFC7807ErrorPayload } from "../RFC7807ErrorPanel";

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
      return <RFC7807ErrorPanel payload={this.props.rfc7807} />;
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
