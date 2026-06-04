import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getBenchmarkLibraryItem,
  importBenchmarkLibraryItem,
  listBenchmarkLibrary,
} from "./api";

function expectNoPrivateHeaders(init: RequestInit | undefined): void {
  const headers = new Headers(init?.headers);
  expect(headers.get("Authorization")).toBeNull();
  expect(headers.get("X-Billing-Charge-Id")).toBeNull();
  expect(headers.get("Idempotency-Key")).toBeNull();
  expect(headers.get("X-Internal-Service-Auth")).toBeNull();
}

describe("benchmark library API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists benchmark library entries from solver service without private headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await listBenchmarkLibrary();

    expect(result).toEqual([]);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8002/v1/benchmark-library");
    expect(init?.method).toBeUndefined();
    expect(init?.body).toBeUndefined();
    expectNoPrivateHeaders(init);
  });

  it("composes list filters with backend snake_case query params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            benchmark_id: "or-lib-afiro-lp",
            suite: "or-lib",
            domain: "linear-programming",
            task_type: "lp",
            title_zh: "OR-Library AFIRO 线性规划模板",
            title_en: "OR-Library AFIRO linear programming template",
            source_name: "OR-Library",
            source_url: "https://example.com/or-lib",
            license_note_zh: "仅引用来源。",
            import_kind: "optimization_request",
            target_endpoint: "/v1/optimizations",
            discount: {
              kind: "benchmark_library",
              label_zh: "50% Credits 折扣",
              discount_multiplier: 0.5,
              billing_supported: true,
            },
            dataset_ref: "benchmark://or-lib/afiro",
            sample_payload: { task_type: "lp" },
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await listBenchmarkLibrary({
      suite: "or-lib",
      domain: "linear-programming",
      taskType: "lp",
    });

    expect(result[0]?.benchmark_id).toBe("or-lib-afiro-lp");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(
      "http://localhost:8002/v1/benchmark-library?suite=or-lib&domain=linear-programming&task_type=lp",
    );
    expect(init?.body).toBeUndefined();
    expectNoPrivateHeaders(init);
  });

  it("gets and imports encoded benchmark ids without request body or private headers", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            benchmark_id: "or/lib afiro",
            suite: "or-lib",
            domain: "linear-programming",
            task_type: "lp",
            title_zh: "OR-Library AFIRO 线性规划模板",
            title_en: "OR-Library AFIRO linear programming template",
            source_name: "OR-Library",
            source_url: "https://example.com/or-lib",
            license_note_zh: "仅引用来源。",
            import_kind: "optimization_request",
            target_endpoint: "/v1/optimizations",
            discount: {
              kind: "benchmark_library",
              label_zh: "50% Credits 折扣",
              discount_multiplier: 0.5,
              billing_supported: true,
            },
            dataset_ref: "benchmark://or-lib/afiro",
            sample_payload: { task_type: "lp" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            benchmark_id: "or/lib afiro",
            import_kind: "optimization_request",
            target_endpoint: "/v1/optimizations",
            request_payload: {
              task_type: "lp",
              options: {
                benchmark_library: true,
                benchmark_id: "or/lib afiro",
              },
            },
            discount: {
              kind: "benchmark_library",
              label_zh: "50% Credits 折扣",
              discount_multiplier: 0.5,
              billing_supported: true,
            },
            dataset_ref: "benchmark://or-lib/afiro",
            disclaimer_zh: "该 import payload 是最小模板，不是完整数据集镜像。",
            disclaimer_en: "This import payload is a minimal template.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    await getBenchmarkLibraryItem("or/lib afiro");
    const imported = await importBenchmarkLibraryItem("or/lib afiro");

    expect(imported.request_payload).toMatchObject({
      options: { benchmark_library: true, benchmark_id: "or/lib afiro" },
    });
    const [detailUrl, detailInit] = fetchMock.mock.calls[0]!;
    expect(detailUrl).toBe("http://localhost:8002/v1/benchmark-library/or%2Flib%20afiro");
    expect(detailInit?.body).toBeUndefined();
    expectNoPrivateHeaders(detailInit);

    const [importUrl, importInit] = fetchMock.mock.calls[1]!;
    expect(importUrl).toBe(
      "http://localhost:8002/v1/benchmark-library/or%2Flib%20afiro/import",
    );
    expect(importInit?.method).toBe("POST");
    expect(importInit?.body).toBeUndefined();
    expectNoPrivateHeaders(importInit);
  });
});
