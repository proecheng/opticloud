import { afterEach, describe, expect, it, vi } from "vitest";

import { OptiCloudClientError, postPrediction } from "./api";

describe("prediction API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs prediction requests to solver without billing headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          prediction_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
          status: "completed",
          family: "chronos",
          horizon: 3,
          prediction: {
            p10: [10, 11, 12],
            p50: [12, 13, 14],
            p90: [14, 15, 16],
          },
          drift_score: 0.12,
          disclaimer: {
            zh: "本预测仅供参考",
            en: "This forecast is for reference only",
            bilingual: "本预测仅供参考 / This forecast is for reference only",
          },
          model_version: {
            provider_id: "chronos",
            kind: "open_source",
            version: "mock-v1",
            provider_url: "https://example.com/chronos",
          },
          predict_seconds: 0.03,
          created_at: "2026-05-28T01:00:00Z",
          completed_at: "2026-05-28T01:00:01Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await postPrediction(
      "sk-test",
      { family: "chronos", data: [10, 20, 30], horizon: 3 },
      "idem-prediction-1",
    );

    expect(result.prediction.p50).toEqual([12, 13, 14]);
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8002/v1/predictions");
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer sk-test");
    expect(headers.get("Idempotency-Key")).toBe("idem-prediction-1");
    expect(headers.get("X-Billing-Charge-Id")).toBeNull();
    expect(init?.body).toBe(
      JSON.stringify({ family: "chronos", data: [10, 20, 30], horizon: 3 }),
    );
  });

  it("preserves RFC7807 prediction error details", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          title: "Invalid Prediction Data",
          status: 422,
          detail: "data length must be between 3 and 10000",
          errors: [
            {
              field_path: "data",
              value: 2,
              constraint: "data length must be between 3 and 10000",
              remediation_hint_key: "errors.422.invalid_prediction_data",
            },
          ],
          next_action_url: "https://api.opticloud.cn/docs/errors/prediction-data",
          request_id: "req-abc",
          trace_id: "trace-def",
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      postPrediction(
        "sk-test",
        { family: "chronos", data: [10, 20], horizon: 3 },
        "idem-prediction-2",
      ),
    ).rejects.toMatchObject({
      status: 422,
      title: "Invalid Prediction Data",
      errors: [
        expect.objectContaining({
          field_path: "data",
          constraint: "data length must be between 3 and 10000",
        }),
      ],
      next_action_url: "https://api.opticloud.cn/docs/errors/prediction-data",
      request_id: "req-abc",
      trace_id: "trace-def",
    } satisfies Partial<OptiCloudClientError>);
  });
});
