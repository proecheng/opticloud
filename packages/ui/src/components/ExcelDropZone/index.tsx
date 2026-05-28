"use client";
/** ExcelDropZone (Tier 1). FR E11 老张 + FG1.2 + 老张-2 中文 UX 微调 + CRG13 actionable hint.
 *
 * S3 fix: 共用 FilePicker (packages/ui 单源).
 *
 * Story 3.E.1 (2026-05-19): API evolution — added `onReject` callback so parent
 * pages can render proper StatusCard hints instead of `alert()`. When `onReject`
 * is not provided we fall back to `console.warn` (stays usable as an isolated
 * stub in Storybook / older callers without breaking).
 *
 * Also added wrong-type rejection: drops that don't have a `.xlsx` suffix are
 * rejected up-front so the parent never sees a .pdf as a "valid file".
 */
import { type DragEvent, useState } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

import { FilePicker } from "../FilePicker";

export type ExcelRejectCode = "too_large" | "wrong_type";

export interface ExcelRejectReason {
  code: ExcelRejectCode;
  message: string;
  sizeMB?: string;
  maxMB?: string;
}

export interface ExcelDropZoneProps {
  onFile: (file: File) => void;
  /** Story 3.E.1 — caller-controlled rejection handler. If omitted, console.warn fallback. */
  onReject?: (reason: ExcelRejectReason) => void;
  ariaLabel?: string;
  /** Max size in bytes (default 5 MB per FR E11). */
  maxSizeBytes?: number;
}

function classifyFile(
  file: File,
  maxSizeBytes: number,
): ExcelRejectReason | null {
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".xlsx")) {
    return {
      code: "wrong_type",
      message: `仅支持 .xlsx 文件，当前是 "${file.name}"。请在 Excel 中"另存为 .xlsx"再上传。`,
    };
  }
  if (file.size > maxSizeBytes) {
    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    const maxMB = (maxSizeBytes / 1024 / 1024).toFixed(0);
    return {
      code: "too_large",
      message: `文件 ${sizeMB}MB 超过 ${maxMB}MB 上限。`,
      sizeMB,
      maxMB,
    };
  }
  return null;
}

export function ExcelDropZone({
  onFile,
  onReject,
  ariaLabel = "excel.drop_zone",
  maxSizeBytes = 5 * 1024 * 1024,
}: ExcelDropZoneProps): JSX.Element {
  const [isOver, setIsOver] = useState(false);
  const a11y = useA11y({ ariaLabel });

  const reportReject = (reason: ExcelRejectReason): void => {
    if (onReject) {
      onReject(reason);
      return;
    }
    // biome-ignore lint/suspicious/noConsole: fallback when caller omits onReject
    console.warn(`[ExcelDropZone] rejected (${reason.code}): ${reason.message}`);
  };

  const handleCandidate = (file: File): void => {
    const reason = classifyFile(file, maxSizeBytes);
    if (reason) {
      reportReject(reason);
      return;
    }
    onFile(file);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsOver(true);
  };
  const onDragLeave = (): void => setIsOver(false);
  const onDrop = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsOver(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    handleCandidate(file);
  };

  return (
    <div
      {...a11y.attrs}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 text-center transition-colors",
        isOver
          ? "border-primary bg-primary/5"
          : "border-border bg-background hover:border-primary/50",
      )}
      data-testid="excel-drop-zone"
    >
      <div className="mb-3 text-4xl" aria-hidden="true">
        📊
      </div>
      {/* 老张-2 中文 UX 微调 — 友好版 Brand Voice "实证克制" */}
      <p className="mb-2 text-lg font-medium">把 .xlsx 拖到这里</p>
      <p className="mb-4 text-sm text-muted-foreground">
        ≤5 MB / 50K 行 · 本地识别 VRPTW / 排班 / 库存预测模板
      </p>
      <FilePicker
        accept=".xlsx"
        maxSizeBytes={maxSizeBytes}
        onFile={handleCandidate}
        onReject={(r) =>
          reportReject({
            code: "too_large",
            message: r.message,
            sizeMB: r.sizeMB,
            maxMB: r.maxMB,
          })
        }
        ariaLabel={`${ariaLabel}.fallback`}
        label="或点击选择文件"
      />
    </div>
  );
}
