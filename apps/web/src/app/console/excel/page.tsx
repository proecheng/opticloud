/** /console/excel — 老张 Excel upload surface (Story 3.E.1 + 3.E.2).
 *
 * State machine:
 *   idle → received (3.E.1)
 *   received → detecting (parse + heuristic detect)
 *   detecting → detected (Confirm Modal with recommendation + alternatives)
 *   detecting → too_many_rows (FR E11 50K cap rejection)
 *   detecting → parse_error (corrupt xlsx)
 *   detected → confirmed (placeholder handoff card for 3.E.3-5)
 *   any → idle (reset button)
 *
 * Parsing is browser-side (`read-excel-file/browser`); File never leaves the
 * browser — privacy preserved for 老张's 制造业 .xlsx workbooks.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  type ExcelRejectReason,
  ConfirmationModal,
  ExcelDropZone,
  LoadingShimmer,
  StatusCard,
} from "@opticloud/ui";

import { type ExcelWorkbookSummary, parseExcel } from "@/lib/excel";
import {
  type DetectedTaskType,
  type DetectionResult,
  TASK_LABEL,
  detectTaskType,
} from "@/lib/task-type-detect";

const MAX_DATA_ROWS = 50_000;

type ExcelState =
  | { kind: "idle" }
  | { kind: "received"; file: File }
  | { kind: "detecting"; file: File }
  | {
      kind: "detected";
      file: File;
      summary: ExcelWorkbookSummary;
      detection: DetectionResult;
    }
  | {
      kind: "confirmed";
      file: File;
      summary: ExcelWorkbookSummary;
      taskType: DetectedTaskType;
      overrodeFrom: DetectedTaskType | null;
    }
  | {
      kind: "too_many_rows";
      file: File;
      rowCount: number;
    }
  | { kind: "parse_error"; file: File; message: string }
  | { kind: "rejected"; reason: ExcelRejectReason };

function ReceivedCard({
  file,
  onParsed,
}: {
  file: File;
  onParsed: (next: ExcelState) => void;
}): JSX.Element {
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const summary = await parseExcel(file);
        if (cancelled) return;
        if (summary.totalRows > MAX_DATA_ROWS) {
          onParsed({ kind: "too_many_rows", file, rowCount: summary.totalRows });
          return;
        }
        const detection = detectTaskType(summary);
        onParsed({ kind: "detected", file, summary, detection });
      } catch (err) {
        if (cancelled) return;
        onParsed({
          kind: "parse_error",
          file,
          message: (err as Error).message || "无法解析此文件",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file, onParsed]);

  const sizeMB = (file.size / 1024 / 1024).toFixed(2);

  return (
    <div className="space-y-3" data-testid="excel-received-card">
      <StatusCard
        variant="ok"
        title="✅ 已收到您的 Excel 文件"
        description={`${file.name} · ${sizeMB} MB`}
        ariaLabel="console.excel.received"
        icon="📊"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4">
        <div className="mb-2 text-sm text-muted-foreground">解析中... 正在识别 task_type</div>
        <LoadingShimmer variant="line" />
        <LoadingShimmer variant="line" />
      </div>
    </div>
  );
}

function DetectedModal({
  detection,
  onConfirm,
  onCancel,
}: {
  detection: DetectionResult;
  onConfirm: (taskType: DetectedTaskType) => void;
  onCancel: () => void;
}): JSX.Element {
  const [selected, setSelected] = useState<DetectedTaskType>(detection.taskType);
  const confidencePct = (detection.confidence * 100).toFixed(0);

  const choices: DetectedTaskType[] = [
    "vrptw",
    "schedule",
    "inventory",
    "lp",
    "unknown",
  ];

  return (
    <ConfirmationModal
      open
      onClose={onCancel}
      onConfirm={() => onConfirm(selected)}
      variant="generic"
      ariaLabel="console.excel.confirm_task_type"
      title={`自动检测：${TASK_LABEL[detection.taskType]}`}
      description={detection.reasoning}
      confirmLabel="确认"
      cancelLabel="取消"
      body={
        <div className="space-y-3 text-sm">
          <div data-testid="detection-confidence" className="text-xs text-muted-foreground">
            可信度 {confidencePct}%
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              不对？手动选择 task_type
            </span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value as DetectedTaskType)}
              data-testid="detection-override-select"
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
            >
              {choices.map((c) => (
                <option key={c} value={c}>
                  {TASK_LABEL[c]}
                  {c === detection.taskType ? " (系统推荐)" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      }
    />
  );
}

function ConfirmedCard({
  taskType,
  overrodeFrom,
  onReset,
}: {
  taskType: DetectedTaskType;
  overrodeFrom: DetectedTaskType | null;
  onReset: () => void;
}): JSX.Element {
  return (
    <div className="space-y-3" data-testid="excel-confirmed-card">
      <StatusCard
        variant="ok"
        title={`✅ task_type 已确认：${TASK_LABEL[taskType]}`}
        description={
          overrodeFrom
            ? `您选择了 ${TASK_LABEL[taskType]}，覆盖系统推荐 ${TASK_LABEL[overrodeFrom]}`
            : "下一步由后续 story (3.E.3-5) 接管 — 将路由到对应业务模板。"
        }
        ariaLabel="console.excel.confirmed"
        icon="🎯"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        📋 下一步：3.E.3 (VRPTW) / 3.E.4 (Schedule) / 3.E.5 (Inventory) 将在 PR #21+ 接管这里的
        task_type 路由 + 字段映射 + 求解触发。
      </div>
      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重新选择文件
      </button>
    </div>
  );
}

function TooManyRowsCard({
  rowCount,
  onReset,
}: {
  rowCount: number;
  onReset: () => void;
}): JSX.Element {
  return (
    <div className="space-y-3" data-testid="excel-too-many-rows-card">
      <StatusCard
        variant="warning"
        title="文件行数过多"
        description={`共 ${rowCount.toLocaleString()} 行 > 50,000 行上限`}
        ariaLabel="console.excel.too_many_rows"
        icon="⚠️"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
        <p className="mb-2 font-medium">试试这三步：</p>
        <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
          <li>① 按时间段拆分（按月/季度/年导出）</li>
          <li>② 按地区/客户拆分（保留核心子集）</li>
          <li>③ 截取关键时段（仅保留最近 N 个月）</li>
        </ul>
        <p className="mt-3">
          <Link href="/docs/excel-upload-faq" className="text-primary hover:underline">
            📖 看教程：如何拆分大 Excel
          </Link>
        </p>
      </div>
      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重试
      </button>
    </div>
  );
}

function ParseErrorCard({
  message,
  onReset,
}: {
  message: string;
  onReset: () => void;
}): JSX.Element {
  return (
    <div className="space-y-3" data-testid="excel-parse-error-card">
      <StatusCard
        variant="error"
        title="无法解析此文件"
        description={message}
        ariaLabel="console.excel.parse_error"
        icon="🚫"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        请确认文件确为有效的 .xlsx 工作簿。若问题持续，请尝试在 Excel 中
        "另存为 .xlsx" 再上传。
      </div>
      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重试
      </button>
    </div>
  );
}

function RejectedCard({
  reason,
  onReset,
}: {
  reason: ExcelRejectReason;
  onReset: () => void;
}): JSX.Element {
  const title = reason.code === "too_large" ? "文件过大" : "不支持的文件类型";
  const variant = reason.code === "too_large" ? "warning" : "error";

  return (
    <div className="space-y-3" data-testid="excel-rejected-card">
      <StatusCard
        variant={variant}
        title={title}
        description={reason.message}
        ariaLabel={`console.excel.rejected.${reason.code}`}
        icon={reason.code === "too_large" ? "⚠️" : "🚫"}
      />

      {reason.code === "too_large" && (
        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <p className="mb-2 font-medium">试试这三步：</p>
          <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
            <li>① 删除多余 sheet（保留只参与求解的工作表）</li>
            <li>② 拆分为 2 个 .xlsx（按客户 / 时间段 / 部门拆）</li>
            <li>③ 转 CSV (≤10MB) — 我们也支持 .csv 上传（v1 末）</li>
          </ul>
          <p className="mt-3">
            <Link href="/docs/excel-upload-faq" className="text-primary hover:underline">
              📖 看教程：如何拆分大 Excel
            </Link>
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重试
      </button>
    </div>
  );
}

export default function ConsoleExcelPage(): JSX.Element {
  const [state, setState] = useState<ExcelState>({ kind: "idle" });

  const reset = (): void => setState({ kind: "idle" });

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              算法目录
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              注册
            </Link>
          </nav>
        </div>
      </header>

      <section className="bg-muted py-12">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h1 className="text-balance text-3xl font-bold">上传 Excel，自动求解</h1>
          <p className="mt-2 text-balance text-muted-foreground">
            适合 VRPTW / 排班 / 库存预测 — 不写代码，拖一下就行（≤5 MB / 50K 行）
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-8">
        {state.kind === "idle" && (
          <ExcelDropZone
            onFile={(file) => setState({ kind: "received", file })}
            onReject={(reason) => setState({ kind: "rejected", reason })}
          />
        )}

        {state.kind === "received" && (
          <ReceivedCard file={state.file} onParsed={setState} />
        )}

        {state.kind === "detected" && (
          <>
            {/* Keep the received card visible behind the modal for context */}
            <div className="space-y-3" data-testid="excel-received-card">
              <StatusCard
                variant="ok"
                title="✅ 已收到您的 Excel 文件"
                description={`${state.file.name} · ${(state.file.size / 1024 / 1024).toFixed(2)} MB`}
                ariaLabel="console.excel.received"
                icon="📊"
              />
            </div>
            <DetectedModal
              detection={state.detection}
              onConfirm={(taskType) =>
                setState({
                  kind: "confirmed",
                  file: state.file,
                  summary: state.summary,
                  taskType,
                  overrodeFrom:
                    taskType !== state.detection.taskType ? state.detection.taskType : null,
                })
              }
              onCancel={reset}
            />
          </>
        )}

        {state.kind === "confirmed" && (
          <ConfirmedCard
            taskType={state.taskType}
            overrodeFrom={state.overrodeFrom}
            onReset={reset}
          />
        )}

        {state.kind === "too_many_rows" && (
          <TooManyRowsCard rowCount={state.rowCount} onReset={reset} />
        )}

        {state.kind === "parse_error" && (
          <ParseErrorCard message={state.message} onReset={reset} />
        )}

        {state.kind === "rejected" && (
          <RejectedCard reason={state.reason} onReset={reset} />
        )}
      </section>

      <footer className="mt-12 border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>
          想用 cURL / Postman / SDK 直接调？{" "}
          <Link href="/algorithms" className="text-primary hover:underline">
            看算法目录 →
          </Link>
        </p>
      </footer>
    </main>
  );
}
