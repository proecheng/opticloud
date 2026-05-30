import type {
  ChatInterfaceFileContext,
  ChatInterfaceFileSelectionResult,
  ChatInterfaceModelAction,
  ChatInterfaceResponse,
  ChatInterfaceSendRequest,
  ChatInterfaceStreamEvent,
  ChatInterfaceWhatIfContext,
} from "@opticloud/ui";

import {
  parseChatFileContext,
  type ChatFileContextPayload,
  ChatFileContextRejectError,
} from "./chat-file-context";
import {
  cancelChatCsvRecovery,
  parseChatCsvWithRecovery,
  replaceFailedChatCsvRows,
  retryAllChatCsvRecovery,
  type ChatCsvRecoverySession,
} from "./chat-file-context-recovery";

const CHAT_SERVICE_URL =
  process.env.NEXT_PUBLIC_CHAT_SERVICE_URL ?? "http://localhost:8004";

export interface InternalBetaCredentials {
  tenant: string;
  user: string;
  token: string;
}

export interface InternalBetaChatRequest {
  credentials: InternalBetaCredentials;
  message: string;
  locale?: "zh-CN" | "en-US" | "mixed";
  fileContexts?: ChatInterfaceFileContext[];
  whatIfContext?: ChatInterfaceWhatIfContext | null;
}

const recoverySessions = new Map<string, ChatCsvRecoverySession>();

export function discardChatRecovery(recoveryId: string): void {
  const session = recoverySessions.get(recoveryId);
  if (session) {
    cancelChatCsvRecovery(session);
  }
  recoverySessions.delete(recoveryId);
}

export async function selectChatFile(
  file: File,
): Promise<ChatInterfaceFileSelectionResult> {
  try {
    if (file.name.toLowerCase().endsWith(".csv")) {
      const recovered = await parseChatCsvWithRecovery(file);
      if (recovered.ok) {
        return { status: "ready", context: toUiFileContext(recovered.context) };
      }
      const recoveryId = makeRecoveryId();
      recoverySessions.set(recoveryId, recovered.session);
      return {
        status: "recovery_required",
        recoveryId,
        filename: recovered.session.filename,
        invalidRowCount: recovered.invalid_row_count,
        invalidRows: recovered.invalid_rows.map((row) => ({
          rowNumber: row.row_number,
          dataRowNumber: row.data_row_number,
          fieldPath: row.field_path,
          constraint: row.constraint,
          remediationHintKey: row.remediation_hint_key,
        })),
        actions: recovered.actions,
      };
    }
    return {
      status: "ready",
      context: toUiFileContext(await parseChatFileContext(file)),
    };
  } catch (error) {
    if (error instanceof ChatFileContextRejectError) {
      return { status: "rejected", message: error.message };
    }
    return { status: "rejected", message: "文件解析失败，请检查格式后重试。" };
  }
}

export async function replaceChatRecoveryRows(
  recoveryId: string,
  replacementCsv: string,
): Promise<ChatInterfaceFileSelectionResult> {
  const session = recoverySessions.get(recoveryId);
  if (!session) {
    return { status: "rejected", message: "恢复会话已失效，请重新选择文件。" };
  }
  const result = replaceFailedChatCsvRows(session, replacementCsv);
  if (result.ok) {
    recoverySessions.delete(recoveryId);
    return { status: "ready", context: toUiFileContext(result.context) };
  }
  recoverySessions.set(recoveryId, result.session);
  return {
    status: "recovery_required",
    recoveryId,
    filename: result.session.filename,
    invalidRowCount: result.invalid_row_count,
    invalidRows: result.invalid_rows.map((row) => ({
      rowNumber: row.row_number,
      dataRowNumber: row.data_row_number,
      fieldPath: row.field_path,
      constraint: row.constraint,
      remediationHintKey: row.remediation_hint_key,
    })),
    actions: result.actions,
  };
}

export function retryChatRecovery(recoveryId: string): void {
  const session = recoverySessions.get(recoveryId);
  if (session) retryAllChatCsvRecovery(session);
  recoverySessions.delete(recoveryId);
}

export async function sendInternalBetaChatMessage(
  request: InternalBetaChatRequest,
): Promise<ChatInterfaceResponse> {
  const response = await fetch(`${CHAT_SERVICE_URL}/v1/chat/internal-beta/messages`, {
    method: "POST",
    headers: requestHeaders(request.credentials),
    body: JSON.stringify(buildRequestBody(request)),
  });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "Chat internal beta unavailable" : "Chat request failed");
  }
  return normalizeInternalBetaChatResponse(await response.json());
}

export async function* streamInternalBetaChatMessage(
  request: InternalBetaChatRequest,
): AsyncIterable<ChatInterfaceStreamEvent> {
  const response = await fetch(
    `${CHAT_SERVICE_URL}/v1/chat/internal-beta/messages/stream`,
    {
      method: "POST",
      headers: requestHeaders(request.credentials),
      body: JSON.stringify(buildRequestBody(request)),
    },
  );
  if (!response.ok) {
    throw new Error(response.status === 404 ? "Chat internal beta unavailable" : "Chat stream failed");
  }
  if (!response.body) {
    yield {
      type: "done",
      response: await sendInternalBetaChatMessage(request),
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamLocale: InternalBetaChatRequest["locale"] | undefined;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseChatSseBlock(block);
      if (event.type === "message_start") {
        streamLocale = event.locale;
      } else if (event.type === "done" && streamLocale) {
        event.response.locale = streamLocale;
      }
      if (event.type !== "heartbeat" && event.type !== "unknown") {
        yield event;
      }
    }
  }
  const tail = buffer.trim();
  if (tail) {
    const event = parseChatSseBlock(tail);
    if (event.type === "message_start") {
      streamLocale = event.locale;
    } else if (event.type === "done" && streamLocale) {
      event.response.locale = streamLocale;
    }
    if (event.type !== "heartbeat" && event.type !== "unknown") {
      yield event;
    }
  }
}

export function parseChatSseBlock(block: string): ChatInterfaceStreamEvent {
  if (block.trim().startsWith(":")) return { type: "heartbeat" };
  let eventName = "";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  const parsed = parseJsonObject(dataLines.join("\n"));
  if (!parsed.ok) {
    return { type: "error", message: "流式响应格式无效" };
  }
  const data = parsed.value;
  if (eventName === "message_start") {
    return {
      type: "message_start",
      messageId: stringOr(data.message_id, "msg_unknown"),
      locale: localeOr(data.locale),
    };
  }
  if (eventName === "content_delta") {
    return {
      type: "content_delta",
      chunk: typeof data.chunk === "string" ? safeText(data.chunk) : "",
    };
  }
  if (eventName === "done") {
    return { type: "done", response: normalizeStreamDone(data) };
  }
  if (eventName === "error") {
    return {
      type: "error",
      message: typeof data.message === "string" ? safeText(data.message) : "流式响应失败",
    };
  }
  return { type: "unknown", event: eventName };
}

export function normalizeInternalBetaChatResponse(value: unknown): ChatInterfaceResponse {
  const payload = asRecord(value);
  const languagePreview = asRecord(payload.language_preview);
  const modelPreview = asRecord(payload.model_preview);
  return {
    messageId: stringOr(payload.message_id, "msg_unknown"),
    locale: localeOr(payload.locale),
    content: safeText(stringOr(languagePreview.summary, "")),
    modelPreview: {
      previewId: stringOr(modelPreview.preview_id, ""),
      status: stringOr(modelPreview.status, "blocked"),
      taskType: typeof modelPreview.task_type === "string" ? modelPreview.task_type : undefined,
      criticConfidence:
        typeof modelPreview.critic_confidence === "number"
          ? modelPreview.critic_confidence
          : undefined,
      sandboxStatus:
        typeof modelPreview.sandbox_status === "string"
          ? modelPreview.sandbox_status
          : undefined,
      actions: Array.isArray(modelPreview.actions)
        ? modelPreview.actions.map(normalizeAction)
        : undefined,
      validationErrors: Array.isArray(modelPreview.validation_errors)
        ? modelPreview.validation_errors.map((error) => {
            const item = asRecord(error);
            return {
              fieldPath: stringOr(item.field_path, "model_preview"),
              message: safeText(stringOr(item.message, "校验失败")),
              remediationHintKey:
                typeof item.remediation_hint_key === "string"
                  ? item.remediation_hint_key
                  : undefined,
            };
          })
        : undefined,
    },
    fileContextPreview: normalizeFilePreview(payload.file_context_preview),
    whatIfPreview: normalizeWhatIfPreview(payload.what_if_preview),
    aigcGate: asRecord(payload.aigc_gate),
  };
}

function normalizeStreamDone(data: Record<string, unknown>): ChatInterfaceResponse {
  return {
    messageId: stringOr(data.message_id, "msg_unknown"),
    locale: "zh-CN",
    content: "",
    modelPreview: {
      previewId: stringOr(data.model_preview_id, ""),
      status: stringOr(data.model_preview_status, "blocked"),
    },
    fileContextPreview: normalizeFilePreview(data.file_context_preview),
    whatIfPreview: normalizeWhatIfPreview(data.what_if_preview),
    aigcGate: asRecord(data.aigc_gate),
  };
}

function normalizeAction(value: unknown): ChatInterfaceModelAction {
  const action = asRecord(value);
  return {
    kind:
      action.kind === "confirm" || action.kind === "edit" || action.kind === "cancel"
        ? action.kind
        : "cancel",
    labelZh: stringOr(action.label_zh, "取消"),
    labelEn: stringOr(action.label_en, "Cancel"),
    enabled: action.enabled === true,
    clientAction: stringOr(action.client_action, "chat.model_preview.cancel"),
    disabledReasonCode:
      typeof action.disabled_reason_code === "string"
        ? action.disabled_reason_code
        : undefined,
  };
}

function normalizeFilePreview(value: unknown): ChatInterfaceResponse["fileContextPreview"] {
  if (value === null || value === undefined) return null;
  const preview = asRecord(value);
  return {
    fileCount: numberOr(preview.file_count, 0),
    kinds: arrayOfStrings(preview.kinds) as Array<"csv" | "excel" | "json">,
    totalRows: numberOr(preview.total_rows, 0),
    filenames: arrayOfStrings(preview.filenames),
    detectedFields: arrayOfStrings(preview.detected_fields),
  };
}

function normalizeWhatIfPreview(value: unknown): ChatInterfaceResponse["whatIfPreview"] {
  if (value === null || value === undefined) return null;
  const preview = asRecord(value);
  return {
    status: stringOr(preview.status, "needs_clarification"),
    changeSummary: safeText(stringOr(preview.change_summary, "")),
    changedFields: arrayOfStrings(preview.changed_fields),
  };
}

function buildRequestBody(request: InternalBetaChatRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {
    message: request.message.trim(),
    client_request_id: makeClientRequestId(),
  };
  if (request.locale) body.locale = request.locale;
  if (request.fileContexts && request.fileContexts.length > 0) {
    body.file_contexts = request.fileContexts.map(toBackendFileContext);
  }
  if (request.whatIfContext) {
    body.what_if_context = toBackendWhatIfContext(request.whatIfContext);
  }
  return body;
}

function requestHeaders(credentials: InternalBetaCredentials): Headers {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  headers.set("X-Internal-Beta-Tenant", credentials.tenant);
  headers.set("X-Internal-Beta-User", credentials.user);
  headers.set("X-Internal-Beta-Token", credentials.token);
  return headers;
}

function toUiFileContext(context: ChatFileContextPayload): ChatInterfaceFileContext {
  return {
    source: context.source,
    kind: context.kind,
    filename: context.filename,
    sizeBytes: context.size_bytes,
    rowCount: context.row_count,
    sheetCount: context.sheet_count,
    sheets: context.sheets.map((sheet) => ({
      name: sheet.name,
      headers: [...sheet.headers],
      rowCount: sheet.row_count,
    })),
    topLevelKeys: [...context.top_level_keys],
    detectedFields: [...context.detected_fields],
    summary: context.summary,
  };
}

function toBackendFileContext(context: ChatInterfaceFileContext): Record<string, unknown> {
  const sheets =
    context.kind === "excel"
      ? (context.sheets ?? []).map((sheet) => ({
          name: sheet.name,
          headers: [...sheet.headers],
          row_count: sheet.rowCount,
        }))
      : [];
  const topLevelKeys =
    context.kind === "json"
      ? context.topLevelKeys && context.topLevelKeys.length > 0
        ? context.topLevelKeys
        : context.detectedFields ?? []
      : [];
  return {
    source: context.source,
    kind: context.kind,
    filename: context.filename,
    size_bytes: context.sizeBytes,
    mime_type: mimeForKind(context.kind),
    row_count: context.rowCount,
    sheet_count: context.sheetCount,
    sheets,
    top_level_keys: topLevelKeys,
    detected_fields: context.detectedFields ?? [],
    summary: context.summary ?? "",
  };
}

function toBackendWhatIfContext(context: ChatInterfaceWhatIfContext): Record<string, unknown> {
  return {
    source: context.source,
    base_message_id: context.baseMessageId,
    base_model_preview_id: context.baseModelPreviewId,
    task_type: context.taskType ?? "unknown",
    variables: {},
    objective: {},
    constraints: {},
    sandbox_status: "skipped",
    summary: context.summary ?? "bounded what-if context",
  };
}

function mimeForKind(kind: string): string {
  if (kind === "excel") return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  if (kind === "json") return "application/json";
  return "text/csv";
}

function parseJsonObject(text: string): { ok: true; value: Record<string, unknown> } | { ok: false } {
  try {
    return { ok: true, value: asRecord(JSON.parse(text)) };
  } catch {
    return { ok: false };
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringOr(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function numberOr(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").map(safeText)
    : [];
}

function localeOr(value: unknown): "zh-CN" | "en-US" | "mixed" {
  return value === "en-US" || value === "mixed" ? value : "zh-CN";
}

function safeText(value: string): string {
  if (
    /(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+|authorization|cookie|password|token|traceback|provider|prompt|[A-Za-z]:\\|\/tmp\/|\/var\/)/i.test(
      value,
    )
  ) {
    return "[filtered]";
  }
  return value.slice(0, 1800);
}

function makeClientRequestId(): string {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `chat-ui-${suffix}`;
}

function makeRecoveryId(): string {
  return `rec_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}
