"use client";
/** ChargeModal (Tier 1, Story 5.A.1).
 *
 * Confirmation modal for Credits charges. Shows amount, current balance,
 * post-charge balance (RED if negative), confirm/cancel buttons.
 *
 * AC3: parent owns HTTP — modal just renders + fires callbacks.
 * AC6: parent passes `error` prop on 422 insufficient; Confirm stays disabled.
 *
 * Mirrors ConfirmationModal's Radix DialogPrimitive pattern (DR4 lock).
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface ChargeModalProps {
  open: boolean;
  amount: number;
  currency: string;
  balance: number;
  purpose: string;
  referenceId: string;
  onConfirm: () => Promise<void> | void;
  onCancel: () => void;
  isLoading?: boolean;
  error?: string;
  /** i18n-friendly aria-label. */
  ariaLabel?: string;
}

function formatMoney(n: number, currency: string): string {
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n).toFixed(2);
  return `${sign}¥${abs}` + (currency !== "CNY" ? ` ${currency}` : "");
}

export function ChargeModal({
  open,
  amount,
  currency,
  balance,
  purpose,
  referenceId,
  onConfirm,
  onCancel,
  isLoading = false,
  error,
  ariaLabel = "Charge confirmation",
}: ChargeModalProps): JSX.Element | null {
  const a11y = useA11y({
    ariaLabel,
    trapFocus: true,
    escapeToClose: isLoading ? undefined : onCancel,
    restoreFocus: true,
  });

  if (!open) return null;

  const balanceAfter = balance - amount;
  const insufficient = balanceAfter < 0;
  const confirmDisabled = isLoading || insufficient;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && !isLoading && onCancel()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50 animate-fade-in" />
        <DialogPrimitive.Content asChild>
          <div
            {...a11y.attrs}
            ref={a11y.ref}
            className={cn(
              "fixed left-1/2 top-1/2 z-50 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2",
              "rounded-lg border-2 bg-background p-6 shadow-lg animate-fade-in",
              insufficient ? "border-danger" : "border-primary",
            )}
            data-testid="charge-modal"
            data-reference-id={referenceId}
          >
            <DialogPrimitive.Title className="text-lg font-semibold">
              Confirm charge / 确认扣费
            </DialogPrimitive.Title>
            <DialogPrimitive.Description className="mt-1 text-sm text-muted-foreground">
              {purpose}
            </DialogPrimitive.Description>

            <div className="mt-4 space-y-2">
              <div className="text-2xl font-bold" data-testid="charge-amount">
                {formatMoney(amount, currency)}
              </div>
              <div className="text-sm">
                Current balance:{" "}
                <span data-testid="charge-balance-before">
                  {formatMoney(balance, currency)}
                </span>
              </div>
              <div className="text-sm">
                After this charge:{" "}
                <span
                  data-testid="charge-balance-after"
                  className={cn(insufficient && "text-danger font-semibold")}
                >
                  {formatMoney(balanceAfter, currency)}
                </span>
              </div>
              {insufficient && (
                <div className="text-sm text-danger" data-testid="charge-warning">
                  Insufficient balance to complete this charge.
                </div>
              )}
              {error && (
                <div
                  className="mt-2 rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger"
                  data-testid="charge-error"
                >
                  {error}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={onCancel}
                disabled={isLoading}
                className="min-h-touch min-w-touch rounded-md border border-border px-4 py-2 hover:bg-muted disabled:opacity-50"
                data-testid="charge-cancel"
              >
                Cancel / 取消
              </button>
              <button
                type="button"
                onClick={() => void onConfirm()}
                disabled={confirmDisabled}
                className={cn(
                  "min-h-touch min-w-touch rounded-md px-4 py-2 text-white",
                  confirmDisabled ? "bg-muted-foreground" : "bg-primary hover:bg-primary/90",
                )}
                data-testid="charge-confirm"
              >
                {isLoading ? "Charging..." : "Confirm and charge"}
              </button>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
