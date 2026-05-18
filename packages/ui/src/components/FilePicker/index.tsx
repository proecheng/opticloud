"use client";
/** FilePicker (Tier 1, S3 fix shared with ExcelDropZone).
 *
 * Generic file input — used by Chat (N8) + Console Excel (E11).
 * packages/ui 单源 (Sally S3 fix).
 */
import { type ChangeEvent, useRef } from "react";

import { useA11y } from "../../hooks/useA11y";

export interface FilePickerProps {
  /** Allowed MIME types or extensions (e.g. ".csv,.xlsx,application/json"). */
  accept?: string;
  /** Max size in bytes (default 5 MB per FR E11 + FR N8). */
  maxSizeBytes?: number;
  onFile: (file: File) => void;
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
      // CRG13 actionable hint
      const sizeMB = (file.size / 1024 / 1024).toFixed(1);
      const maxMB = (maxSizeBytes / 1024 / 1024).toFixed(0);
      // biome-ignore lint/suspicious/noConsole: dev-only stub; real UI shows Modal hint
      console.warn(
        `[FilePicker] 文件 ${sizeMB}MB > ${maxMB}MB 上限。请：① 删除多余 sheet ② 拆分为 2 个文件 ③ 转 CSV (≤10MB)`,
      );
      alert(`文件过大 (${sizeMB}MB > ${maxMB}MB)`);
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
