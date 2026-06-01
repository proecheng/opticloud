import { afterEach, describe, expect, it, vi } from "vitest";

import { getBillingBudget, putBillingBudget } from "./api";

const budget = {
  budget_control_id: "budget-1",
  enabled: true,
  status: "active",
  monthly_budget_amount: "100.00",
  alert_threshold_ratio: "0.8000",
  period_start: "2026-06-01T00:00:00Z",
  period_end: "2026-07-01T00:00:00Z",
  actual_spend: "70.00",
  percent_used: "0.7000",
  currency: "CNY",
  alert_threshold_reached: false,
  paused: false,
  paused_at: null,
  pause_period_start: null,
  recent_events: [],
};

describe("billing budget API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("gets budget status with bearer auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(budget), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getBillingBudget("jwt-test");

    expect(result.monthly_budget_amount).toBe("100.00");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/budget");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("puts budget status with precise body shape", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ...budget, status: "paused", paused: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await putBillingBudget("jwt-test", {
      monthly_budget_amount: "80.00",
      enabled: true,
    });

    expect(result.paused).toBe(true);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/budget");
    expect(init?.method).toBe("PUT");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(init?.body).toBe(JSON.stringify({ monthly_budget_amount: "80.00", enabled: true }));
  });

  it("preserves RFC7807 errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          title: "Invalid Budget Request",
          detail: "monthly budget request is invalid",
          errors: [
            {
              field_path: "body.monthly_budget_amount",
              value: "0.99",
              constraint: "must be >= 1.00",
              remediation_hint_key: "errors.422.invalid_budget_request",
            },
          ],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      putBillingBudget("jwt-test", { monthly_budget_amount: "0.99", enabled: true }),
    ).rejects.toMatchObject({
      status: 422,
      title: "Invalid Budget Request",
      detail: "monthly budget request is invalid",
      errors: [
        expect.objectContaining({
          field_path: "body.monthly_budget_amount",
        }),
      ],
    });
  });
});
