import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import {
  ChatInterface,
  type ChatInterfaceFileSelectionResult,
  type ChatInterfaceSendResult,
  type ChatInterfaceStreamEvent,
} from "./index";

const meta = {
  title: "Tier 2/ChatInterface",
  component: ChatInterface,
  parameters: { layout: "fullscreen" },
} satisfies Meta<typeof ChatInterface>;

export default meta;
type Story = StoryObj<typeof meta>;

const completeResult: ChatInterfaceSendResult = {
  mode: "complete",
  response: {
    messageId: "msg_storybook",
    locale: "zh-CN",
    content: "模型预览已生成，请核对后继续。",
    modelPreview: {
      previewId: "mpv_0123456789abcdef",
      status: "needs_clarification",
      taskType: "vrptw",
      criticConfidence: 0.72,
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

async function* streamingEvents(): AsyncIterable<ChatInterfaceStreamEvent> {
  yield { type: "message_start", messageId: "msg_story_stream", locale: "zh-CN" };
  yield { type: "content_delta", chunk: "正在生成 " };
  yield { type: "content_delta", chunk: "模型预览。" };
  yield {
    type: "done",
    response: {
      messageId: "msg_story_stream",
      locale: "zh-CN",
      content: "",
      modelPreview: {
        previewId: "mpv_story_stream",
        status: "ready_to_confirm",
      },
    },
  };
}

const fileContextResult: ChatInterfaceFileSelectionResult = {
  status: "ready",
  context: {
    source: "parsed_browser_file_context_v1",
    kind: "excel",
    filename: "demand-plan.xlsx",
    sizeBytes: 4096,
    rowCount: 120,
    sheetCount: 2,
    sheets: [
      { name: "Demand", headers: ["sku", "month", "demand"], rowCount: 100 },
      { name: "Capacity", headers: ["line", "capacity"], rowCount: 20 },
    ],
    detectedFields: ["sku", "month", "demand", "capacity"],
    summary: "excel rows=120 sheets=Demand, Capacity",
  },
};

export const Default: Story = {
  args: {
    ariaLabel: "chat.interface",
    onSendMessage: async () => completeResult,
    onSelectFile: fn(),
  },
};

export const Streaming: Story = {
  args: {
    ariaLabel: "chat.interface.streaming",
    onSendMessage: async () => ({ mode: "stream", events: streamingEvents() }),
    onSelectFile: fn(),
  },
};

export const WithFileContext: Story = {
  args: {
    ariaLabel: "chat.interface.file",
    onSendMessage: async () => completeResult,
    onSelectFile: async () => fileContextResult,
  },
};

export const RecoveryModal: Story = {
  args: {
    ariaLabel: "chat.interface.recovery",
    initialRecovery: {
      recoveryId: "rec_story",
      filename: "broken.csv",
      invalidRowCount: 1,
      invalidRows: [
        {
          rowNumber: 12,
          dataRowNumber: 11,
          fieldPath: "rows[11]",
          constraint: "row cell count must match header cell count",
          remediationHintKey: "chat.csv.replace_failed_row",
        },
      ],
      actions: [
        { action: "replace_failed_rows", label: "仅替换失败行" },
        { action: "retry_all", label: "全部重试" },
        { action: "cancel", label: "取消" },
      ],
    },
    onSendMessage: async () => completeResult,
    onSelectFile: fn(),
    onReplaceFailedRows: async () => fileContextResult,
  },
};

export const ErrorState: Story = {
  args: {
    ariaLabel: "chat.interface.error",
    initialMessages: [
      { id: "u-error", role: "user", status: "complete", content: "求解" },
      {
        id: "a-error",
        role: "assistant",
        status: "error",
        content: "请求失败，请检查 internal beta 配置后重试。",
      },
    ],
    onSendMessage: async () => completeResult,
    onSelectFile: fn(),
  },
};

export const WithHistory: Story = {
  args: {
    ariaLabel: "chat.interface.history",
    initialMessages: [
      { id: "u1", role: "user", status: "complete", content: "如果车辆数 +1?" },
      {
        id: "a1",
        role: "assistant",
        status: "complete",
        content: "已生成 what-if 预览。",
        modelPreview: completeResult.response.modelPreview,
      },
    ],
    onSendMessage: async () => completeResult,
    onSelectFile: fn(),
  },
};
