// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

import { LOCALE_STORAGE_KEY } from "./locale";
import { listAlgorithms, postOptimization, requestAccountDeletion } from "./api";

function getFetchHeaders(fetchMock: { mock: { calls: unknown[][] } }): Headers {
  const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
  return init?.headers as Headers;
}

describe("API client locale header", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("sends zh-CN by default", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await listAlgorithms();

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8002/v1/algorithms",
    );
    expect(getFetchHeaders(fetchMock).get("Accept-Language")).toBe("zh-CN");
  });

  it("sends en-US from stored preference", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en-US");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "none",
          user_id_snapshot: null,
          requested_at: null,
          hard_delete_at: null,
          completed_at: null,
          grace_period_days: 7,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await requestAccountDeletion("jwt-test");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8001/v1/auth/account-deletion",
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe(
      "POST",
    );
    expect(getFetchHeaders(fetchMock).get("Authorization")).toBe(
      "Bearer jwt-test",
    );
    expect(getFetchHeaders(fetchMock).get("Accept-Language")).toBe("en-US");
  });

  it("falls back to zh-CN for unsupported stored preference", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await listAlgorithms();

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8002/v1/algorithms",
    );
    expect(getFetchHeaders(fetchMock).get("Accept-Language")).toBe("zh-CN");
  });

  it("preserves authorization and idempotency headers while adding locale", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en-US");
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000000",
    );
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          optimization_id: "opt-1",
          status: "completed",
          solution: { x: [1] },
          objective: 1,
          model_version: {
            provider_id: "highs",
            kind: "open_source",
            version: "1",
            provider_url: "https://example.com",
          },
          solve_seconds: 0.01,
          created_at: "2026-05-25T00:00:00Z",
          completed_at: "2026-05-25T00:00:00Z",
          citation: null,
          ip_attribution: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await postOptimization("sk-test", {
      task_type: "lp",
      minimize: { c: [1] },
      st: { A: [[1]], b: [1] },
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8002/v1/optimizations",
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe(
      "POST",
    );
    expect(getFetchHeaders(fetchMock).get("Authorization")).toBe(
      "Bearer sk-test",
    );
    expect(getFetchHeaders(fetchMock).get("Idempotency-Key")).toBe(
      "00000000-0000-4000-8000-000000000000",
    );
    expect(getFetchHeaders(fetchMock).get("Accept-Language")).toBe("en-US");
  });
});
