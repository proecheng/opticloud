"use client";
/** Toast (Tier 1). aria-live by sentence (UX-DR5 + AA7). */
import { useEffect, useState } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type ToastVariant = "success" | "warning" | "danger" | "info";

export interface ToastProps {
  variant?: ToastVariant;
  message: string;
  ariaLabel: string;
  durationMs?: number;
  onDismiss?: () => void;
}

const variantStyles: Record<ToastVariant, string> = {
  success: "bg-success text-success-foreground",
  warning: "bg-warning text-warning-foreground",
  danger: "bg-danger text-danger-foreground",
  info: "bg-primary text-primary-foreground",
};

export function Toast({ variant = "info", message, ariaLabel, durationMs = 4000, onDismiss }: ToastProps): JSX.Element | null {
  const [visible, setVisible] = useState(true);
  const a11y = useA11y({ ariaLabel, liveRegion: "polite" });

  useEffect(() => {
    const t = setTimeout(() => {
      setVisible(false);
      onDismiss?.();
    }, durationMs);
    return () => clearTimeout(t);
  }, [durationMs, onDismiss]);

  if (!visible) return null;

  return (
    <div
      {...a11y.attrs}
      className={cn(
        "fixed bottom-4 right-4 z-50 max-w-sm rounded-md px-4 py-3 shadow-lg animate-slide-up",
        variantStyles[variant],
      )}
      data-testid="toast"
      data-variant={variant}
    >
      {message}
    </div>
  );
}
