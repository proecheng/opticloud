import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  normalizeInternalBetaChatResponse,
  parseChatSseBlock,
  sendInternalBetaChatMessage,
  streamInternalBetaChatMessage,
} from "./chat";

const responseBody = {
  message_id: "msg_0123456789abcdef01234567",
  locale: "zh-CN",
  language_preview: {
    summary: "AI 生成内容仅供参考。",
  },
  model_preview: {
    preview_id: "mpv_0123456789abcdef",
    status: "ready_to_confirm",
    task_type: "vrptw",
    critic_confidence: 0.92,
    sandbox_status: "succeeded",
    actions: [
      {
        kind: "confirm",
        label_zh: "确认模型",
        label_en: "Confirm model",
        enabled: true,
        client_action: "chat.model_preview.confirm",
        disabled_reason_code: null,
      },
    ],
    validation_errors: [],
  },
  file_context_preview: {
    file_count: 1,
    kinds: ["csv"],
    total_rows: 24,
    filenames: ["demand.csv"],
    detected_fields: ["sku"],
  },
  what_if_preview: null,
  aigc_gate: { status: "filing_pending", public_surface: "hidden" },
};

describe("chat web adapter", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("normalizes backend JSON response into ChatInterface response", () => {
    const normalized = normalizeInternalBetaChatResponse(responseBody);

    expect(normalized).toMatchObject({
      messageId: "msg_0123456789abcdef01234567",
      locale: "zh-CN",
      content: "AI 生成内容仅供参考。",
      modelPreview: {
        previewId: "mpv_0123456789abcdef",
        status: "ready_to_confirm",
        taskType: "vrptw",
      },
      fileContextPreview: {
        fileCount: 1,
        filenames: ["demand.csv"],
      },
    });
  });

  it("parses heartbeat, message_start, delta, done, and error SSE blocks", () => {
    expect(parseChatSseBlock(":heartbeat")).toEqual({ type: "heartbeat" });
    expect(
      parseChatSseBlock(
        'id: sse_x_000001\nevent: message_start\ndata: {"message_id":"msg_stream","locale":"mixed"}',
      ),
    ).toEqual({ type: "message_start", messageId: "msg_stream", locale: "mixed" });
    expect(
      parseChatSseBlock(
        'id: sse_x_000001\nevent: content_delta\ndata: {"chunk":"你好"}',
      ),
    ).toEqual({ type: "content_delta", chunk: "你好" });
    expect(
      parseChatSseBlock(
        'event: done\ndata: {"message_id":"msg_0123456789abcdef01234567","done":true,"model_preview_id":"mpv_0123456789abcdef","model_preview_status":"blocked","file_context_preview":null,"what_if_preview":null}',
      ),
    ).toMatchObject({
      type: "done",
      response: {
        messageId: "msg_0123456789abcdef01234567",
        modelPreview: {
          previewId: "mpv_0123456789abcdef",
          status: "blocked",
        },
      },
    });
    expect(
      parseChatSseBlock(
        'event: error\ndata: {"message":"stream cursor is invalid for this response"}',
      ),
    ).toEqual({
      type: "error",
      message: "stream cursor is invalid for this response",
    });
    expect(parseChatSseBlock("event: content_delta\ndata: {bad json")).toEqual({
      type: "error",
      message: "流式响应格式无效",
    });
  });

  it("posts internal beta JSON with headers and a bounded body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendInternalBetaChatMessage({
      credentials: {
        tenant: "research-staging",
        user: "scholar-a",
        token: "internal-beta-token",
      },
      message: " 求最短路径 ",
      fileContexts: [],
    });

    expect(result.messageId).toBe("msg_0123456789abcdef01234567");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("X-Internal-Beta-Token")).toBe(
      "internal-beta-token",
    );
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body.message).toBe("求最短路径");
    expect(String(body.client_request_id)).toMatch(/^chat-ui-/);
    expect(JSON.stringify(body)).not.toContain("internal-beta-token");
  });

  it("maps Excel sheets and JSON top-level keys into backend file contexts", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendInternalBetaChatMessage({
      credentials: { tenant: "t", user: "u", token: "tok" },
      message: "使用文件上下文",
      fileContexts: [
        {
          source: "parsed_browser_file_context_v1",
          kind: "excel",
          filename: "demand.xlsx",
          sizeBytes: 4096,
          rowCount: 12,
          sheetCount: 1,
          sheets: [{ name: "Sheet1", headers: ["sku", "month"], rowCount: 12 }],
          detectedFields: ["sku", "month"],
          summary: "excel rows=12 sheets=Sheet1",
        },
        {
          source: "parsed_browser_file_context_v1",
          kind: "json",
          filename: "config.json",
          sizeBytes: 256,
          rowCount: 0,
          sheetCount: 0,
          topLevelKeys: ["objective", "constraints"],
          detectedFields: ["objective", "constraints"],
          summary: "json object keys=objective, constraints",
        },
      ],
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body)) as {
      file_contexts: Array<Record<string, unknown>>;
    };
    expect(body.file_contexts[0]).toMatchObject({
      kind: "excel",
      sheet_count: 1,
      sheets: [{ name: "Sheet1", headers: ["sku", "month"], row_count: 12 }],
      top_level_keys: [],
    });
    expect(body.file_contexts[1]).toMatchObject({
      kind: "json",
      sheets: [],
      top_level_keys: ["objective", "constraints"],
    });
  });

  it("fails closed for sparse 404 without leaking token or schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
      ),
    );

    await expect(
      sendInternalBetaChatMessage({
        credentials: { tenant: "t", user: "u", token: "secret-token" },
        message: "求解",
      }),
    ).rejects.toThrow("Chat internal beta unavailable");
  });

  it("streams via fetch POST instead of EventSource", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(":heartbeat\n\n"));
        controller.enqueue(
          encoder.encode(
            'event: content_delta\ndata: {"chunk":"你好"}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'event: done\ndata: {"message_id":"msg_0123456789abcdef01234567","done":true,"model_preview_id":"mpv_0123456789abcdef","model_preview_status":"ready_to_confirm","file_context_preview":null,"what_if_preview":null}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const eventSourceSpy = vi.fn();
    vi.stubGlobal("EventSource", eventSourceSpy);

    const events: string[] = [];
    for await (const event of streamInternalBetaChatMessage({
      credentials: { tenant: "t", user: "u", token: "tok" },
      message: "求解",
    })) {
      events.push(event.type);
    }

    expect(events).toEqual(["content_delta", "done"]);
    expect(fetchMock).toHaveBeenCalled();
    expect(eventSourceSpy).not.toHaveBeenCalled();
  });

  it("carries message_start locale onto stream done normalization", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: message_start\ndata: {"message_id":"msg_stream","locale":"en-US"}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'event: done\ndata: {"message_id":"msg_stream","done":true,"model_preview_id":"mpv_stream","model_preview_status":"ready_to_confirm","file_context_preview":null,"what_if_preview":null}\n\n',
          ),
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(body, { status: 200 })),
    );

    const events: Awaited<ReturnType<typeof parseChatSseBlock>>[] = [];
    for await (const event of streamInternalBetaChatMessage({
      credentials: { tenant: "t", user: "u", token: "tok" },
      message: "solve",
    })) {
      events.push(event);
    }

    expect(events).toMatchObject([
      { type: "message_start", locale: "en-US" },
      { type: "done", response: { locale: "en-US" } },
    ]);
  });
});
