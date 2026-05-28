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
import { OptiCloudClientError, submitOptimizationDemo } from "@/lib/api";
import { buildVrptwPayload } from "@/lib/vrptw-template";
import { buildSchedulePayload } from "@/lib/schedule-template";
import { buildInventoryPayload } from "@/lib/inventory-template";
import {
  buildResultWorkbook,
  type ExportablePayload,
  type ExportRequest,
  type ExportResultStatus,
} from "@/lib/excel-export";

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
        description={`${file.name} · ${sizeMB} MB · 正在本地解析，原始文件不会上传`}
        ariaLabel="console.excel.received"
        icon="📊"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4">
        <div className="mb-2 text-sm text-muted-foreground">
          正在本地解析工作簿，原始文件不会上传
        </div>
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
      title={`系统判断：${TASK_LABEL[detection.taskType]}`}
      description={detection.reasoning}
      confirmLabel="确认并继续"
      cancelLabel="取消"
      body={
        <div className="space-y-3 text-sm">
          <div data-testid="detection-confidence" className="text-xs text-muted-foreground">
            可信度 {confidencePct}%
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              如果判断不对，可以手动选择类型
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

type SubmitState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "solved"; objective: number | null; solveSeconds: number }
  | { kind: "not_implemented"; detail: string }
  | { kind: "error"; message: string };

function DownloadResultCard({
  taskType,
  source,
  payload,
  status,
  realResult,
  sourceFilename,
  dataTestId,
}: {
  taskType: "vrptw" | "schedule" | "inventory";
  source: ExcelWorkbookSummary;
  payload: ExportablePayload;
  status: ExportResultStatus;
  realResult?: ExportRequest["realResult"];
  sourceFilename: string;
  dataTestId: string;
}): JSX.Element {
  const [genState, setGenState] = useState<
    { kind: "idle" } | { kind: "generating" } | { kind: "error"; message: string }
  >({ kind: "idle" });

  const handleDownload = async (): Promise<void> => {
    setGenState({ kind: "generating" });
    try {
      const { blob, filename } = await buildResultWorkbook({
        source,
        payload,
        status,
        realResult,
        sourceFilename,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setGenState({ kind: "idle" });
    } catch (err) {
      setGenState({
        kind: "error",
        message: (err as Error).message || "下载失败",
      });
    }
  };

  // Discourage taskType prop from going unused after refactor (kept for downstream filters).
  void taskType;

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => void handleDownload()}
        disabled={genState.kind === "generating"}
        data-testid={dataTestId}
        aria-label="下载 Excel 结果"
        className="min-h-touch rounded-md border border-primary px-4 py-2 text-sm text-primary hover:bg-primary/5 disabled:opacity-50"
      >
        {genState.kind === "generating" ? "正在生成 Excel..." : "📥 下载 Excel 结果"}
      </button>
      {genState.kind === "error" && (
        <p className="text-xs text-red-600">{genState.message}</p>
      )}
    </div>
  );
}

function VrptwPreviewCard({
  file,
  onReset,
}: {
  file: File;
  onReset: () => void;
}): JSX.Element {
  const [state, setState] = useState<
    | { kind: "parsing" }
    | {
        kind: "mapped";
        result: ReturnType<typeof buildVrptwPayload>;
        summary: ExcelWorkbookSummary;
      }
    | { kind: "error"; message: string }
  >({ kind: "parsing" });
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const summary = await parseExcel(file, { includeRows: true });
        if (cancelled) return;
        const result = buildVrptwPayload(summary);
        setState({ kind: "mapped", result, summary });
      } catch (err) {
        if (cancelled) return;
        setState({ kind: "error", message: (err as Error).message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file]);

  const handleSubmit = async (): Promise<void> => {
    if (state.kind !== "mapped" || !state.result.ok) return;
    setSubmitState({ kind: "loading" });
    try {
      const resp = await submitOptimizationDemo(state.result.payload);
      setSubmitState({
        kind: "solved",
        objective: resp.objective,
        solveSeconds: resp.solve_seconds,
      });
    } catch (err) {
      if (err instanceof OptiCloudClientError && err.status === 501) {
        setSubmitState({ kind: "not_implemented", detail: err.detail });
      } else {
        setSubmitState({
          kind: "error",
          message:
            err instanceof OptiCloudClientError
              ? `${err.title}: ${err.detail}`
              : String((err as Error).message),
        });
      }
    }
  };

  if (state.kind === "parsing") {
    return (
      <div className="space-y-3" data-testid="vrptw-preview-card">
        <div className="text-sm text-muted-foreground">正在读取数据行...</div>
        <LoadingShimmer variant="card" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="space-y-3" data-testid="vrptw-preview-card">
        <StatusCard
          variant="error"
          title="读取失败"
          description={state.message}
          ariaLabel="console.excel.vrptw.parse_error"
          icon="🚫"
        />
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

  const result = state.result;
  if (!result.ok) {
    return (
      <div className="space-y-3" data-testid="vrptw-preview-card">
        <StatusCard
          variant="error"
          title="VRPTW 数据校验失败"
          description={`发现 ${result.errors.length} 个问题，请在 Excel 中修正后重试`}
          ariaLabel="console.excel.vrptw.invalid"
          icon="⚠️"
        />
        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
            {result.errors.map((e, i) => (
              <li key={i}>
                <code className="font-mono text-xs">{e.sheet}</code>
                {e.field && (
                  <>
                    {" · "}
                    <code className="font-mono text-xs">{e.field}</code>
                  </>
                )}
                {" — "}
                {e.message}
              </li>
            ))}
          </ul>
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

  return (
    <div className="space-y-3" data-testid="vrptw-preview-card">
      <StatusCard
        variant="ok"
        title={`✅ VRPTW 路线试跑已准备好 — ${result.customer_count} 客户 / ${result.vehicle_count} 车辆`}
        description="数据已通过格式校验。可点击 试跑 提交到路线求解器。"
        ariaLabel="console.excel.vrptw.ready"
        icon="🎯"
      />

      {result.warnings.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}

      <details className="rounded-md border border-border bg-muted/30">
        <summary className="cursor-pointer px-4 py-2 text-sm font-medium">
          📋 查看构建的 JSON 请求
        </summary>
        <pre
          className="overflow-x-auto p-3 font-mono text-xs"
          data-testid="vrptw-payload-json"
        >
          {JSON.stringify(result.payload, null, 2)}
        </pre>
      </details>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={submitState.kind === "loading"}
          data-testid="vrptw-submit-button"
          className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
        >
          {submitState.kind === "loading" ? "求解中..." : "🚀 试跑"}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
          data-testid="excel-reset-button"
        >
          重新选择文件
        </button>
      </div>

      {submitState.kind === "not_implemented" && (
        <div data-testid="vrptw-501-card" className="space-y-2">
          <StatusCard
            variant="info"
            title="VRPTW 路线求解器即将上线 (M2-M3)"
            description={
              `您的数据已通过格式校验（${result.customer_count} 客户 / ${result.vehicle_count} 车辆）。` +
              " 求解器将在后续版本上线，届时本页面将直接返回结果。"
            }
            ariaLabel="console.excel.vrptw.not_implemented"
            icon="🚧"
          />
          <p className="text-sm text-muted-foreground">
            <Link href="/algorithms?tier=T4" className="text-primary hover:underline">
              → 看其它 T4 求解器
            </Link>
          </p>
          <DownloadResultCard
            taskType="vrptw"
            source={state.summary}
            payload={result.payload}
            status="demo"
            sourceFilename={file.name}
            dataTestId="vrptw-download-button"
          />
        </div>
      )}

      {submitState.kind === "solved" && (
        <div className="space-y-2">
          <StatusCard
            variant="ok"
            title="✅ 求解完成"
            description={`耗时 ${submitState.solveSeconds.toFixed(2)}s · 目标值 ${submitState.objective ?? "(N/A)"}`}
            ariaLabel="console.excel.vrptw.solved"
            icon="🎉"
          />
          <DownloadResultCard
            taskType="vrptw"
            source={state.summary}
            payload={result.payload}
            status="solved"
            realResult={{
              objective: submitState.objective,
              solveSeconds: submitState.solveSeconds,
            }}
            sourceFilename={file.name}
            dataTestId="vrptw-download-button"
          />
        </div>
      )}

      {submitState.kind === "error" && (
        <StatusCard
          variant="error"
          title="提交失败"
          description={submitState.message}
          ariaLabel="console.excel.vrptw.submit_error"
          icon="🚫"
        />
      )}
    </div>
  );
}

function SchedulePreviewCard({
  file,
  onReset,
}: {
  file: File;
  onReset: () => void;
}): JSX.Element {
  const [state, setState] = useState<
    | { kind: "parsing" }
    | {
        kind: "mapped";
        result: ReturnType<typeof buildSchedulePayload>;
        summary: ExcelWorkbookSummary;
      }
    | { kind: "error"; message: string }
  >({ kind: "parsing" });
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const summary = await parseExcel(file, { includeRows: true });
        if (cancelled) return;
        const result = buildSchedulePayload(summary);
        setState({ kind: "mapped", result, summary });
      } catch (err) {
        if (cancelled) return;
        setState({ kind: "error", message: (err as Error).message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file]);

  const handleSubmit = async (): Promise<void> => {
    if (state.kind !== "mapped" || !state.result.ok) return;
    setSubmitState({ kind: "loading" });
    try {
      const resp = await submitOptimizationDemo(state.result.payload);
      setSubmitState({
        kind: "solved",
        objective: resp.objective,
        solveSeconds: resp.solve_seconds,
      });
    } catch (err) {
      if (err instanceof OptiCloudClientError && err.status === 501) {
        setSubmitState({ kind: "not_implemented", detail: err.detail });
      } else {
        setSubmitState({
          kind: "error",
          message:
            err instanceof OptiCloudClientError
              ? `${err.title}: ${err.detail}`
              : String((err as Error).message),
        });
      }
    }
  };

  if (state.kind === "parsing") {
    return (
      <div className="space-y-3" data-testid="schedule-preview-card">
        <div className="text-sm text-muted-foreground">正在读取数据行...</div>
        <LoadingShimmer variant="card" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="space-y-3" data-testid="schedule-preview-card">
        <StatusCard
          variant="error"
          title="读取失败"
          description={state.message}
          ariaLabel="console.excel.schedule.parse_error"
          icon="🚫"
        />
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

  const result = state.result;
  if (!result.ok) {
    return (
      <div className="space-y-3" data-testid="schedule-preview-card">
        <StatusCard
          variant="error"
          title="排班/调度数据校验失败"
          description={`发现 ${result.errors.length} 个问题，请在 Excel 中修正后重试`}
          ariaLabel="console.excel.schedule.invalid"
          icon="⚠️"
        />
        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
            {result.errors.map((e, i) => (
              <li key={i}>
                <code className="font-mono text-xs">{e.sheet}</code>
                {e.field && (
                  <>
                    {" · "}
                    <code className="font-mono text-xs">{e.field}</code>
                  </>
                )}
                {" — "}
                {e.message}
              </li>
            ))}
          </ul>
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

  return (
    <div className="space-y-3" data-testid="schedule-preview-card">
      <StatusCard
        variant="ok"
        title={`✅ 排班/调度试跑已准备好 — ${result.task_count} 任务 / ${result.resource_count} 资源 / ${result.precedence_count} 前驱后继`}
        description="数据已通过格式校验。可点击 试跑 提交到排班/调度求解器。"
        ariaLabel="console.excel.schedule.ready"
        icon="🎯"
      />

      {result.warnings.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}

      <details className="rounded-md border border-border bg-muted/30">
        <summary className="cursor-pointer px-4 py-2 text-sm font-medium">
          📋 查看构建的 JSON 请求
        </summary>
        <pre
          className="overflow-x-auto p-3 font-mono text-xs"
          data-testid="schedule-payload-json"
        >
          {JSON.stringify(result.payload, null, 2)}
        </pre>
      </details>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={submitState.kind === "loading"}
          data-testid="schedule-submit-button"
          className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
        >
          {submitState.kind === "loading" ? "排班/调度试跑中..." : "🚀 试跑"}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
          data-testid="excel-reset-button"
        >
          重新选择文件
        </button>
      </div>

      {submitState.kind === "not_implemented" && (
        <div data-testid="schedule-501-card" className="space-y-2">
          <StatusCard
            variant="info"
            title="排班/调度求解器即将上线 (M2-M3)"
            description={
              `您的数据已通过格式校验（${result.task_count} 任务 / ${result.resource_count} 资源）。` +
              " 求解器将在后续版本上线，届时本页面将直接返回结果。"
            }
            ariaLabel="console.excel.schedule.not_implemented"
            icon="🚧"
          />
          <p className="text-sm text-muted-foreground">
            <Link
              href="/algorithms?task_type=schedule"
              className="text-primary hover:underline"
            >
              → 看其它排班/调度求解器
            </Link>
          </p>
          <DownloadResultCard
            taskType="schedule"
            source={state.summary}
            payload={result.payload}
            status="demo"
            sourceFilename={file.name}
            dataTestId="schedule-download-button"
          />
        </div>
      )}

      {submitState.kind === "solved" && (
        <div className="space-y-2">
          <StatusCard
            variant="ok"
            title="✅ 求解完成"
            description={`耗时 ${submitState.solveSeconds.toFixed(2)}s · 目标值 ${submitState.objective ?? "(N/A)"}`}
            ariaLabel="console.excel.schedule.solved"
            icon="🎉"
          />
          <DownloadResultCard
            taskType="schedule"
            source={state.summary}
            payload={result.payload}
            status="solved"
            realResult={{
              objective: submitState.objective,
              solveSeconds: submitState.solveSeconds,
            }}
            sourceFilename={file.name}
            dataTestId="schedule-download-button"
          />
        </div>
      )}

      {submitState.kind === "error" && (
        <StatusCard
          variant="error"
          title="提交失败"
          description={submitState.message}
          ariaLabel="console.excel.schedule.submit_error"
          icon="🚫"
        />
      )}
    </div>
  );
}

function InventoryPreviewCard({
  file,
  onReset,
}: {
  file: File;
  onReset: () => void;
}): JSX.Element {
  const [state, setState] = useState<
    | { kind: "parsing" }
    | {
        kind: "mapped";
        result: ReturnType<typeof buildInventoryPayload>;
        summary: ExcelWorkbookSummary;
      }
    | { kind: "error"; message: string }
  >({ kind: "parsing" });
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const summary = await parseExcel(file, { includeRows: true });
        if (cancelled) return;
        const result = buildInventoryPayload(summary);
        setState({ kind: "mapped", result, summary });
      } catch (err) {
        if (cancelled) return;
        setState({ kind: "error", message: (err as Error).message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file]);

  const handleSubmit = async (): Promise<void> => {
    if (state.kind !== "mapped" || !state.result.ok) return;
    setSubmitState({ kind: "loading" });
    try {
      const resp = await submitOptimizationDemo(state.result.payload);
      setSubmitState({
        kind: "solved",
        objective: resp.objective,
        solveSeconds: resp.solve_seconds,
      });
    } catch (err) {
      if (err instanceof OptiCloudClientError && err.status === 501) {
        setSubmitState({ kind: "not_implemented", detail: err.detail });
      } else {
        setSubmitState({
          kind: "error",
          message:
            err instanceof OptiCloudClientError
              ? `${err.title}: ${err.detail}`
              : String((err as Error).message),
        });
      }
    }
  };

  if (state.kind === "parsing") {
    return (
      <div className="space-y-3" data-testid="inventory-preview-card">
        <div className="text-sm text-muted-foreground">正在读取数据行...</div>
        <LoadingShimmer variant="card" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="space-y-3" data-testid="inventory-preview-card">
        <StatusCard
          variant="error"
          title="读取失败"
          description={state.message}
          ariaLabel="console.excel.inventory.parse_error"
          icon="🚫"
        />
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

  const result = state.result;
  if (!result.ok) {
    return (
      <div className="space-y-3" data-testid="inventory-preview-card">
        <StatusCard
          variant="error"
          title="库存预测数据校验失败"
          description={`发现 ${result.errors.length} 个问题，请在 Excel 中修正后重试`}
          ariaLabel="console.excel.inventory.invalid"
          icon="⚠️"
        />
        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
            {result.errors.map((e, i) => (
              <li key={i}>
                <code className="font-mono text-xs">{e.sheet}</code>
                {e.field && (
                  <>
                    {" · "}
                    <code className="font-mono text-xs">{e.field}</code>
                  </>
                )}
                {" — "}
                {e.message}
              </li>
            ))}
          </ul>
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

  return (
    <div className="space-y-3" data-testid="inventory-preview-card">
      <StatusCard
        variant="ok"
        title={`✅ 库存预测试跑已准备好 — ${result.sku_count} SKU / ${result.history_count} 历史行 / ${result.seasonality_count} 季节性`}
        description="数据已通过格式校验。可点击 试跑 提交到库存预测引擎。"
        ariaLabel="console.excel.inventory.ready"
        icon="📈"
      />

      {result.warnings.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}

      <details className="rounded-md border border-border bg-muted/30">
        <summary className="cursor-pointer px-4 py-2 text-sm font-medium">
          📋 查看构建的 JSON 请求
        </summary>
        <pre
          className="overflow-x-auto p-3 font-mono text-xs"
          data-testid="inventory-payload-json"
        >
          {JSON.stringify(result.payload, null, 2)}
        </pre>
      </details>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={submitState.kind === "loading"}
          data-testid="inventory-submit-button"
          className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
        >
          {submitState.kind === "loading" ? "库存预测中..." : "🚀 试跑"}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
          data-testid="excel-reset-button"
        >
          重新选择文件
        </button>
      </div>

      {submitState.kind === "not_implemented" && (
        <div data-testid="inventory-501-card" className="space-y-2">
          <StatusCard
            variant="info"
            title="📈 库存预测引擎即将上线 (M2-M3)"
            description={
              `您的数据已通过格式校验（${result.sku_count} SKU / ${result.history_count} 历史行）。` +
              " 预测引擎将在后续版本上线，届时本页面将直接返回 P10/P50/P90 预测区间。"
            }
            ariaLabel="console.excel.inventory.not_implemented"
            icon="🚧"
          />
          <p className="text-sm text-muted-foreground">
            <Link
              href="/algorithms?task_type=forecast"
              className="text-primary hover:underline"
            >
              → 看其它预测算法
            </Link>
          </p>
          <DownloadResultCard
            taskType="inventory"
            source={state.summary}
            payload={result.payload}
            status="demo"
            sourceFilename={file.name}
            dataTestId="inventory-download-button"
          />
        </div>
      )}

      {submitState.kind === "solved" && (
        <div className="space-y-2">
          <StatusCard
            variant="ok"
            title="✅ 预测完成"
            description={`耗时 ${submitState.solveSeconds.toFixed(2)}s · 目标值 ${submitState.objective ?? "(N/A)"}`}
            ariaLabel="console.excel.inventory.solved"
            icon="🎉"
          />
          <DownloadResultCard
            taskType="inventory"
            source={state.summary}
            payload={result.payload}
            status="solved"
            realResult={{
              objective: submitState.objective,
              solveSeconds: submitState.solveSeconds,
            }}
            sourceFilename={file.name}
            dataTestId="inventory-download-button"
          />
        </div>
      )}

      {submitState.kind === "error" && (
        <StatusCard
          variant="error"
          title="提交失败"
          description={submitState.message}
          ariaLabel="console.excel.inventory.submit_error"
          icon="🚫"
        />
      )}
    </div>
  );
}

function ConfirmedCard({
  file,
  taskType,
  overrodeFrom,
  onReset,
}: {
  file: File;
  taskType: DetectedTaskType;
  overrodeFrom: DetectedTaskType | null;
  onReset: () => void;
}): JSX.Element {
  if (taskType === "vrptw") {
    return <VrptwPreviewCard file={file} onReset={onReset} />;
  }
  if (taskType === "schedule") {
    return <SchedulePreviewCard file={file} onReset={onReset} />;
  }
  if (taskType === "inventory") {
    return <InventoryPreviewCard file={file} onReset={onReset} />;
  }

  return (
    <div className="space-y-3" data-testid="excel-confirmed-card">
      <StatusCard
        variant="ok"
        title={`✅ 类型已确认：${TASK_LABEL[taskType]}`}
        description={
          overrodeFrom
            ? `您选择了 ${TASK_LABEL[taskType]}，覆盖系统推荐 ${TASK_LABEL[overrodeFrom]}`
            : "下一步将进入结果下载界面。"
        }
        ariaLabel="console.excel.confirmed"
        icon="🎯"
      />
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        📋 通用 LP / 未知类型暂未接入模板。VRPTW 路线 / 排班/调度 / 库存预测可自动映射、试跑并下载结果，请回到上一步选择其它类型。
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
            适合 VRPTW 路线 / 排班调度 / 库存预测 - 不写代码，拖一下就行（≤5 MB / 50K 行）
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
                description={`${state.file.name} · ${(state.file.size / 1024 / 1024).toFixed(2)} MB · 本地解析完成，原始文件未上传`}
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
            file={state.file}
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
