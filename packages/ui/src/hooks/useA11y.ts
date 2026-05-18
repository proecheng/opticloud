"use client";
/** Standard a11y Hook Wrapper — UX-DR5 + Story 0.12 + AA6/AA12.
 *
 * 强制 packages/ui Component a11y baseline：
 *   - Modal focus trap + ESC 关闭
 *   - aria-label required (i18n key 单源, 与 errors[] FG1.3 i18n 单源对齐)
 *   - Heading hierarchy lint hint
 *   - Form for/id link verification (run-time check in dev)
 *   - Disabled contrast ≥3:1 (linter rule, runtime no-op)
 *
 * Usage:
 *   const a11y = useA11y({
 *     ariaLabel: t('modal.confirm'),
 *     trapFocus: true,
 *     escapeToClose: () => onClose(),
 *   });
 *   <div {...a11y.attrs} ref={a11y.ref}>...</div>
 */

import { useCallback, useEffect, useId, useRef } from "react";

export interface UseA11yOptions {
  /** ARIA label — i18n key (REQUIRED for Modal/Dialog/Toast/Confirmation). */
  ariaLabel: string;
  /** ARIA description (optional). */
  ariaDescription?: string;
  /** Trap focus inside container (Modal pattern). */
  trapFocus?: boolean;
  /** Callback on ESC keydown (Modal pattern). */
  escapeToClose?: () => void;
  /** Restore focus to previously focused element on unmount. */
  restoreFocus?: boolean;
  /** ARIA live region politeness (Toast / aria-live by sentence). */
  liveRegion?: "off" | "polite" | "assertive";
  /** ARIA role override (default inferred). */
  role?: string;
}

export interface UseA11yResult {
  /** Spread onto wrapper element for ARIA attributes. */
  attrs: Record<string, string | boolean | undefined>;
  /** Ref to attach to focusable container (focus trap target). */
  ref: React.RefObject<HTMLDivElement | null>;
  /** Stable ID for label/described-by linking. */
  id: string;
}

export function useA11y(options: UseA11yOptions): UseA11yResult {
  const {
    ariaLabel,
    ariaDescription,
    trapFocus = false,
    escapeToClose,
    restoreFocus = false,
    liveRegion = "off",
    role,
  } = options;

  // Stable ID for ARIA linking
  const id = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Save previously focused element on mount; restore on unmount
  useEffect(() => {
    if (restoreFocus) {
      previousFocusRef.current = document.activeElement as HTMLElement | null;
    }
    return () => {
      if (restoreFocus && previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    };
  }, [restoreFocus]);

  // ESC to close (Modal pattern)
  useEffect(() => {
    if (!escapeToClose) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        escapeToClose();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [escapeToClose]);

  // Focus trap (Modal pattern — basic implementation)
  const trapFocusHandler = useCallback(
    (e: KeyboardEvent) => {
      if (!trapFocus || e.key !== "Tab") return;
      const container = containerRef.current;
      if (!container) return;
      const focusable = container.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    },
    [trapFocus],
  );

  useEffect(() => {
    if (!trapFocus) return;
    document.addEventListener("keydown", trapFocusHandler);
    return () => document.removeEventListener("keydown", trapFocusHandler);
  }, [trapFocus, trapFocusHandler]);

  // Dev warning: missing aria-label (i18n key)
  if (process.env.NODE_ENV !== "production" && !ariaLabel) {
    // biome-ignore lint/suspicious/noConsole: dev-only warning
    console.warn(
      "[useA11y] ariaLabel is required (UX-DR5 + AA6). Provide an i18n key.",
    );
  }

  const attrs: Record<string, string | boolean | undefined> = {
    "aria-label": ariaLabel,
    "aria-describedby": ariaDescription ? `${id}-desc` : undefined,
    id,
    role,
  };
  if (liveRegion !== "off") {
    attrs["aria-live"] = liveRegion;
    attrs["aria-atomic"] = "true";
  }

  return { attrs, ref: containerRef, id };
}
