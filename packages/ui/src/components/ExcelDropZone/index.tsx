"use client";
/** ExcelDropZone (Tier 1). FR E11 老张 + FG1.2 + 老张-2 中文 UX 微调 + CRG13 actionable hint.
 *
 * S3 fix: 共用 FilePicker (packages/ui 单源).
 */
import { type DragEvent, useState } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

import { FilePicker } from "../FilePicker";

export interface ExcelDropZoneProps {
  onFile: (file: File) => void;
  ariaLabel?: string;
  /** Max size in bytes (default 5 MB per FR E11). */
  maxSizeBytes?: number;
}

export function ExcelDropZone({
  onFile,
  ariaLabel = "excel.drop_zone",
  maxSizeBytes = 5 * 1024 * 1024,
}: ExcelDropZoneProps): JSX.Element {
  const [isOver, setIsOver] = useState(false);
  const a11y = useA11y({ ariaLabel });

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
    if (file.size > maxSizeBytes) {
      const sizeMB = (file.size / 1024 / 1024).toFixed(1);
      // CRG13 老张-friendly actionable hint
      alert(`已收到您的 Excel 文件，但 ${sizeMB}MB 超过 5MB 上限。请：① 删除多余 sheet ② 拆分为 2 个 .xlsx ③ 转 CSV (≤10MB)`);
      return;
    }
    onFile(file);
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
      <p className="mb-2 text-lg font-medium">拖拽 .xlsx 到这里</p>
      <p className="mb-4 text-sm text-muted-foreground">
        ≤5 MB / 50K rows · 自动识别 VRPTW / Schedule / Inventory 模板
      </p>
      <FilePicker
        accept=".xlsx"
        maxSizeBytes={maxSizeBytes}
        onFile={onFile}
        ariaLabel={`${ariaLabel}.fallback`}
        label="或点击选择文件"
      />
    </div>
  );
}
