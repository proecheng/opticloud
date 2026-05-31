import { afterEach, describe, expect, it, vi } from "vitest";

import { getBillingUsageTrends } from "./api";

const trends = {
  trend_contract: "billing_usage_trends_v1",
  generated_at: "2026-05-31T12:00:00Z",
  windows: [
    {
      window_days: 7,
      window_start: "2026-05-25T00:00:00Z",
      window_end: "2026-06-01T00:00:00Z",
      label: { zh: "近 7 天实际用量支出趋势", en: "Last 7 days actual usage spend trend" },
      currency: "CNY",
      total_actual_spend: "7.00",
      average_daily_spend: "1.00",
      points: [{ date: "2026-05-25", actual_spend: "7.00", currency: "CNY" }],
    },
  ],
};

describe("billing usage trends API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("gets billing usage trends with bearer auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(trends), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getBillingUsageTrends("jwt-test");

    expect(result.trend_contract).toBe("billing_usage_trends_v1");
    expect(result.windows[0]?.window_days).toBe(7);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/usage-trends");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("preserves RFC7807-style errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ title: "Unauthorized", detail: "missing token" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getBillingUsageTrends("bad-jwt")).rejects.toMatchObject({
      status: 401,
      title: "Unauthorized",
      detail: "missing token",
    });
  });
});
