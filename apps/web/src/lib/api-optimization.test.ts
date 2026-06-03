import { afterEach, describe, expect, it, vi } from "vitest";

import { postOptimization } from "./api";

describe("optimization API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs teaching mode as query mode and preserves teaching response metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          optimization_id: "ee2a9f28-2c7f-4a4d-a54d-43084dc8a7d6",
          status: "completed",
          solution: { x: [0, 10] },
          objective: 10,
          model_version: {
            provider_id: "highs",
            kind: "open_source",
            version: "1.7.0",
            provider_url: "https://highs.dev/",
          },
          solve_seconds: 0.02,
          created_at: "2026-06-04T01:00:00Z",
          completed_at: "2026-06-04T01:00:01Z",
          citation: null,
          ip_attribution: null,
          teaching: {
            mode: "teaching",
            principle_explanation: {
              title_zh: "线性规划教学模式",
              summary_zh: "线性目标函数示例",
              modeling_steps_zh: ["定义变量", "写目标函数", "写约束"],
              limitations_zh: ["仅覆盖线性关系"],
            },
            credits_discount: {
              kind: "teaching",
              label_zh: "50% Credits 折扣",
              discount_multiplier: 0.5,
            },
            notebook: {
              label_zh: "LP 教学 Notebook",
              repo_path: "docs/notebooks/teaching-lp.ipynb",
              colab_url:
                "https://colab.research.google.com/github/proecheng/opticloud/blob/main/docs/notebooks/teaching-lp.ipynb",
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await postOptimization(
      "sk-test",
      {
        task_type: "lp",
        minimize: { c: [1, 1] },
        st: { A: [[1, 1]], b: [10] },
      },
      { mode: "teaching", idempotencyKey: "idem-teaching-1" },
    );

    expect(result.teaching?.mode).toBe("teaching");
    expect(result.teaching?.credits_discount.discount_multiplier).toBe(0.5);
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8002/v1/optimizations?mode=teaching");
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer sk-test");
    expect(headers.get("Idempotency-Key")).toBe("idem-teaching-1");
    expect(headers.get("X-Billing-Charge-Id")).toBeNull();
  });
});
