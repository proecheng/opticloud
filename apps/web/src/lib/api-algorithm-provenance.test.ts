import { afterEach, describe, expect, it, vi } from "vitest";

import { getAlgorithm } from "./api";

function expectNoPrivateHeaders(init: RequestInit | undefined): void {
  const headers = new Headers(init?.headers);
  expect(headers.get("Authorization")).toBeNull();
  expect(headers.get("X-Billing-Charge-Id")).toBeNull();
  expect(headers.get("Idempotency-Key")).toBeNull();
  expect(headers.get("X-Internal-Service-Auth")).toBeNull();
}

describe("algorithm provenance API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("gets algorithm detail with provenance from solver service", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          k_algo: "highs-lp",
          task_type: "lp",
          tier: "T1",
          status: "v1",
          model_version: {
            provider_id: "highs",
            kind: "open_source",
            version: "1.7.0",
            provider_url: "https://highs.dev/",
          },
          description_zh: "HiGHS LP",
          description_en: "HiGHS LP",
          examples: [],
          supported_solvers: ["highs"],
          citation: null,
          ip_attribution: {
            tier: "L3",
            label_zh: "L3",
            display_name_zh: "HiGHS",
            summary_zh: "开源 Runner",
            visibility: "license_only",
            contract_anchor: "docs/legal-templates.md",
          },
          provenance: {
            theory_zh: "线性规划理论",
            theory_en: "Linear programming theory",
            configuration_parameters: [
              {
                name: "建模形式",
                value_zh: "线性目标",
                description_zh: "请求 schema 承载",
                source: "request_schema",
              },
            ],
            applicable_scenarios_zh: ["资源分配"],
            limitations_zh: ["不表达整数变量"],
            citation_source: "catalog_citation",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getAlgorithm("highs-lp");

    expect(result.provenance?.citation_source).toBe("catalog_citation");
    expect(result.provenance?.configuration_parameters[0]?.source).toBe("request_schema");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8002/v1/algorithms/highs-lp");
    expect(init?.body).toBeUndefined();
    expectNoPrivateHeaders(init);
  });
});
