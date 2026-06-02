import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getProviderKpiDashboard,
  getProviderRevenuePayoutDashboard,
  getProviderRouteShareDashboard,
  listProviderApplications,
  listProviderMonthlyRevenueShareBatches,
  listProviderVersionUpdates,
} from "./api";

describe("provider console API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists provider applications with exact query filters and bearer auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await listProviderApplications("jwt-test", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      requestedProviderId: "provider-alpha",
      status: "submitted",
    });

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(
      "http://localhost:8006/v1/provider-applications?tenant_id=11111111-1111-1111-1111-111111111111&requested_provider_id=provider-alpha&status=submitted",
    );
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer jwt-test");
    expect(init?.body).toBeUndefined();
    expect(headers.get("X-Internal-Service-Auth")).toBeNull();
    expect(headers.get("If-Match")).toBeNull();
    expect(headers.get("Idempotency-Key")).toBeNull();
  });

  it("uses existing provider dashboard GET contracts without request bodies", async () => {
    const responses = [
      { status_counts: {}, total_rollouts: 0, current_rollouts: [], timeline: [] },
      { total_runs: 0, run_metrics: [], timeline: [] },
      { status_counts: {}, total_entries: 0, currency_totals: [], period_summaries: [], entries: [] },
    ];
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(responses[0]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(responses[1]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(responses[2]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await getProviderRouteShareDashboard("jwt-test", "provider-alpha", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      from: "2026-06-01T00:00:00Z",
      to: "2026-06-30T23:59:59Z",
    });
    await getProviderKpiDashboard("jwt-test", "provider-alpha", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      from: "2026-06-01T00:00:00Z",
      to: "2026-06-30T23:59:59Z",
    });
    await getProviderRevenuePayoutDashboard("jwt-test", "provider-alpha", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      periodMonth: "2026-06",
      currency: "CNY",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8006/v1/providers/provider-alpha/route-share-dashboard?tenant_id=11111111-1111-1111-1111-111111111111&from=2026-06-01T00%3A00%3A00Z&to=2026-06-30T23%3A59%3A59Z",
      "http://localhost:8006/v1/providers/provider-alpha/kpi-dashboard?tenant_id=11111111-1111-1111-1111-111111111111&from=2026-06-01T00%3A00%3A00Z&to=2026-06-30T23%3A59%3A59Z",
      "http://localhost:8006/v1/providers/provider-alpha/revenue-payout-dashboard?tenant_id=11111111-1111-1111-1111-111111111111&period_month=2026-06&currency=CNY",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.body).toBeUndefined();
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBe("Bearer jwt-test");
      expect(headers.get("X-Internal-Service-Auth")).toBeNull();
      expect(headers.get("If-Match")).toBeNull();
    }
  });

  it("lists version updates and monthly batches with read-only GET calls", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await listProviderVersionUpdates("jwt-test", "app-alpha", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      requestedProviderId: "provider-alpha",
      status: "approved",
      changeKind: "minor",
    });
    await listProviderMonthlyRevenueShareBatches("jwt-test", {
      tenantId: "11111111-1111-1111-1111-111111111111",
      periodMonth: "2026-06",
      status: "approved",
      currency: "CNY",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8006/v1/provider-applications/app-alpha/version-updates?tenant_id=11111111-1111-1111-1111-111111111111&requested_provider_id=provider-alpha&status=approved&change_kind=minor",
      "http://localhost:8006/v1/revenue-share/monthly-batches?tenant_id=11111111-1111-1111-1111-111111111111&period_month=2026-06&status=approved&currency=CNY",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.body).toBeUndefined();
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBe("Bearer jwt-test");
      expect(headers.get("X-Internal-Service-Auth")).toBeNull();
      expect(headers.get("If-Match")).toBeNull();
    }
  });
});
