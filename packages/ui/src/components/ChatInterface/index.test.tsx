import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ChatInterface,
  type ChatInterfaceFileSelectionResult,
  type ChatInterfaceSendResult,
  type ChatInterfaceStreamEvent,
} from "./index";

async function* streamEvents(): AsyncIterable<ChatInterfaceStreamEvent> {
  yield { type: "message_start", messageId: "msg_stream", locale: "zh-CN" };
  yield { type: "content_delta", chunk: "已读取" };
  yield { type: "content_delta", chunk: "上传文件上下文" };
  yield {
    type: "done",
    response: {
      messageId: "msg_stream",
      locale: "zh-CN",
      content: "已读取上传文件上下文",
      modelPreview: {
        previewId: "mpv_0123456789abcdef",
        status: "ready_to_confirm",
        taskType: "vrptw",
        criticConfidence: 0.91,
        sandboxStatus: "succeeded",
        actions: [
          {
            kind: "confirm",
            labelZh: "确认模型",
            labelEn: "Confirm model",
            enabled: true,
            clientAction: "chat.model_preview.confirm",
          },
          {
            kind: "edit",
            labelZh: "编辑模型",
            labelEn: "Edit model",
            enabled: true,
            clientAction: "chat.model_preview.edit",
          },
          {
            kind: "cancel",
            labelZh: "取消",
            labelEn: "Cancel",
            enabled: true,
            clientAction: "chat.model_preview.cancel",
          },
        ],
      },
      fileContextPreview: {
        fileCount: 1,
        kinds: ["csv"],
        totalRows: 24,
        filenames: ["demand.csv"],
        detectedFields: ["sku", "month", "demand"],
      },
    },
  };
}

async function* streamEventsWithEmptyDoneContent(): AsyncIterable<ChatInterfaceStreamEvent> {
  yield { type: "message_start", messageId: "msg_empty_done", locale: "zh-CN" };
  yield { type: "content_delta", chunk: "分段" };
  yield { type: "content_delta", chunk: "响应" };
  yield {
    type: "done",
    response: {
      messageId: "msg_empty_done",
      locale: "zh-CN",
      content: "",
      modelPreview: {
        previewId: "mpv_empty_done",
        status: "ready_to_confirm",
      },
    },
  };
}

async function* streamEventsWithError(): AsyncIterable<ChatInterfaceStreamEvent> {
  yield { type: "message_start", messageId: "msg_error", locale: "zh-CN" };
  yield { type: "content_delta", chunk: "部分内容" };
  yield { type: "error", message: "stream cursor is invalid for this response" };
}

function completeResponse(content = "模型预览已生成"): ChatInterfaceSendResult {
  return {
    mode: "complete",
    response: {
      messageId: "msg_complete",
      locale: "zh-CN",
      content,
      modelPreview: {
        previewId: "mpv_aaaaaaaaaaaaaaaa",
        status: "needs_clarification",
        taskType: "unknown",
        criticConfidence: 0.4,
        sandboxStatus: "skipped",
        actions: [
          {
            kind: "confirm",
            labelZh: "确认模型",
            labelEn: "Confirm model",
            enabled: false,
            clientAction: "chat.model_preview.confirm",
            disabledReasonCode: "needs_clarification",
          },
          {
            kind: "edit",
            labelZh: "编辑模型",
            labelEn: "Edit model",
            enabled: true,
            clientAction: "chat.model_preview.edit",
          },
          {
            kind: "cancel",
            labelZh: "取消",
            labelEn: "Cancel",
            enabled: true,
            clientAction: "chat.model_preview.cancel",
          },
        ],
      },
    },
  };
}

describe("ChatInterface", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("sends a trimmed message, streams deltas, and restores composer focus", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn().mockResolvedValue({
      mode: "stream",
      events: streamEvents(),
    } satisfies ChatInterfaceSendResult);

    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    const composer = screen.getByLabelText("输入消息");
    await user.type(composer, "  如果车辆数 +1?  ");
    await user.keyboard("{Enter}");

    expect(onSendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ message: "如果车辆数 +1?" }),
    );
    await screen.findByText("已读取上传文件上下文");
    expect(screen.getByTestId("chat-model-preview")).toHaveTextContent(
      "ready_to_confirm",
    );
    expect(screen.getByTestId("chat-file-preview")).toHaveTextContent("demand.csv");
    expect(document.activeElement).toBe(composer);
  });

  it("keeps streamed deltas when the done event has empty content", async () => {
    const onSendMessage = vi.fn().mockResolvedValue({
      mode: "stream",
      events: streamEventsWithEmptyDoneContent(),
    } satisfies ChatInterfaceSendResult);

    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "生成响应" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("分段响应")).toBeInTheDocument();
    expect(screen.getAllByText("完成").length).toBeGreaterThan(0);
  });

  it("keeps stream error events in error state instead of incomplete", async () => {
    const onSendMessage = vi.fn().mockResolvedValue({
      mode: "stream",
      events: streamEventsWithError(),
    } satisfies ChatInterfaceSendResult);

    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "触发流式错误" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByTestId("chat-error-message")).toHaveTextContent(
      "stream cursor is invalid for this response",
    );
    expect(screen.queryByText("响应未完成")).not.toBeInTheDocument();
  });


  it("uses Shift+Enter for newline and rejects drafts shorter than two chars", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    const composer = screen.getByLabelText("输入消息");
    await user.type(composer, "a");
    await user.keyboard("{Enter}");
    expect(onSendMessage).not.toHaveBeenCalled();

    await user.clear(composer);
    await user.type(composer, "第一行");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(composer, "第二行");
    expect(composer).toHaveValue("第一行\n第二行");
  });

  it("renders file context preview from FilePicker adapter without raw rows", async () => {
    const onSelectFile = vi
      .fn<(file: File) => Promise<ChatInterfaceFileSelectionResult>>()
      .mockResolvedValue({
      status: "ready",
      context: {
        source: "parsed_browser_file_context_v1",
        kind: "csv",
        filename: "safe.csv",
        sizeBytes: 512,
        rowCount: 2,
        sheetCount: 0,
        detectedFields: ["sku", "month"],
        summary: "csv rows=2 headers=sku, month",
      },
    });
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={vi.fn().mockResolvedValue(completeResponse())}
        onSelectFile={onSelectFile}
      />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["sku,month\nSKU-01,2026-01"], "safe.csv", {
      type: "text/csv",
    });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    fireEvent.change(input);

    await screen.findByTestId("chat-pending-files");
    expect(screen.getByTestId("chat-pending-files")).toHaveTextContent("safe.csv");
    expect(screen.getByTestId("chat-pending-files")).toHaveTextContent(
      "fields=sku, month",
    );
    expect(screen.queryByText("SKU-01")).not.toBeInTheDocument();
  });

  it("does not clear files selected while a prior request is still streaming", async () => {
    let resolveSend: ((result: ChatInterfaceSendResult) => void) | undefined;
    const onSelectFile = vi
      .fn<(file: File) => Promise<ChatInterfaceFileSelectionResult>>()
      .mockImplementation((file) =>
        Promise.resolve({
          status: "ready",
          context: {
            source: "parsed_browser_file_context_v1",
            kind: "csv",
            filename: file.name,
            sizeBytes: 128,
            rowCount: 1,
            sheetCount: 0,
            detectedFields: ["sku"],
          },
        }),
      );
    const sendResult = {
      mode: "complete",
      response: {
        messageId: "msg_delayed",
        locale: "zh-CN",
        content: "完成",
      },
    } satisfies ChatInterfaceSendResult;
    const onSendMessage = vi.fn(
      () =>
        new Promise<ChatInterfaceSendResult>((resolve) => {
          resolveSend = resolve;
        }),
    );
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={onSelectFile}
      />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, "files", {
      value: [new File(["a"], "first.csv", { type: "text/csv" })],
      configurable: true,
    });
    fireEvent.change(input);
    expect(await screen.findByText("first.csv")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("输入消息"), { target: { value: "发送" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    Object.defineProperty(input, "files", {
      value: [new File(["b"], "second.csv", { type: "text/csv" })],
      configurable: true,
    });
    fireEvent.change(input);
    expect(await screen.findByText("second.csv")).toBeInTheDocument();

    resolveSend?.(sendResult);
    await screen.findByText("完成");

    expect(screen.queryByText("first.csv")).not.toBeInTheDocument();
    expect(screen.getByText("second.csv")).toBeInTheDocument();
  });

  it("handles partial CSV recovery replace, retry, and cancel", async () => {
    const onSelectFile = vi
      .fn<(file: File) => Promise<ChatInterfaceFileSelectionResult>>()
      .mockResolvedValue({
      status: "recovery_required",
      recoveryId: "rec_1",
      filename: "broken.csv",
      invalidRowCount: 1,
      invalidRows: [
        {
          rowNumber: 848,
          dataRowNumber: 847,
          fieldPath: "rows[847]",
          constraint: "row cell count must match header cell count",
          remediationHintKey: "chat.csv.replace_failed_row",
        },
      ],
      actions: [
        { action: "replace_failed_rows", label: "仅替换失败行" },
        { action: "retry_all", label: "全部重试" },
        { action: "cancel", label: "取消" },
      ],
    });
    const onReplaceFailedRows = vi
      .fn<(recoveryId: string, replacementCsv: string) => Promise<ChatInterfaceFileSelectionResult>>()
      .mockResolvedValue({
        status: "ready",
        context: {
          source: "parsed_browser_file_context_v1",
          kind: "csv",
          filename: "broken.csv",
          sizeBytes: 1024,
          rowCount: 1000,
          sheetCount: 0,
          detectedFields: ["sku", "month", "demand"],
        },
      });
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={vi.fn().mockResolvedValue(completeResponse())}
        onSelectFile={onSelectFile}
        onReplaceFailedRows={onReplaceFailedRows}
      />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, "files", {
      value: [new File(["bad"], "broken.csv", { type: "text/csv" })],
      configurable: true,
    });
    fireEvent.change(input);

    expect(await screen.findByTestId("confirmation-modal")).toHaveTextContent(
      "CSV 部分校验失败",
    );
    fireEvent.change(screen.getByLabelText("替换行 CSV"), {
      target: { value: "SKU-08,2026-08,8470" },
    });
    fireEvent.click(screen.getByRole("button", { name: "仅替换失败行" }));

    await waitFor(() => {
      expect(onReplaceFailedRows).toHaveBeenCalledWith(
        "rec_1",
        "SKU-08,2026-08,8470",
      );
    });
    expect(await screen.findByTestId("chat-pending-files")).toHaveTextContent("1000");

    Object.defineProperty(input, "files", {
      value: [new File(["bad"], "again.csv", { type: "text/csv" })],
      configurable: true,
    });
    fireEvent.change(input);
    expect(await screen.findByTestId("confirmation-modal")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("chat-retry-all"));
    await waitFor(() => {
      expect(screen.queryByTestId("confirmation-modal")).not.toBeInTheDocument();
    });

    Object.defineProperty(input, "files", {
      value: [new File(["bad"], "cancel.csv", { type: "text/csv" })],
      configurable: true,
    });
    fireEvent.change(input);
    expect(await screen.findByTestId("confirmation-modal")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => {
      expect(screen.queryByTestId("confirmation-modal")).not.toBeInTheDocument();
    });
  });

  it("keeps model preview actions local-only and clears local state", async () => {
    const onSendMessage = vi.fn().mockResolvedValue(completeResponse("请补充约束"));
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "求最短路径" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("请补充约束")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "编辑模型" }));
    expect((screen.getByLabelText("输入消息") as HTMLTextAreaElement).value).toContain(
      "mpv_aaaaaaaaaaaaaaaa",
    );
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByTestId("chat-model-preview")).toHaveTextContent("已取消");
    expect(onSendMessage).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "清空历史" }));
    expect(screen.getByTestId("chat-empty-state")).toBeInTheDocument();
  });

  it("uses explicit what-if context only after the user selects it", async () => {
    const onSendMessage = vi.fn().mockResolvedValue(completeResponse("下一步"));
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        initialMessages={[
          {
            id: "assistant-ready",
            role: "assistant",
            status: "complete",
            content: "已有模型",
            messageId: "msg_base",
            modelPreview: {
              previewId: "mpv_base",
              status: "ready_to_confirm",
            },
          },
        ]}
        buildWhatIfContext={(message) => ({
          source: "chat-ui-selected-message",
          baseMessageId: message.messageId ?? "",
          baseModelPreviewId: message.modelPreview?.previewId ?? "",
          taskType: message.modelPreview?.taskType,
          summary: "bounded what-if",
        })}
        onSendMessage={onSendMessage}
        onSelectFile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "普通追问" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => {
      expect(onSendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ whatIfContext: null }),
      );
    });

    const whatIfButton = screen.getAllByRole("button", { name: "What-if" })[0];
    if (!whatIfButton) throw new Error("Expected a what-if button");
    fireEvent.click(whatIfButton);
    expect(screen.getByTestId("chat-what-if-context")).toHaveTextContent("mpv_base");
    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "车辆数 +1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(onSendMessage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          whatIfContext: expect.objectContaining({
            baseMessageId: "msg_base",
            baseModelPreviewId: "mpv_base",
          }),
        }),
      );
    });
  });

  it("turns adapter failures into bounded assistant errors", async () => {
    render(
      <ChatInterface
        ariaLabel="chat.interface"
        onSendMessage={vi.fn().mockRejectedValue(new Error("sk-secret traceback"))}
        onSelectFile={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "求解" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByTestId("chat-error-message")).toHaveTextContent(
      "请求失败",
    );
    expect(screen.queryByText(/sk-secret|traceback/i)).not.toBeInTheDocument();
  });
});
