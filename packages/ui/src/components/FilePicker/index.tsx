"use client";
/** FilePicker (Tier 1, S3 fix shared with ExcelDropZone).
 *
 * Generic file input — used by Chat (N8) + Console Excel (E11).
 * packages/ui 单源 (Sally S3 fix).
 *
 * Story 3.E.1 (2026-05-19): added `onReject` callback so callers can render
 * proper UI instead of `alert()`. Fallback to `console.warn` when omitted.
 */
import { type ChangeEvent, useRef } from "react";

import { useA11y } from "../../hooks/useA11y";

export interface FilePickerRejectReason {
  code: "too_large";
  sizeMB: string;
  maxMB: string;
  message: string;
}

export interface FilePickerProps {
  /** Allowed MIME types or extensions (e.g. ".csv,.xlsx,application/json"). */
  accept?: string;
  /** Max size in bytes (default 5 MB per FR E11 + FR N8). */
  maxSizeBytes?: number;
  onFile: (file: File) => void;
  /** Story 3.E.1 — caller-controlled rejection handler. If omitted, console.warn fallback. */
  onReject?: (reason: FilePickerRejectReason) => void;
  /** Multi-file? (FR N8 v1 stub: single). */
  multiple?: boolean;
  ariaLabel: string;
  label?: string;
}

export const DEFAULT_MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

export function FilePicker({
  accept = ".csv,.xlsx,.json",
  maxSizeBytes = DEFAULT_MAX_SIZE_BYTES,
  onFile,
  onReject,
  multiple = false,
  ariaLabel,
  label = "选择文件",
}: FilePickerProps): JSX.Element {
  const a11y = useA11y({ ariaLabel });
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handle = (e: ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > maxSizeBytes) {
      const sizeMB = (file.size / 1024 / 1024).toFixed(1);
      const maxMB = (maxSizeBytes / 1024 / 1024).toFixed(0);
      const reason: FilePickerRejectReason = {
        code: "too_large",
        sizeMB,
        maxMB,
        message: `文件 ${sizeMB}MB 超过 ${maxMB}MB 上限。`,
      };
      if (onReject) {
        onReject(reason);
      } else {
        // biome-ignore lint/suspicious/noConsole: fallback when caller omits onReject
        console.warn(`[FilePicker] rejected (too_large): ${reason.message}`);
      }
      // Reset input so the same file can be re-selected after fixing.
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    onFile(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <label
      {...a11y.attrs}
      className="inline-flex min-h-touch min-w-touch cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-4 py-2 hover:bg-muted"
      data-testid="file-picker"
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handle}
        className="sr-only"
        aria-hidden="false"
      />
      <span aria-hidden="true">📎</span>
      <span>{label}</span>
    </label>
  );
}
