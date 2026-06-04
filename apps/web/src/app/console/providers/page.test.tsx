// @vitest-environment happy-dom

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listProviderApplications: vi.fn(),
  getProviderRouteShareDashboard: vi.fn(),
  getProviderKpiDashboard: vi.fn(),
  getProviderRevenuePayoutDashboard: vi.fn(),
  listProviderVersionUpdates: vi.fn(),
  listProviderMonthlyRevenueShareBatches: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status: number;
    title: string;
    detail: string;
    constructor(payload: { status: number; title: string; detail: string }) {
      super(payload.detail);
      this.status = payload.status;
      this.title = payload.title;
      this.detail = payload.detail;
    }
  },
  listProviderApplications: mocks.listProviderApplications,
  getProviderRouteShareDashboard: mocks.getProviderRouteShareDashboard,
  getProviderKpiDashboard: mocks.getProviderKpiDashboard,
  getProviderRevenuePayoutDashboard: mocks.getProviderRevenuePayoutDashboard,
  listProviderVersionUpdates: mocks.listProviderVersionUpdates,
  listProviderMonthlyRevenueShareBatches: mocks.listProviderMonthlyRevenueShareBatches,
}));

import ProviderConsolePage from "./page";

const application = {
  id: "00000000-0000-0000-0000-000000000001",
  tenant_id: null,
  application_id: "app-alpha",
  requested_provider_id: "provider-alpha",
  provider_kind: "academic",
  display_name: "Alpha Solver Lab",
  organization_name: "Alpha University",
  contact_email: "provider@example.com",
  homepage_url: "https://example.com",
  openapi_url: "https://example.com/openapi.json",
  openapi_sha256: "a".repeat(64),
  image_digest: `repo/provider@sha256:${"b".repeat(64)}`,
  cosign_bundle: {},
  evaluation_profile: {},
  status: "submitted",
  submitted_at: "2026-06-01T00:00:00Z",
  metadata: {},
  scope_source: "global",
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-02T00:00:00Z",
};

const routeShare = {
  provider_id: "provider-alpha",
  tenant_id: null,
  from_at: null,
  to_at: null,
  status_counts: { draft: 0, active: 1, paused: 0, completed: 1, cancelled: 0 },
  total_rollouts: 2,
  highest_current_stage_percent: 50,
  current_rollouts: [
    {
      application_id: "app-alpha",
      evaluation_id: "eval-alpha",
      run_id: "run-alpha",
      rollout_id: "rollout-alpha",
      status: "active",
      current_stage_percent: 50,
      started_at: "2026-06-01T00:00:00Z",
      completed_at: null,
      paused_at: null,
      cancelled_at: null,
      updated_at: "2026-06-02T00:00:00Z",
      scope_source: "global",
    },
  ],
  timeline: [
    {
      application_id: "app-alpha",
      evaluation_id: "eval-alpha",
      run_id: "run-alpha",
      rollout_id: "rollout-alpha",
      provider_id: "provider-alpha",
      baseline_provider_id: "baseline",
      benchmark_suite: "standard",
      action: "advance",
      stage_percent: 50,
      from_status: "active",
      to_status: "active",
      observed_at: "2026-06-02T00:00:00Z",
      scope_source: "global",
    },
  ],
};

const kpi = {
  provider_id: "provider-alpha",
  tenant_id: null,
  from_at: null,
  to_at: null,
  run_status_counts: { draft: 0, running: 0, passed: 1, failed: 0, cancelled: 0 },
  total_runs: 1,
  aggregate: {
    sample_count: 500,
    success_count: 492,
    failed_count: 8,
    timeout_count: 2,
    provider_error_count: 1,
    success_rate: "0.984000",
    average_deviation_ratio: "0.010000",
    provider_p95_latency_ms: 120,
    baseline_p95_latency_ms: 100,
    p95_latency_ratio: "1.200000",
  },
  rollout_summary: {
    total_rollouts: 2,
    highest_current_stage_percent: 50,
    status_counts: { draft: 0, active: 1, paused: 0, completed: 1, cancelled: 0 },
  },
  run_metrics: [
    {
      application_id: "app-alpha",
      evaluation_id: "eval-alpha",
      run_id: "run-alpha",
      provider_id: "provider-alpha",
      baseline_provider_id: "baseline",
      benchmark_suite: "standard",
      status: "passed",
      started_at: "2026-06-01T00:00:00Z",
      ended_at: "2026-06-02T00:00:00Z",
      updated_at: "2026-06-02T00:00:00Z",
      observed_from: "2026-06-01T00:00:00Z",
      observed_to: "2026-06-02T00:00:00Z",
      coverage_classes: ["platform_standard"],
      coverage_class_counts: { platform_standard: 500 },
      threshold_violations: [],
      metrics: {
        sample_count: 500,
        success_count: 492,
        failed_count: 8,
        timeout_count: 2,
        provider_error_count: 1,
        success_rate: "0.984000",
        average_deviation_ratio: "0.010000",
        provider_p95_latency_ms: 120,
        baseline_p95_latency_ms: 100,
        p95_latency_ratio: "1.200000",
      },
      scope_source: "global",
    },
  ],
  timeline: [],
};

const revenue = {
  provider_id: "provider-alpha",
  tenant_id: null,
  from_at: null,
  to_at: null,
  period_month: "2026-06",
  status: null,
  k_algo: null,
  currency: "CNY",
  status_counts: { pending: 1, held: 1, paid: 0, voided: 0 },
  total_entries: 2,
  currency_totals: [
    {
      currency: "CNY",
      entry_count: 2,
      gross_amount: "1000.0000",
      provider_revenue_amount: "600.0000",
      platform_revenue_amount: "400.0000",
      pending_payout_amount: "300.0000",
      held_payout_amount: "300.0000",
      paid_amount: "0.0000",
      voided_gross_amount: "0.0000",
    },
  ],
  period_summaries: [
    {
      period_month: "2026-05",
      currency: "CNY",
      entry_count: 3,
      gross_amount: "1200.0000",
      provider_revenue_amount: "720.0000",
      platform_revenue_amount: "480.0000",
      pending_payout_amount: "420.0000",
      held_payout_amount: "300.0000",
      paid_amount: "0.0000",
      voided_gross_amount: "0.0000",
    },
  ],
  entries: [
    {
      entry_id: "entry-alpha",
      hook_id: "00000000-0000-0000-0000-000000000002",
      provider_id: "provider-alpha",
      k_algo: "opt-lp",
      policy_id: "policy-alpha",
      source_service: "billing-service",
      source_event_id: "00000000-0000-0000-0000-000000000003",
      period_month: "2026-06",
      currency: "CNY",
      gross_amount: "500.0000",
      provider_share_ratio: "0.600000",
      platform_share_ratio: "0.400000",
      provider_revenue_amount: "300.0000",
      platform_revenue_amount: "200.0000",
      status: "pending",
      recognized_at: "2026-06-02T00:00:00Z",
      scope_source: "global",
    },
  ],
};

const versionUpdate = {
  id: "00000000-0000-0000-0000-000000000004",
  tenant_id: null,
  application_id: "app-alpha",
  version_update_id: "vu-alpha",
  requested_provider_id: "provider-alpha",
  current_version: "1.2.0",
  proposed_version: "1.3.0",
  change_kind: "minor",
  openapi_url: "https://example.com/openapi.json",
  openapi_sha256: "c".repeat(64),
  image_digest: `repo/provider@sha256:${"d".repeat(64)}`,
  cosign_bundle: { hidden: "should not render" },
  sbom_ref: "s3://bucket/sbom",
  release_notes_ref: "s3://bucket/release-notes",
  status: "approved",
  review_notes_ref: "s3://bucket/review",
  submitted_at: "2026-06-02T00:00:00Z",
  reviewed_at: "2026-06-03T00:00:00Z",
  record_version: 2,
  metadata: { hidden: "should not render" },
  scope_source: "global",
  created_at: "2026-06-02T00:00:00Z",
  updated_at: "2026-06-03T00:00:00Z",
};

const monthlyBatch = {
  id: "00000000-0000-0000-0000-000000000005",
  tenant_id: null,
  batch_id: "batch-alpha",
  period_month: "2026-06",
  status: "approved",
  calculated_at: "2026-07-01T00:00:00Z",
  entry_count: 2,
  provider_count: 1,
  currency_totals: [
    {
      currency: "CNY",
      entry_count: 2,
      provider_count: 1,
      gross_amount: "1000.0000",
      provider_revenue_amount: "600.0000",
      platform_revenue_amount: "400.0000",
      pending_payout_amount: "300.0000",
      held_payout_amount: "300.0000",
    },
  ],
  provider_summaries: [],
  policy_ratio_summaries: [],
  excluded_entries: [],
  source_entry_ids: ["entry-alpha", "entry-beta"],
  calculation_checksum: `${"e".repeat(54)}ffffffffff`,
  notes_ref: "s3://bucket/notes",
  approved_by_ref: "s3://bucket/approval",
  record_version: 2,
  scope_source: "global",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
};

function mockSuccess(): void {
  mocks.listProviderApplications.mockResolvedValue([application]);
  mocks.getProviderRouteShareDashboard.mockResolvedValue(routeShare);
  mocks.getProviderKpiDashboard.mockResolvedValue(kpi);
  mocks.getProviderRevenuePayoutDashboard.mockResolvedValue(revenue);
  mocks.listProviderVersionUpdates.mockResolvedValue([versionUpdate]);
  mocks.listProviderMonthlyRevenueShareBatches.mockResolvedValue([monthlyBatch]);
}

async function submitFilters(
  providerId = "provider-alpha",
  options: { tenantId?: string; applicationId?: string; periodMonth?: string } = {},
): Promise<void> {
  fireEvent.change(screen.getByLabelText("Provider ID"), { target: { value: providerId } });
  fireEvent.change(screen.getByLabelText("Tenant ID"), {
    target: { value: options.tenantId ?? "" },
  });
  fireEvent.change(screen.getByLabelText("Application ID"), {
    target: { value: options.applicationId ?? "" },
  });
  fireEvent.change(screen.getByLabelText("月份"), {
    target: { value: options.periodMonth ?? "2026-06" },
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "加载 Provider Console" }));
  });
}

describe("ProviderConsolePage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listProviderApplications.mockReset();
    mocks.getProviderRouteShareDashboard.mockReset();
    mocks.getProviderKpiDashboard.mockReset();
    mocks.getProviderRevenuePayoutDashboard.mockReset();
    mocks.listProviderVersionUpdates.mockReset();
    mocks.listProviderMonthlyRevenueShareBatches.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    render(<ProviderConsolePage />);

    expect(mocks.push).toHaveBeenCalledWith("/auth/login");
  });

  it("renders the read-only provider aggregate dashboard", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mockSuccess();

    render(<ProviderConsolePage />);
    await submitFilters();

    expect(await screen.findByText("Alpha Solver Lab")).toBeTruthy();
    expect(screen.getByText("Alpha University")).toBeTruthy();
    expect(screen.getAllByText("50%").length).toBeGreaterThan(0);
    expect(screen.getByText("0.984000")).toBeTruthy();
    expect(screen.getAllByText("600.0000 CNY").length).toBeGreaterThan(0);
    expect(screen.getByText("2026-05")).toBeTruthy();
    expect(screen.getByText("720.0000 CNY")).toBeTruthy();
    expect(screen.getByText("vu-alpha")).toBeTruthy();
    expect(screen.getByText("1.2.0 -> 1.3.0")).toBeTruthy();
    expect(screen.getByText("batch-alpha")).toBeTruthy();
    expect(screen.getByText("Tier 3 Operational Overview")).toBeTruthy();
    expect(screen.getByText("Application readiness")).toBeTruthy();
    expect(screen.getByText("Route Share rollout")).toBeTruthy();
    expect(screen.getByText("Shadow KPI quality")).toBeTruthy();
    expect(screen.getByText("Revenue/Payout projection")).toBeTruthy();
    expect(screen.getByText("Provider Console open issues")).toBeTruthy();
    expect(screen.getByText(/Application readiness: watch/)).toBeTruthy();
    expect(screen.getByText(/Revenue\/Payout projection: watch/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "打开 Routing History" }).getAttribute("href")).toBe(
      "/console/routing-history?provider_id=provider-alpha&period_month=2026-06",
    );
    expect(screen.getByText("ffffffffff")).toBeTruthy();
    expect(screen.queryByText("should not render")).toBeNull();
    expect(mocks.listProviderApplications).toHaveBeenCalledWith("jwt-test", {
      requestedProviderId: "provider-alpha",
      status: undefined,
      tenantId: undefined,
    });
    expect(mocks.getProviderRevenuePayoutDashboard).toHaveBeenCalledWith(
      "jwt-test",
      "provider-alpha",
      { periodMonth: "2026-06", tenantId: undefined },
    );
    expect(mocks.listProviderMonthlyRevenueShareBatches).toHaveBeenCalledWith(
      "jwt-test",
      { periodMonth: "2026-06", tenantId: undefined },
    );
  });

  it("shows version update empty state when no application can anchor the list", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listProviderApplications.mockResolvedValue([]);
    mocks.getProviderRouteShareDashboard.mockResolvedValue(routeShare);
    mocks.getProviderKpiDashboard.mockResolvedValue(kpi);
    mocks.getProviderRevenuePayoutDashboard.mockResolvedValue(revenue);
    mocks.listProviderMonthlyRevenueShareBatches.mockResolvedValue([monthlyBatch]);

    render(<ProviderConsolePage />);
    await submitFilters();

    expect(await screen.findByText("未找到 Provider application")).toBeTruthy();
    expect(screen.getByText("暂无版本更新")).toBeTruthy();
    expect(mocks.listProviderVersionUpdates).not.toHaveBeenCalled();
  });

  it("keeps successful sections visible when one provider read fails", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mockSuccess();
    mocks.getProviderRevenuePayoutDashboard.mockRejectedValue(
      new Error("revenue projection unavailable"),
    );

    render(<ProviderConsolePage />);
    await submitFilters();

    expect(await screen.findByText("Alpha Solver Lab")).toBeTruthy();
    expect(screen.getByText("0.984000")).toBeTruthy();
    expect(screen.getByText("收入/待结算加载失败")).toBeTruthy();
    expect(screen.getAllByText(/revenue projection unavailable/).length).toBeGreaterThan(0);
    expect(screen.getByText("batch-alpha")).toBeTruthy();
    expect(screen.getByText(/Revenue\/Payout projection: blocked\/error/)).toBeTruthy();
  });

  it("does not write provider filters or dashboard data to browser storage", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mockSuccess();
    const storageSet = vi.spyOn(Storage.prototype, "setItem");

    render(<ProviderConsolePage />);
    await submitFilters();

    await waitFor(() => expect(screen.getByText("Alpha Solver Lab")).toBeTruthy());
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/provider|tenant|application|dashboard|payout|batch/i),
      expect.any(String),
    );
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Providers" }).getAttribute("href")).toBe(
      "/console/providers",
    );
    expect(screen.getByRole("link", { name: "打开 Routing History" }).getAttribute("href")).not.toContain(
      "jwt-test",
    );
  });

  it("builds routing-history handoff from submitted filters and keeps it stable across draft edits", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mockSuccess();

    render(<ProviderConsolePage />);
    await submitFilters("provider-alpha", {
      tenantId: "tenant 1",
      applicationId: "app/alpha",
      periodMonth: "2026-06",
    });

    const link = await screen.findByRole("link", { name: "打开 Routing History" });
    expect(link.getAttribute("href")).toBe(
      "/console/routing-history?provider_id=provider-alpha&tenant_id=tenant+1&application_id=app%2Falpha&period_month=2026-06",
    );

    fireEvent.change(screen.getByLabelText("Provider ID"), { target: { value: "provider-beta" } });
    expect(screen.getByRole("link", { name: "打开 Routing History" }).getAttribute("href")).toBe(
      "/console/routing-history?provider_id=provider-alpha&tenant_id=tenant+1&application_id=app%2Falpha&period_month=2026-06",
    );
  });

  it("clears prior provider data while a new submitted context is loading", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mockSuccess();

    render(<ProviderConsolePage />);
    await submitFilters("provider-alpha");
    expect(await screen.findByText("Alpha Solver Lab")).toBeTruthy();

    let resolveApplications: (value: unknown[]) => void = () => undefined;
    mocks.listProviderApplications.mockReturnValue(
      new Promise((resolve) => {
        resolveApplications = resolve;
      }),
    );
    mocks.getProviderRouteShareDashboard.mockResolvedValue(routeShare);
    mocks.getProviderKpiDashboard.mockResolvedValue(kpi);
    mocks.getProviderRevenuePayoutDashboard.mockResolvedValue(revenue);
    mocks.listProviderMonthlyRevenueShareBatches.mockResolvedValue([monthlyBatch]);
    fireEvent.change(screen.getByLabelText("Provider ID"), { target: { value: "provider-beta" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "加载 Provider Console" }));
    });

    expect(screen.getByRole("link", { name: "打开 Routing History" }).getAttribute("href")).toBe(
      "/console/routing-history?provider_id=provider-beta&period_month=2026-06",
    );
    expect(screen.queryByText("Alpha Solver Lab")).toBeNull();

    await act(async () => {
      resolveApplications([]);
    });
  });

  it("renders empty-section operational issues without treating the whole page as failed", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listProviderApplications.mockResolvedValue([]);
    mocks.getProviderRouteShareDashboard.mockResolvedValue({
      ...routeShare,
      total_rollouts: 0,
      highest_current_stage_percent: 0,
      current_rollouts: [],
      timeline: [],
      status_counts: { draft: 0, active: 0, paused: 0, completed: 0, cancelled: 0 },
    });
    mocks.getProviderKpiDashboard.mockResolvedValue({
      ...kpi,
      total_runs: 0,
      aggregate: { ...kpi.aggregate, sample_count: 0 },
      run_metrics: [],
      timeline: [],
      run_status_counts: { draft: 0, running: 0, passed: 0, failed: 0, cancelled: 0 },
    });
    mocks.getProviderRevenuePayoutDashboard.mockResolvedValue({
      ...revenue,
      total_entries: 0,
      status_counts: { pending: 0, held: 0, paid: 0, voided: 0 },
      currency_totals: [],
      period_summaries: [],
      entries: [],
    });
    mocks.listProviderMonthlyRevenueShareBatches.mockResolvedValue([]);

    render(<ProviderConsolePage />);
    await submitFilters();

    expect(await screen.findByText(/Application readiness: empty/)).toBeTruthy();
    expect(screen.getByText(/Route Share rollout: empty/)).toBeTruthy();
    expect(screen.getByText(/Shadow KPI quality: empty/)).toBeTruthy();
    expect(screen.getByText(/Revenue\/Payout projection: empty/)).toBeTruthy();
    expect(screen.getByText(/Monthly Batches lifecycle: empty/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "打开 Routing History" })).toBeTruthy();
  });
});
