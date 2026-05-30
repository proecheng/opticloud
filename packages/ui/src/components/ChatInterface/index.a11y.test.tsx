import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { ChatInterface, type ChatInterfaceMessage } from "./index";

const completeMessage: ChatInterfaceMessage = {
  id: "assistant-1",
  role: "assistant",
  status: "complete",
  content: "模型预览已生成",
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
};

describe("ChatInterface a11y", () => {
  it("happy path has no axe violations", async () => {
    const { container } = render(
      <ChatInterface
        ariaLabel="chat.interface"
        initialMessages={[completeMessage]}
        onSendMessage={vi.fn()}
        onSelectFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("streaming path has no axe violations", async () => {
    const { container } = render(
      <ChatInterface
        ariaLabel="chat.interface"
        initialMessages={[
          {
            id: "assistant-streaming",
            role: "assistant",
            status: "streaming",
            content: "正在生成",
          },
        ]}
        onSendMessage={vi.fn()}
        onSelectFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("recovery modal path has no axe violations", async () => {
    const { container } = render(
      <ChatInterface
        ariaLabel="chat.interface"
        initialRecovery={{
          recoveryId: "rec_a11y",
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
        }}
        onSendMessage={vi.fn()}
        onSelectFile={vi.fn()}
        onReplaceFailedRows={vi.fn()}
      />,
    );

    const modal = container.ownerDocument.querySelector(
      '[data-testid="confirmation-modal"]',
    );
    expect(modal).toBeTruthy();
    const results = await axe(modal as HTMLElement);
    expect(results.violations).toHaveLength(0);
  });
});
