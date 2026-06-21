"use client";
/** /console/predictions — Lina CSV prediction recovery surface (Story 3.11). */

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

import { ConsolePageHeader, ConsoleShell } from "@/components/ConsoleShell";
import {
  createJobTemplate,
  createJobTemplateVersion,
  listJobTemplateVersions,
  OptiCloudClientError,
  type JobTemplateDetail,
  type JobTemplateSummary,
  type PredictionFamily,
  type PredictionRequest,
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
    title: "errors.fallback.prediction_request_failed",
    status: 500,
    detail: error instanceof Error ? error.message : "预测请求失败",
    errors: [
      {
        field_path: "prediction.request",
        value: null,
        constraint: "prediction request must complete without client-side failure",
        remediation_hint_key: "errors.fallback.prediction_request_failed",
      },
    ],
  };
}

function toPredictionRequestPayload(payload: Record<string, unknown>): PredictionRequest {
  const family = payload.family;
  const data = payload.data;
  const horizon = payload.horizon;
  if (
    (family !== "arima" && family !== "chronos") ||
    !Array.isArray(data) ||
    data.some((value) => typeof value !== "number" || !Number.isFinite(value)) ||
    typeof horizon !== "number" ||
    !Number.isInteger(horizon)
  ) {
    throw new Error("模板版本 payload 不是有效预测请求");
  }
  return { family, data, horizon };
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

type TemplateSaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; template: JobTemplateDetail }
  | { kind: "error"; error: RFC7807ErrorPayload };

type TemplateReuseState =
  | { kind: "idle"; history: JobTemplateSummary[] }
  | { kind: "creating"; history: JobTemplateSummary[] }
  | {
      kind: "created";
      template: JobTemplateDetail;
      response: PredictionResponse;
      history: JobTemplateSummary[];
    }
  | {
      kind: "prediction_error";
      template: JobTemplateDetail;
      error: RFC7807ErrorPayload;
      history: JobTemplateSummary[];
    }
  | { kind: "error"; error: RFC7807ErrorPayload; history: JobTemplateSummary[] };

function TemplateReusePanel({
  template,
  apiKeyRef,
}: {
  template: JobTemplateDetail;
  apiKeyRef: React.RefObject<HTMLInputElement>;
}): JSX.Element {
  const initialHorizon =
    typeof template.payload_json.horizon === "number" ? template.payload_json.horizon : 3;
  const [horizon, setHorizon] = useState(initialHorizon);
  const [state, setState] = useState<TemplateReuseState>({
    kind: "idle",
    history: [template],
  });

  const createVersionAndPredict = async (): Promise<void> => {
    const apiKey = apiKeyRef.current?.value.trim() ?? "";
    if (apiKey === "") {
      setState({
        kind: "error",
        history: state.history,
        error: {
          title: "Missing API Key",
          status: 401,
          detail: "请输入 API key 后再创建模板版本",
        },
      });
      return;
    }

    const nextHorizon = Math.max(1, Math.min(90, Math.trunc(horizon)));
    setState({ kind: "creating", history: state.history });
    try {
      const version = await createJobTemplateVersion(apiKey, template.id, {
        parameter_path: "horizon",
        value: nextHorizon,
      });
      const history = await listJobTemplateVersions(apiKey, template.id);
      const historyItems = history.items.length > 0 ? history.items : [template, version];
      let prediction: PredictionResponse;
      try {
        prediction = await postPrediction(
          apiKey,
          toPredictionRequestPayload(version.payload_json),
          idempotencyKey(),
        );
      } catch (err) {
        setState({
          kind: "prediction_error",
          template: version,
          error: toRfc7807(err),
          history: historyItems,
        });
        return;
      }
      setState({
        kind: "created",
        template: version,
        response: prediction,
        history: historyItems,
      });
    } catch (err) {
      setState({ kind: "error", history: state.history, error: toRfc7807(err) });
    }
  };

  const history = state.history.length > 0 ? state.history : [template];

  return (
    <div className="mt-4 space-y-4 rounded-md border border-border bg-muted/20 p-4">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <label className="block">
          <span className="mb-1 block text-sm font-medium">新版预测步长</span>
          <input
            aria-label="新版预测步长"
            type="number"
            min={1}
            max={90}
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={() => void createVersionAndPredict()}
            disabled={state.kind === "creating"}
            data-testid="create-template-version-button"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
          >
            {state.kind === "creating" ? "创建中..." : "创建版本并预测"}
          </button>
        </div>
      </div>

      <div data-testid="template-version-history" className="rounded-md border border-border bg-background">
        <div className="border-b border-border px-3 py-2 text-sm font-medium">
          版本历史
        </div>
        <div className="divide-y divide-border text-sm">
          {history.map((item) => (
            <div key={item.id} className="grid gap-1 px-3 py-2 md:grid-cols-[auto_1fr_auto]">
              <span className="font-medium">v{item.version}</span>
              <span className="truncate text-muted-foreground">{item.payload_sha256}</span>
              <span className="text-muted-foreground">{item.parent_template_id ? "版本" : "根模板"}</span>
            </div>
          ))}
        </div>
      </div>

      {state.kind === "created" && (
        <div data-testid="template-version-success" className="space-y-3">
          <div className="rounded-md border border-success/30 bg-success/5 p-3 text-sm text-success">
            已创建模板版本：{state.template.name} · v{state.template.version}
          </div>
          <PredictionResult response={state.response} />
        </div>
      )}
      {state.kind === "prediction_error" && (
        <div data-testid="template-version-prediction-error" className="space-y-3">
          <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
            已创建模板版本：{state.template.name} · v{state.template.version}
          </div>
          <div className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
            {state.error.title}: {state.error.detail}
          </div>
        </div>
      )}
      {state.kind === "error" && (
        <div
          data-testid="template-version-error"
          className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger"
        >
          {state.error.title}: {state.error.detail}
        </div>
      )}
    </div>
  );
}

function TemplateSavePanel({
  response,
  apiKeyRef,
}: {
  response: PredictionResponse;
  apiKeyRef: React.RefObject<HTMLInputElement>;
}): JSX.Element {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saveState, setSaveState] = useState<TemplateSaveState>({ kind: "idle" });

  const saveTemplate = async (): Promise<void> => {
    const apiKey = apiKeyRef.current?.value.trim() ?? "";
    const templateName = name.trim();
    if (templateName === "") return;
    if (apiKey === "") {
      setSaveState({
        kind: "error",
        error: {
          title: "Missing API Key",
          status: 401,
          detail: "请输入 API key 后再保存模板",
        },
      });
      return;
    }
    setSaveState({ kind: "saving" });
    try {
      const template = await createJobTemplate(apiKey, {
        name: templateName,
        description: description.trim() || undefined,
        source_kind: "prediction",
        source_id: response.prediction_id,
      });
      setSaveState({ kind: "saved", template });
    } catch (err) {
      setSaveState({ kind: "error", error: toRfc7807(err) });
    }
  };

  return (
    <section
      aria-label="保存为任务模板"
      className="space-y-3 rounded-md border border-border bg-background p-4"
    >
      <div>
        <h2 className="text-base font-semibold">保存为任务模板</h2>
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="block">
          <span className="mb-1 block text-sm font-medium">模板名称</span>
          <input
            aria-label="模板名称"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={120}
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
            placeholder="月度销量模板"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">描述</span>
          <input
            aria-label="模板描述"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={500}
            className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
            placeholder="可选"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={() => void saveTemplate()}
            disabled={saveState.kind === "saving" || name.trim() === ""}
            data-testid="save-template-button"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
          >
            {saveState.kind === "saving" ? "保存中..." : "保存模板"}
          </button>
        </div>
      </div>
      {saveState.kind === "saved" && (
        <>
          <div
            data-testid="template-save-success"
            className="rounded-md border border-success/30 bg-success/5 p-3 text-sm text-success"
          >
            已保存模板：{saveState.template.name} · v{saveState.template.version}
          </div>
          <TemplateReusePanel template={saveState.template} apiKeyRef={apiKeyRef} />
        </>
      )}
      {saveState.kind === "error" && (
        <div
          data-testid="template-save-error"
          className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger"
        >
          {saveState.error.title}: {saveState.error.detail}
        </div>
      )}
    </section>
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
    <ConsoleShell active="predictions">
      <ConsolePageHeader
        eyebrow="Console / Forecast workflow"
        title="CSV 需求预测"
        description="上传销售 CSV，先在浏览器内校验和修复，再提交到现有预测 API。"
        meta={
          <>
            <span className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground">
              {"CSV <= 10 MB"}
            </span>
            <span className="inline-flex min-h-touch items-center rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
              浏览器内校验
            </span>
          </>
        }
      />

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
        {state.kind === "solved" && (
          <>
            <PredictionResult response={state.response} />
            <TemplateSavePanel response={state.response} apiKeyRef={apiKeyRef} />
          </>
        )}
      </section>
    </ConsoleShell>
  );
}
