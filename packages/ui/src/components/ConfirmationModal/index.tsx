"use client";
/** ConfirmationModal (Tier 1, Story 0.9 stub).
 *
 * Source: UX Spec Step 11 Component Strategy.
 * AC: Story 1.1b J1 Vertical Slice P5 警示 + ESC 关闭 + 焦点陷阱 + aria-label
 *      (W3 fix + S-S1 packages/ui PR-gate)
 *
 * 5 P5 警示分支:
 *   - p5_alert: T5/T6/P5 调用警示
 *   - balance_warn: 余额 < 预估 (FR B6)
 *   - signup_success: 注册成功 + API Key (Story 1.1b)
 *   - destructive: 删除账户 / 吊销 key (FR A6)
 *   - generic: fallback
 */

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type ConfirmationVariant =
  | "p5_alert"
  | "balance_warn"
  | "signup_success"
  | "destructive"
  | "generic";

export interface ConfirmationModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  variant?: ConfirmationVariant;
  /** i18n key for ARIA label (required, UX-DR5). */
  ariaLabel: string;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Additional CTA between title + buttons (e.g. cURL preview in Story 1.1b). */
  body?: ReactNode;
}

const variantStyles: Record<ConfirmationVariant, string> = {
  p5_alert: "border-warning",
  balance_warn: "border-warning",
  signup_success: "border-primary",
  destructive: "border-danger",
  generic: "border-border",
};

/** Tier 1 v1 stub — minimal viable; full P5 警示 visual treatment in business Epic. */
export function ConfirmationModal({
  open,
  onClose,
  onConfirm,
  variant = "generic",
  ariaLabel,
  title,
  description,
  body,
  confirmLabel = "确认",
  cancelLabel = "取消",
}: ConfirmationModalProps): JSX.Element | null {
  const a11y = useA11y({
    ariaLabel,
    trapFocus: true,
    escapeToClose: onClose,
    restoreFocus: true,
  });

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent asChild>
        <div
          {...a11y.attrs}
          ref={a11y.ref}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-w-md -translate-x-1/2 -translate-y-1/2",
            "rounded-lg border-2 bg-background p-6 shadow-lg animate-fade-in",
            variantStyles[variant],
          )}
          data-testid="confirmation-modal"
          data-variant={variant}
        >
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold">{title}</DialogTitle>
            {description && (
              <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            )}
          </DialogHeader>
          {body && <div className="mt-4">{body}</div>}
          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="min-h-touch min-w-touch rounded-md border border-border px-4 py-2 hover:bg-muted"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="min-h-touch min-w-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
