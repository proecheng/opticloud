// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  streamInternalBetaChatMessage: vi.fn(),
  sendInternalBetaChatMessage: vi.fn(),
}));

vi.mock("@/lib/chat", () => ({
  streamInternalBetaChatMessage: mocks.streamInternalBetaChatMessage,
  sendInternalBetaChatMessage: mocks.sendInternalBetaChatMessage,
  selectChatFile: vi.fn(),
  replaceChatRecoveryRows: vi.fn(),
  discardChatRecovery: vi.fn(),
}));

import ConsoleChatPage from "./page";

async function* streamResult() {
  yield { type: "content_delta" as const, chunk: "已读取" };
  yield {
    type: "done" as const,
    response: {
      messageId: "msg_0123456789abcdef01234567",
      locale: "zh-CN" as const,
      content: "已读取",
      modelPreview: {
        previewId: "mpv_0123456789abcdef",
        status: "ready_to_confirm",
      },
    },
  };
}

describe("ConsoleChatPage", () => {
  it("sends internal beta credentials without saving token to storage", async () => {
    mocks.streamInternalBetaChatMessage.mockReturnValue(streamResult());
    const localSet = vi.spyOn(Storage.prototype, "setItem");

    render(<ConsoleChatPage />);

    fireEvent.change(screen.getByLabelText("Tenant"), {
      target: { value: "research-staging" },
    });
    fireEvent.change(screen.getByLabelText("User"), {
      target: { value: "scholar-a" },
    });
    fireEvent.change(screen.getByLabelText("Token"), {
      target: { value: "internal-beta-token" },
    });
    fireEvent.change(screen.getByLabelText("输入消息"), {
      target: { value: "求最短路径" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(mocks.streamInternalBetaChatMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          credentials: {
            tenant: "research-staging",
            user: "scholar-a",
            token: "internal-beta-token",
          },
          message: "求最短路径",
        }),
      );
    });
    expect(localSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/token|chat/i),
      expect.any(String),
    );
    expect(await screen.findByText("已读取")).toBeTruthy();
  });

  it("falls back to JSON helper when stream fails", async () => {
    mocks.streamInternalBetaChatMessage.mockImplementation(async function* () {
      throw new Error("stream unavailable");
    });
    mocks.sendInternalBetaChatMessage.mockResolvedValue({
      messageId: "msg_json",
      locale: "zh-CN",
      content: "JSON fallback",
    });

    render(<ConsoleChatPage />);

    fireEvent.change(screen.getByLabelText("Tenant"), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText("User"), { target: { value: "u" } });
    fireEvent.change(screen.getByLabelText("Token"), { target: { value: "tok" } });
    fireEvent.change(screen.getByLabelText("输入消息"), { target: { value: "求解" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("JSON fallback")).toBeTruthy();
    expect(mocks.sendInternalBetaChatMessage).toHaveBeenCalled();
  });
});
