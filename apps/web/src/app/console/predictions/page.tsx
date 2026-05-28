"use client";
/** /console/predictions — Lina CSV prediction recovery surface (Story 3.11). */

import Link from "next/link";
import { useRef, useState } from "react";

import {
  ConfirmationModal,
  FilePicker,
  LoadingShimmer,
  RFC7807Panel,
  StatusCard,
  type FilePickerRejectReason,
  type RFC7807ErrorPayload,
} from "@opticloud/ui";

import {
  OptiCloudClientError,
  type PredictionFamily,
  type PredictionResponse,
  postPrediction,
} from "@/lib/api";
import {
  buildPredictionRequest,
  parsePredictionCsv,
  replaceInvalidPredictionRows,
  type PredictionCsvInvalidResult,
  type PredictionCsvParseResult,
  type PredictionCsvValidResult,
} from "@/lib/csv-prediction";

const MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024;
const TEMPLATE = [
  "商品编号,月份,销量",
  "SKU-01,2026-01,120",
  "SKU-01,2026-02,132",
  "SKU-01,2026-03,141",
].join("\n");

type PredictionPageState =
  | { kind: "idle" }
  | { kind: "parsing"; filename: string }
  | { kind: "rejected"; reason: FilePickerRejectReason }
  | { kind: "parse_error"; message: string }
  | { kind: "invalid_partial"; result: PredictionCsvInvalidResult; modalOpen: boolean }
  | { kind: "ready"; result: PredictionCsvValidResult }
  | { kind: "submitting"; result: PredictionCsvValidResult }
  | { kind: "solved"; result: PredictionCsvValidResult; response: PredictionResponse }
  | {
      kind: "api_error";
      result: PredictionCsvValidResult;
      error: RFC7807ErrorPayload;
    };

function templateHref(): string {
  return `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;
}

function toRfc7807(error: unknown): RFC7807ErrorPayload {
  if (error instanceof OptiCloudClientError) {
    return {
      title: error.title,
      status: error.status,
      detail: error.detail,
      errors: error.errors,
      next_action_url: error.next_action_url,
      request_id: error.request_id,
      trace_id: error.trace_id,
    };
  }
  return {
    title: "Prediction Request Failed",
    status: 500,
    detail: error instanceof Error ? error.message : "预测请求失败",
  };
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value);
}

function idempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `pred-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function InvalidRowsPanel({
  result,
}: {
  result: PredictionCsvInvalidResult;
}): JSX.Element {
  return (
    <div
      data-testid="csv-invalid-card"
      className="space-y-3 rounded-md border border-danger bg-background p-4"
    >
      <StatusCard
        variant="error"
        title="CSV 校验失败"
        description={`发现 ${result.invalidRows.length} 个问题，数据行 ${formatNumber(result.summary.rowCount)} 行`}
        ariaLabel="console.predictions.invalid"
        icon="⚠️"
      />
      <ul className="space-y-2 text-sm">
        {result.invalidRows.map((row, idx) => (
          <li
            key={`${row.fieldPath}-${idx}`}
            className="rounded-md border border-border bg-muted/30 p-3"
          >
            <div className="font-medium">
              数据行 {row.dataRowNumber} · 文件第 {row.rowNumber} 行
            </div>
            <div className="mt-1 font-mono text-xs text-muted-foreground">
              {row.fieldPath} · {row.constraint} · value: {String(row.value)}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecoveryModal({
  result,
  open,
  replacement,
  onReplacementChange,
  onReplace,
  onRetryAll,
  onCancel,
}: {
  result: PredictionCsvInvalidResult;
  open: boolean;
  replacement: string;
  onReplacementChange: (value: string) => void;
  onReplace: () => void;
  onRetryAll: () => void;
  onCancel: () => void;
}): JSX.Element | null {
  const first = result.invalidRows[0];
  return (
    <ConfirmationModal
      open={open}
      onClose={onCancel}
      onConfirm={onReplace}
      variant="generic"
      ariaLabel="console.predictions.partial_upload_recovery"
      title="CSV 部分校验失败"
      description={
        first
          ? `第 ${first.dataRowNumber} 条数据行需要修正：${first.fieldPath}`
          : "请修正失败记录后继续"
      }
      confirmLabel="仅替换失败行"
      cancelLabel="取消"
      body={
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              替换行 CSV
            </span>
            <textarea
              aria-label="替换行 CSV"
              value={replacement}
              onChange={(event) => onReplacementChange(event.target.value)}
              rows={3}
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
              placeholder="SKU-08,2026-08,8470"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onRetryAll}
              data-testid="csv-retry-all"
              className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              全部重试
            </button>
          </div>
        </div>
      }
    />
  );
}

function ReadyCard({
  result,
  family,
  horizon,
  onFamily,
  onHorizon,
  onSubmit,
  onReset,
  submitting,
  apiKeyRef,
}: {
  result: PredictionCsvValidResult;
  family: PredictionFamily;
  horizon: number;
  onFamily: (value: PredictionFamily) => void;
  onHorizon: (value: number) => void;
  onSubmit: () => void;
  onReset: () => void;
  submitting?: boolean;
  apiKeyRef: React.RefObject<HTMLInputElement>;
}): JSX.Element {
  return (
    <div data-testid="csv-ready-card" className="space-y-4">
      <StatusCard
        variant="ok"
        title="CSV 已通过校验"
        description={`${formatNumber(result.summary.rowCount)} 行 · ${formatNumber(result.summary.skuCount)} SKU · ${result.summary.minPeriod ?? "-"} 至 ${result.summary.maxPeriod ?? "-"}`}
        ariaLabel="console.predictions.ready"
        icon="📈"
      />
      <div className="grid gap-3 rounded-md border border-border bg-muted/30 p-4 text-sm md:grid-cols-2">
        <div>
          <div className="text-xs text-muted-foreground">聚合序列长度</div>
          <div className="font-medium">{formatNumber(result.series.length)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">CSV 编码</div>
          <div className="font-medium">{result.summary.encoding}</div>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block md:col-span-3">
          <span className="mb-1 block text-sm font-medium">API key</span>
          <input
            ref={apiKeyRef}
            aria-label="API key"
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
            placeholder="sk-..."
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">预测族</span>
          <select
            aria-label="预测族"
            value={family}
            onChange={(event) => onFamily(event.target.value as PredictionFamily)}
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
          >
            <option value="chronos">chronos</option>
            <option value="arima">arima</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">预测步长</span>
          <input
            aria-label="预测步长"
            type="number"
            min={1}
            max={90}
            value={horizon}
            onChange={(event) => onHorizon(Number(event.target.value))}
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitting}
          data-testid="prediction-submit"
          className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
        >
          {submitting ? "预测中..." : "提交预测"}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
          data-testid="csv-reset"
        >
          重新选择 CSV
        </button>
      </div>
    </div>
  );
}

function PredictionResult({
  response,
}: {
  response: PredictionResponse;
}): JSX.Element {
  const rows = response.prediction.p50.map((p50, idx) => ({
    step: idx + 1,
    p10: response.prediction.p10[idx],
    p50,
    p90: response.prediction.p90[idx],
  }));
  return (
    <div data-testid="prediction-result" className="space-y-4">
      <StatusCard
        variant="ok"
        title="预测完成"
        description={`P50 中位预测已生成，drift_score=${response.drift_score.toFixed(3)}`}
        ariaLabel="console.predictions.solved"
        icon="✅"
      />
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[420px] text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Step</th>
              <th className="px-3 py-2 text-left">P10</th>
              <th className="px-3 py-2 text-left">P50</th>
              <th className="px-3 py-2 text-left">P90</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.step} className="border-t border-border">
                <td className="px-3 py-2">{row.step}</td>
                <td className="px-3 py-2">{formatNumber(row.p10 ?? 0)}</td>
                <td className="px-3 py-2 font-medium">{formatNumber(row.p50)}</td>
                <td className="px-3 py-2">{formatNumber(row.p90 ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
        <div className="font-medium">
          {response.model_version.provider_id} · {response.model_version.kind} ·{" "}
          {response.model_version.version}
        </div>
        <a
          href={response.model_version.provider_url}
          className="text-primary hover:underline"
        >
          provider_url
        </a>
        <p className="mt-2 text-muted-foreground">{response.disclaimer.bilingual}</p>
        <p className="mt-2">
          Lina 可优先查看 P50 作为主预测，并用 P10/P90 估计低高需求区间。
        </p>
      </div>
    </div>
  );
}

export default function ConsolePredictionsPage(): JSX.Element {
  const [state, setState] = useState<PredictionPageState>({ kind: "idle" });
  const [replacement, setReplacement] = useState("");
  const [family, setFamily] = useState<PredictionFamily>("chronos");
  const [horizon, setHorizon] = useState(3);
  const apiKeyRef = useRef<HTMLInputElement | null>(null);

  const reset = (): void => {
    setReplacement("");
    setState({ kind: "idle" });
  };

  const handleFile = (file: File): void => {
    setState({ kind: "parsing", filename: file.name });
    void (async () => {
      try {
        const result = await parsePredictionCsv(file);
        applyParsedResult(result);
      } catch (err) {
        setState({
          kind: "parse_error",
          message: err instanceof Error ? err.message : "无法解析 CSV",
        });
      }
    })();
  };

  const applyParsedResult = (result: PredictionCsvParseResult): void => {
    if (result.ok) {
      setFamily(result.defaultFamily);
      setHorizon(result.defaultHorizon);
      setState({ kind: "ready", result });
      return;
    }
    setState({ kind: "invalid_partial", result, modalOpen: true });
  };

  const replaceInvalidRows = (): void => {
    if (state.kind !== "invalid_partial") return;
    const next = replaceInvalidPredictionRows(state.result, replacement);
    setReplacement("");
    applyParsedResult(next);
  };

  const cancelRecovery = (): void => {
    if (state.kind === "invalid_partial") {
      setState({ ...state, modalOpen: false });
    }
  };

  const currentResult =
    state.kind === "ready" ||
    state.kind === "submitting" ||
    state.kind === "solved" ||
    state.kind === "api_error"
      ? state.result
      : null;

  const submitPrediction = async (): Promise<void> => {
    if (!currentResult) return;
    const apiKey = apiKeyRef.current?.value.trim() ?? "";
    if (apiKey === "") return;
    const body = buildPredictionRequest(currentResult, {
      family,
      horizon: Math.max(1, Math.min(90, horizon)),
    });
    setState({ kind: "submitting", result: currentResult });
    try {
      const response = await postPrediction(apiKey, body, idempotencyKey());
      setState({ kind: "solved", result: currentResult, response });
    } catch (err) {
      setState({ kind: "api_error", result: currentResult, error: toRfc7807(err) });
    }
  };

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/console/excel" className="text-muted-foreground hover:text-foreground">
              Excel
            </Link>
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              算法目录
            </Link>
          </nav>
        </div>
      </header>

      <section className="bg-muted py-10">
        <div className="mx-auto max-w-3xl px-6">
          <h1 className="text-3xl font-bold">CSV 需求预测</h1>
          <p className="mt-2 text-muted-foreground">
            上传销售 CSV，先在浏览器内校验和修复，再提交到现有预测 API。
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {state.kind === "idle" && (
          <div
            data-testid="csv-idle-panel"
            className="space-y-4 rounded-md border border-border bg-background p-5"
          >
            <div>
              <h2 className="text-lg font-semibold">选择 CSV 文件</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                支持 sku/SKU/商品、month/date/月份、value/sales/销量 等表头；单文件 ≤10 MB。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <FilePicker
                accept=".csv,text/csv"
                maxSizeBytes={MAX_CSV_SIZE_BYTES}
                onFile={handleFile}
                onReject={(reason) => setState({ kind: "rejected", reason })}
                ariaLabel="console.predictions.csv_file"
                label="选择 CSV"
              />
              <a
                href={templateHref()}
                download="opticloud-prediction-template.csv"
                className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                下载模板
              </a>
            </div>
          </div>
        )}

        {state.kind === "parsing" && (
          <div className="space-y-3" data-testid="csv-parsing-card">
            <StatusCard
              variant="info"
              title="正在解析 CSV"
              description={state.filename}
              ariaLabel="console.predictions.parsing"
              icon="⏳"
            />
            <LoadingShimmer variant="card" />
          </div>
        )}

        {state.kind === "rejected" && (
          <div className="space-y-3" data-testid="csv-rejected-card">
            <StatusCard
              variant="warning"
              title="CSV 文件过大"
              description={state.reason.message}
              ariaLabel="console.predictions.rejected"
              icon="⚠️"
            />
            <div className="rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              请拆分为多个 ≤10 MB 文件，或另存为 UTF-8 CSV 后重试。
            </div>
            <button
              type="button"
              onClick={reset}
              className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              重试
            </button>
          </div>
        )}

        {state.kind === "parse_error" && (
          <div className="space-y-3" data-testid="csv-parse-error-card">
            <StatusCard
              variant="error"
              title="无法解析 CSV"
              description={state.message}
              ariaLabel="console.predictions.parse_error"
              icon="🚫"
            />
            <div className="rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              请确认文件为 CSV；如果来自旧版 Excel，请另存为 UTF-8 CSV 后重试。
            </div>
            <button
              type="button"
              onClick={reset}
              className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              重试
            </button>
          </div>
        )}

        {state.kind === "invalid_partial" && (
          <>
            <InvalidRowsPanel result={state.result} />
            <RecoveryModal
              result={state.result}
              open={state.modalOpen}
              replacement={replacement}
              onReplacementChange={setReplacement}
              onReplace={replaceInvalidRows}
              onRetryAll={reset}
              onCancel={cancelRecovery}
            />
          </>
        )}

        {(state.kind === "ready" ||
          state.kind === "submitting" ||
          state.kind === "solved" ||
          state.kind === "api_error") && (
          <ReadyCard
            result={state.result}
            family={family}
            horizon={horizon}
            onFamily={setFamily}
            onHorizon={setHorizon}
            onSubmit={() => void submitPrediction()}
            onReset={reset}
            submitting={state.kind === "submitting"}
            apiKeyRef={apiKeyRef}
          />
        )}

        {state.kind === "submitting" && <LoadingShimmer variant="card" />}
        {state.kind === "api_error" && <RFC7807Panel payload={state.error} />}
        {state.kind === "solved" && <PredictionResult response={state.response} />}
      </section>
    </main>
  );
}
