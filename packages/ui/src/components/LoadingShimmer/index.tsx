"use client";
/** LoadingShimmer (Tier 1). UX Spec Step 12 Loading & Skeleton pattern. */
import { cn } from "../../lib/cn";

export interface LoadingShimmerProps {
  className?: string;
  /** Visual variant: line (default), avatar, card. */
  variant?: "line" | "avatar" | "card";
}

export function LoadingShimmer({ className, variant = "line" }: LoadingShimmerProps): JSX.Element {
  const variantClass = {
    line: "h-4 w-full rounded",
    avatar: "h-10 w-10 rounded-full",
    card: "h-32 w-full rounded-lg",
  }[variant];

  return (
    <div
      role="status"
      aria-label="loading.shimmer"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        "animate-shimmer-pulse bg-muted",
        variantClass,
        className,
      )}
      data-testid="loading-shimmer"
      data-variant={variant}
    />
  );
}
