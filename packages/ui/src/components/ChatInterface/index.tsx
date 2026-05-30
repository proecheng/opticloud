"use client";
/** ChatInterface (Tier 2, Story 4.C.6).
 *
 * Adapter-driven Chat UI. The component owns only in-memory UI state; callers own
 * network, internal beta credentials, file parsing, and backend contracts.
 */

import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  RotateCw,
  Send,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ConfirmationModal } from "../ConfirmationModal";
import { FilePicker, type FilePickerRejectReason } from "../FilePicker";
import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type ChatInterfaceLocale = "zh-CN" | "en-US" | "mixed";
export type ChatInterfaceFileKind = "csv" | "excel" | "json";
export type ChatInterfaceMessageRole = "user" | "assistant";
export type ChatInterfaceMessageStatus =
  | "pending"
  | "streaming"
  | "complete"
  | "error"
  | "incomplete";

export interface ChatInterfaceFileContext {
  source: "parsed_browser_file_context_v1";
  kind: ChatInterfaceFileKind;
  filename: string;
  sizeBytes: number;
  rowCount: number;
  sheetCount: number;
  sheets?: ChatInterfaceFileSheetContext[];
  topLevelKeys?: string[];
  detectedFields?: string[];
  summary?: string;
}

export interface ChatInterfaceFileSheetContext {
  name: string;
  headers: string[];
  rowCount: number;
}

export interface ChatInterfaceFileContextPreview {
  fileCount: number;
  kinds: ChatInterfaceFileKind[];
  totalRows: number;
  filenames: string[];
  detectedFields: string[];
}

export interface ChatInterfaceRecoveryAction {
  action: "replace_failed_rows" | "retry_all" | "cancel";
  label: string;
}

export interface ChatInterfaceRecoveryInvalidRow {
  rowNumber: number;
  dataRowNumber: number;
  fieldPath: string;
  constraint: string;
  remediationHintKey: string;
}

export interface ChatInterfaceRecoveryState {
  recoveryId: string;
  filename: string;
  invalidRowCount: number;
  invalidRows: ChatInterfaceRecoveryInvalidRow[];
  actions: ChatInterfaceRecoveryAction[];
}

export type ChatInterfaceFileSelectionResult =
  | { status: "ready"; context: ChatInterfaceFileContext }
  | (ChatInterfaceRecoveryState & { status: "recovery_required" })
  | { status: "rejected"; message: string }
  | { status: "canceled" };

export interface ChatInterfaceModelAction {
  kind: "confirm" | "edit" | "cancel";
  labelZh: string;
  labelEn: string;
  enabled: boolean;
  clientAction: string;
  disabledReasonCode?: string | null;
}

export interface ChatInterfaceModelValidationError {
  fieldPath: string;
  message: string;
  remediationHintKey?: string | null;
}

export interface ChatInterfaceModelPreview {
  previewId: string;
  status: string;
  taskType?: string;
  criticConfidence?: number;
  sandboxStatus?: string;
  actions?: ChatInterfaceModelAction[];
  validationErrors?: ChatInterfaceModelValidationError[];
}

export interface ChatInterfaceWhatIfPreview {
  status: string;
  changeSummary: string;
  changedFields?: string[];
}

export interface ChatInterfaceWhatIfContext {
  source: string;
  baseMessageId: string;
  baseModelPreviewId: string;
  taskType?: string;
  summary?: string;
}

export interface ChatInterfaceResponse {
  messageId: string;
  locale: ChatInterfaceLocale;
  content: string;
  modelPreview?: ChatInterfaceModelPreview;
  fileContextPreview?: ChatInterfaceFileContextPreview | null;
  whatIfPreview?: ChatInterfaceWhatIfPreview | null;
  aigcGate?: Record<string, unknown>;
}

export type ChatInterfaceStreamEvent =
  | { type: "heartbeat" }
  | { type: "message_start"; messageId: string; locale: ChatInterfaceLocale }
  | { type: "content_delta"; chunk: string }
  | { type: "done"; response: ChatInterfaceResponse }
  | { type: "error"; message: string }
  | { type: "unknown"; event?: string };

export type ChatInterfaceSendResult =
  | { mode: "complete"; response: ChatInterfaceResponse }
  | { mode: "stream"; events: AsyncIterable<ChatInterfaceStreamEvent> };

export interface ChatInterfaceSendRequest {
  message: string;
  locale?: ChatInterfaceLocale;
  fileContexts: ChatInterfaceFileContext[];
  whatIfContext?: ChatInterfaceWhatIfContext | null;
}

export interface ChatInterfaceMessage {
  id: string;
  role: ChatInterfaceMessageRole;
  status: ChatInterfaceMessageStatus;
  content: string;
  messageId?: string;
  locale?: ChatInterfaceLocale;
  modelPreview?: ChatInterfaceModelPreview;
  fileContextPreview?: ChatInterfaceFileContextPreview | null;
  whatIfPreview?: ChatInterfaceWhatIfPreview | null;
  localModelState?: "confirmed" | "canceled";
}

export interface ChatInterfaceProps {
  ariaLabel: string;
  initialMessages?: ChatInterfaceMessage[];
  initialRecovery?: ChatInterfaceRecoveryState;
  locale?: ChatInterfaceLocale;
  disabled?: boolean;
  className?: string;
  onSendMessage: (request: ChatInterfaceSendRequest) => Promise<ChatInterfaceSendResult>;
  onSelectFile: (file: File) => Promise<ChatInterfaceFileSelectionResult>;
  onReplaceFailedRows?: (
    recoveryId: string,
    replacementCsv: string,
  ) => Promise<ChatInterfaceFileSelectionResult>;
  onDiscardRecovery?: (recoveryId: string) => void;
  buildWhatIfContext?: (message: ChatInterfaceMessage) => ChatInterfaceWhatIfContext | null;
}

const MAX_DRAFT_CHARS = 2000;
const MAX_FILE_CONTEXTS = 3;

interface ChatInterfacePendingFile {
  id: string;
  context: ChatInterfaceFileContext;
}

export function ChatInterface({
  ariaLabel,
  initialMessages = [],
  initialRecovery,
  locale = "zh-CN",
  disabled = false,
  className,
  onSendMessage,
  onSelectFile,
  onReplaceFailedRows,
  onDiscardRecovery,
  buildWhatIfContext,
}: ChatInterfaceProps): JSX.Element {
  const a11y = useA11y({ ariaLabel, role: "region" });
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [messages, setMessages] = useState<ChatInterfaceMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [pendingFiles, setPendingFiles] = useState<ChatInterfacePendingFile[]>([]);
  const [draftWhatIfContext, setDraftWhatIfContext] =
    useState<ChatInterfaceWhatIfContext | null>(null);
  const [recovery, setRecovery] = useState<ChatInterfaceRecoveryState | null>(
    initialRecovery ?? null,
  );
  const recoveryRef = useRef<ChatInterfaceRecoveryState | null>(initialRecovery ?? null);
  const discardRecoveryRef = useRef(onDiscardRecovery);
  const [replacementCsv, setReplacementCsv] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  useEffect(() => {
    discardRecoveryRef.current = onDiscardRecovery;
  }, [onDiscardRecovery]);

  useEffect(() => {
    recoveryRef.current = recovery;
  }, [recovery]);

  useEffect(
    () => () => {
      const activeRecovery = recoveryRef.current;
      if (activeRecovery) discardRecoveryRef.current?.(activeRecovery.recoveryId);
    },
    [],
  );

  const canSend = normalizeDraft(draft).length >= 2 && !disabled && !isSending;

  const submit = (): void => {
    const message = normalizeDraft(draft);
    if (message.length < 2 || message.length > MAX_DRAFT_CHARS || disabled || isSending) {
      return;
    }
    const userMessage: ChatInterfaceMessage = {
      id: makeLocalId("user"),
      role: "user",
      status: "complete",
      content: message,
    };
    const assistantId = makeLocalId("assistant");
    const assistantMessage: ChatInterfaceMessage = {
      id: assistantId,
      role: "assistant",
      status: "pending",
      content: "",
    };
    const sentFiles = pendingFiles.map((file) => ({
      id: file.id,
      context: cloneFileContext(file.context),
    }));
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setDraft("");
    setDraftWhatIfContext(null);
    setIsSending(true);
    void runSend(
      {
        message,
        locale,
        fileContexts: sentFiles.map((file) => file.context),
        whatIfContext: draftWhatIfContext,
      },
      assistantId,
      sentFiles.map((file) => file.id),
    );
  };

  const runSend = async (
    request: ChatInterfaceSendRequest,
    assistantId: string,
    sentFileIds: string[],
  ): Promise<void> => {
    let completed = false;
    let failed = false;
    try {
      const result = await onSendMessage(request);
      if (result.mode === "complete") {
        completed = true;
        applyResponse(assistantId, result.response);
        clearSentFileContexts(sentFileIds);
        return;
      }

      for await (const event of result.events) {
        if (event.type === "heartbeat") continue;
        if (event.type === "message_start") {
          patchMessage(assistantId, {
            status: "streaming",
            messageId: event.messageId,
            locale: event.locale,
          });
        } else if (event.type === "content_delta") {
          appendAssistantChunk(assistantId, event.chunk);
        } else if (event.type === "done") {
          completed = true;
          applyResponse(assistantId, event.response);
          clearSentFileContexts(sentFileIds);
        } else if (event.type === "error") {
          failed = true;
          patchMessage(assistantId, {
            status: "error",
            content: safeErrorText(event.message),
          });
        }
      }
      if (!completed && !failed) {
        patchMessage(assistantId, {
          status: "incomplete",
          content: "响应未完成，请重试。",
        });
      }
    } catch {
      if (!completed) {
        patchMessage(assistantId, {
          status: "error",
          content: "请求失败，请检查 internal beta 配置后重试。",
        });
      }
    } finally {
      setIsSending(false);
      requestAnimationFrame(() => composerRef.current?.focus());
    }
  };

  const applyResponse = (assistantId: string, response: ChatInterfaceResponse): void => {
    setMessages((current) =>
      current.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              status: "complete",
              content: response.content || message.content,
              messageId: response.messageId,
              locale: response.locale,
              modelPreview: response.modelPreview,
              fileContextPreview: response.fileContextPreview ?? null,
              whatIfPreview: response.whatIfPreview ?? null,
            }
          : message,
      ),
    );
  };

  const patchMessage = (
    id: string,
    patch: Partial<ChatInterfaceMessage>,
  ): void => {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    );
  };

  const appendAssistantChunk = (id: string, chunk: string): void => {
    setMessages((current) =>
      current.map((message) =>
        message.id === id
          ? { ...message, status: "streaming", content: `${message.content}${chunk}` }
          : message,
      ),
    );
  };

  const clearSentFileContexts = (sentFileIds: string[]): void => {
    if (sentFileIds.length === 0) return;
    const sent = new Set(sentFileIds);
    setPendingFiles((current) => current.filter((file) => !sent.has(file.id)));
  };

  const handleSelectedFile = (file: File): void => {
    setFileError(null);
    void (async () => {
      try {
        const result = await onSelectFile(file);
        applyFileSelection(result);
      } catch {
        setFileError("文件解析失败，请检查格式后重试。");
      }
    })();
  };

  const applyFileSelection = (
    result: ChatInterfaceFileSelectionResult,
    options: { discardExistingRecovery?: boolean } = {},
  ): void => {
    if (result.status === "ready") {
      if (options.discardExistingRecovery !== false && recovery) {
        discardRecoveryRef.current?.(recovery.recoveryId);
      }
      recoveryRef.current = null;
      setRecovery(null);
      setReplacementCsv("");
      setPendingFiles((current) =>
        [
          ...current,
          { id: makeLocalId("file"), context: cloneFileContext(result.context) },
        ].slice(0, MAX_FILE_CONTEXTS),
      );
      return;
    }
    if (result.status === "recovery_required") {
      if (recovery && recovery.recoveryId !== result.recoveryId) {
        discardRecoveryRef.current?.(recovery.recoveryId);
      }
      const nextRecovery = {
        recoveryId: result.recoveryId,
        filename: result.filename,
        invalidRowCount: result.invalidRowCount,
        invalidRows: result.invalidRows,
        actions: result.actions,
      };
      recoveryRef.current = nextRecovery;
      setRecovery(nextRecovery);
      return;
    }
    if (result.status === "rejected") {
      setFileError(safeErrorText(result.message));
    }
  };

  const replaceRows = (): void => {
    if (!recovery || !onReplaceFailedRows) return;
    void (async () => {
      try {
        const result = await onReplaceFailedRows(recovery.recoveryId, replacementCsv);
        setReplacementCsv("");
        applyFileSelection(result, { discardExistingRecovery: false });
      } catch {
        setFileError("替换失败，请检查 CSV 后重试。");
      }
    })();
  };

  const retryAll = (): void => {
    if (recovery) discardRecoveryRef.current?.(recovery.recoveryId);
    recoveryRef.current = null;
    setReplacementCsv("");
    setRecovery(null);
  };

  const cancelRecovery = (): void => {
    if (recovery) discardRecoveryRef.current?.(recovery.recoveryId);
    recoveryRef.current = null;
    setReplacementCsv("");
    setRecovery(null);
  };

  const clearHistory = (): void => {
    if (recovery) discardRecoveryRef.current?.(recovery.recoveryId);
    recoveryRef.current = null;
    setMessages([]);
    setPendingFiles([]);
    setDraftWhatIfContext(null);
    setRecovery(null);
    setReplacementCsv("");
    setFileError(null);
    setDraft("");
  };

  const rejectFile = (reason: FilePickerRejectReason): void => {
    setFileError(safeErrorText(reason.message));
  };

  const startWhatIf = (message: ChatInterfaceMessage): void => {
    if (!buildWhatIfContext) return;
    const context = buildWhatIfContext(message);
    if (!context) return;
    setDraftWhatIfContext(context);
    setDraft((current) => current || "基于上一个模型预览做 what-if：");
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  return (
    <section
      {...a11y.attrs}
      ref={a11y.ref}
      className={cn(
        "flex min-h-[620px] flex-col rounded-md border border-border bg-background text-foreground",
        className,
      )}
      data-testid="chat-interface"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-base font-semibold">Internal beta Chat</h2>
          <p className="text-xs text-muted-foreground">仅限受信 internal beta 使用</p>
        </div>
        <button
          type="button"
          onClick={clearHistory}
          className="inline-flex min-h-touch items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
          aria-label="清空历史"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          清空历史
        </button>
      </header>

      <div
        className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
        aria-live="polite"
        aria-atomic="false"
        data-testid="chat-history"
      >
        {messages.length === 0 ? (
          <div
            data-testid="chat-empty-state"
            className="flex min-h-[220px] flex-col items-center justify-center rounded-md border border-dashed border-border p-6 text-center"
          >
            <FileText className="mb-2 h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <h3 className="text-sm font-semibold">暂无对话</h3>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              输入需求或附加 CSV / Excel / JSON 上下文后开始 internal beta 预览。
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onConfirm={() => patchMessage(message.id, { localModelState: "confirmed" })}
              onEdit={() =>
                setDraft(`请调整模型预览 ${message.modelPreview?.previewId ?? ""}: `)
              }
              onCancel={() => patchMessage(message.id, { localModelState: "canceled" })}
              onWhatIf={
                message.role === "assistant" &&
                message.status === "complete" &&
                Boolean(message.messageId) &&
                Boolean(message.modelPreview) &&
                buildWhatIfContext
                  ? () => startWhatIf(message)
                  : undefined
              }
            />
          ))
        )}
      </div>

      <div className="border-t border-border px-4 py-3">
        {fileError && (
          <div className="mb-3 rounded-md border border-danger bg-danger/5 p-3 text-sm text-danger">
            {fileError}
          </div>
        )}
        {pendingFiles.length > 0 && (
          <div
            className="mb-3 flex flex-wrap gap-2"
            data-testid="chat-pending-files"
            aria-label="待发送文件上下文"
          >
            {pendingFiles.map((pendingFile) => {
              const file = pendingFile.context;
              return (
              <span
                key={pendingFile.id}
                className="inline-flex max-w-full items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs"
              >
                <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="min-w-0 truncate">{file.filename}</span>
                <span className="shrink-0 text-muted-foreground">
                  {file.kind} rows={file.rowCount}
                  {file.sheetCount > 0 ? ` sheets=${file.sheetCount}` : ""}
                </span>
                {file.detectedFields && file.detectedFields.length > 0 && (
                  <span className="min-w-0 truncate text-muted-foreground">
                    fields={file.detectedFields.slice(0, 3).join(", ")}
                  </span>
                )}
              </span>
              );
            })}
          </div>
        )}
        {draftWhatIfContext && (
          <div
            className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs"
            data-testid="chat-what-if-context"
          >
            <span className="font-medium">What-if 上下文已选择</span>
            <span className="min-w-0 truncate text-muted-foreground">
              base={draftWhatIfContext.baseModelPreviewId}
            </span>
            <button
              type="button"
              onClick={() => setDraftWhatIfContext(null)}
              className="ml-auto min-h-touch rounded-md border border-border px-2 py-1 hover:bg-background"
              aria-label="清除 What-if 上下文"
            >
              清除
            </button>
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-sm font-medium">输入消息</span>
            <textarea
              ref={composerRef}
              aria-label="输入消息"
              value={draft}
              maxLength={MAX_DRAFT_CHARS}
              disabled={disabled}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              rows={3}
              className="min-h-[92px] w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="例如：如果车辆数 +1，会怎样？"
            />
          </label>
          <div className="flex flex-row items-end gap-2 md:flex-col md:justify-end">
            <FilePicker
              ariaLabel="chat.file_picker"
              label="添加文件"
              onFile={handleSelectedFile}
              onReject={rejectFile}
            />
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              className={cn(
                "inline-flex min-h-touch items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold",
                canSend
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "cursor-not-allowed bg-muted text-muted-foreground",
              )}
              aria-label="发送"
            >
              {isSending ? (
                <RotateCw className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-4 w-4" aria-hidden="true" />
              )}
              发送
            </button>
          </div>
        </div>
      </div>

      <RecoveryModal
        recovery={recovery}
        replacementCsv={replacementCsv}
        onReplacementCsv={setReplacementCsv}
        onReplace={replaceRows}
        onRetryAll={retryAll}
        onCancel={cancelRecovery}
      />
    </section>
  );
}

function MessageBubble({
  message,
  onConfirm,
  onEdit,
  onCancel,
  onWhatIf,
}: {
  message: ChatInterfaceMessage;
  onConfirm: () => void;
  onEdit: () => void;
  onCancel: () => void;
  onWhatIf?: () => void;
}): JSX.Element {
  const isUser = message.role === "user";
  return (
    <article
      className={cn(
        "rounded-md border p-3",
        isUser ? "ml-auto max-w-[85%] border-primary bg-primary/5" : "mr-auto border-border",
      )}
      data-testid={message.status === "error" ? "chat-error-message" : "chat-message"}
    >
      <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span>{isUser ? "用户" : "助手"}</span>
        <span>{statusLabel(message.status)}</span>
      </div>
      <p className="whitespace-pre-wrap break-words text-sm">
        {message.content || (message.status === "pending" ? "等待响应..." : "")}
      </p>
      {message.status === "streaming" && (
        <div className="mt-2 inline-flex items-center gap-2 text-xs text-primary">
          <RotateCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          正在生成
        </div>
      )}
      {message.status === "incomplete" && (
        <div className="mt-2 inline-flex items-center gap-2 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          响应未完成
        </div>
      )}
      {message.modelPreview && (
        <ModelPreviewPanel
          preview={message.modelPreview}
          localState={message.localModelState}
          onConfirm={onConfirm}
          onEdit={onEdit}
          onCancel={onCancel}
        />
      )}
      {onWhatIf && (
        <button
          type="button"
          onClick={onWhatIf}
          className="mt-3 min-h-touch rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
        >
          What-if
        </button>
      )}
      {message.fileContextPreview && (
        <div
          data-testid="chat-file-preview"
          className="mt-3 rounded-md border border-border bg-muted/30 p-3 text-xs"
        >
          <div className="font-semibold">文件上下文</div>
          <div className="mt-1 break-words">
            {message.fileContextPreview.filenames.join(", ")} · rows=
            {message.fileContextPreview.totalRows}
          </div>
        </div>
      )}
      {message.whatIfPreview && (
        <div className="mt-3 rounded-md border border-border bg-muted/30 p-3 text-xs">
          <div className="font-semibold">What-if</div>
          <div>{message.whatIfPreview.changeSummary}</div>
        </div>
      )}
    </article>
  );
}

function ModelPreviewPanel({
  preview,
  localState,
  onConfirm,
  onEdit,
  onCancel,
}: {
  preview: ChatInterfaceModelPreview;
  localState?: "confirmed" | "canceled";
  onConfirm: () => void;
  onEdit: () => void;
  onCancel: () => void;
}): JSX.Element {
  const actions = preview.actions ?? [];
  return (
    <div
      data-testid="chat-model-preview"
      className="mt-3 rounded-md border border-border bg-muted/30 p-3 text-xs"
    >
      <div className="flex flex-wrap items-center gap-2 font-semibold">
        <span>模型预览</span>
        <span className="font-mono">{preview.previewId}</span>
        <span>{preview.status}</span>
        {localState === "confirmed" && (
          <span className="inline-flex items-center gap-1 text-success">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            已确认
          </span>
        )}
        {localState === "canceled" && <span className="text-muted-foreground">已取消</span>}
      </div>
      <dl className="mt-2 grid gap-2 sm:grid-cols-3">
        <KeyValue label="task" value={preview.taskType ?? "-"} />
        <KeyValue
          label="confidence"
          value={
            typeof preview.criticConfidence === "number"
              ? preview.criticConfidence.toFixed(2)
              : "-"
          }
        />
        <KeyValue label="sandbox" value={preview.sandboxStatus ?? "-"} />
      </dl>
      {actions.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {actions.map((action) => (
            <button
              key={action.kind}
              type="button"
              disabled={!action.enabled}
              onClick={
                action.kind === "confirm"
                  ? onConfirm
                  : action.kind === "edit"
                    ? onEdit
                    : onCancel
              }
              className="min-h-touch rounded-md border border-border px-3 py-2 text-sm hover:bg-background disabled:cursor-not-allowed disabled:opacity-50"
            >
              {action.labelZh}
            </button>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-muted-foreground">完整模型动作不可用</p>
      )}
      {preview.validationErrors && preview.validationErrors.length > 0 && (
        <ul className="mt-2 space-y-1 text-danger">
          {preview.validationErrors.slice(0, 10).map((error) => (
            <li key={`${error.fieldPath}-${error.message}`}>
              {error.fieldPath}: {error.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RecoveryModal({
  recovery,
  replacementCsv,
  onReplacementCsv,
  onReplace,
  onRetryAll,
  onCancel,
}: {
  recovery: ChatInterfaceRecoveryState | null;
  replacementCsv: string;
  onReplacementCsv: (value: string) => void;
  onReplace: () => void;
  onRetryAll: () => void;
  onCancel: () => void;
}): JSX.Element | null {
  if (!recovery) return null;
  const first = recovery.invalidRows[0];
  return (
    <ConfirmationModal
      open
      onClose={onCancel}
      onConfirm={onReplace}
      ariaLabel="chat.partial_upload_recovery"
      variant="generic"
      title="CSV 部分校验失败"
      description={
        first
          ? `文件 ${recovery.filename} 第 ${first.dataRowNumber} 条数据行需要修正`
          : `文件 ${recovery.filename} 需要修正`
      }
      confirmLabel="仅替换失败行"
      cancelLabel="取消"
      body={
        <div className="space-y-3">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
            <div>失败行数：{recovery.invalidRowCount}</div>
            {first && (
              <div className="mt-1 break-words">
                {first.fieldPath} · {first.constraint}
              </div>
            )}
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              替换行 CSV
            </span>
            <textarea
              aria-label="替换行 CSV"
              value={replacementCsv}
              onChange={(event) => onReplacementCsv(event.target.value)}
              rows={3}
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
            />
          </label>
          <button
            type="button"
            onClick={onRetryAll}
            data-testid="chat-retry-all"
            className="min-h-touch rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
          >
            全部重试
          </button>
        </div>
      }
    />
  );
}

function KeyValue({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words font-medium">{value}</dd>
    </div>
  );
}

function cloneFileContext(context: ChatInterfaceFileContext): ChatInterfaceFileContext {
  return {
    ...context,
    sheets: context.sheets
      ? context.sheets.map((sheet) => ({
          ...sheet,
          headers: [...sheet.headers],
        }))
      : undefined,
    topLevelKeys: context.topLevelKeys ? [...context.topLevelKeys] : undefined,
    detectedFields: context.detectedFields ? [...context.detectedFields] : undefined,
  };
}

function normalizeDraft(value: string): string {
  return value.trim().slice(0, MAX_DRAFT_CHARS);
}

function makeLocalId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function statusLabel(status: ChatInterfaceMessageStatus): string {
  return {
    pending: "等待中",
    streaming: "流式生成中",
    complete: "完成",
    error: "错误",
    incomplete: "未完成",
  }[status];
}

function safeErrorText(value: string): string {
  if (
    /(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+|authorization|cookie|password|token|traceback|provider|prompt|[A-Za-z]:\\|\/tmp\/|\/var\/)/i.test(
      value,
    )
  ) {
    return "请求失败，请检查 internal beta 配置后重试。";
  }
  return value.slice(0, 160);
}
