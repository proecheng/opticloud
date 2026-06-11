// @vitest-environment happy-dom

import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

const mocks = vi.hoisted(() => ({
  getOptimization: vi.fn(),
  searchParams: new URLSearchParams(),
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

vi.mock("next/navigation", () => ({
  useSearchParams: () => mocks.searchParams,
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
  getOptimization: mocks.getOptimization,
}));

import RoutingHistoryPage from "./page";

const routingHistory = {
  primary_route: {
    task_type: "lp",
    requested_solver: null,
    selected_solver: "highs",
    provider_id: "highs",
    provider_kind: "open_source",
    provider_url: "https://highs.dev/",
    routing_reason: "default_solver",
  },
  executed_route: {
    task_type: "lp",
    requested_solver: "highs",
    selected_solver: "highs",
    provider_id: "highs",
    provider_kind: "open_source",
    provider_url: "https://highs.dev/",
    routing_reason: "explicit_solver",
  },
  summary: {
    attempt_count: 2,
    fallback_used: true,
    terminal_status: "optimal",
    terminal_attempt: 2,
    exhausted: false,
    solve_seconds: 0.375,
  },
  attempts: [
    {
      attempt: 1,
      role: "primary",
      requested_solver: null,
      selected_solver: "highs",
      provider_id: "highs",
      provider_kind: "open_source",
      provider_url: "https://highs.dev/",
      routing_reason: "default_solver",
      status: "timeout",
      retryable: true,
      solve_seconds: 0.125,
    },
    {
      attempt: 2,
      role: "fallback",
      requested_solver: "highs",
      selected_solver: "highs",
      provider_id: "highs",
      provider_kind: "open_source",
      provider_url: "https://highs.dev/",
      routing_reason: "explicit_solver",
      status: "optimal",
      retryable: false,
      solve_seconds: 0.25,
    },
  ],
};

function renderPage(): void {
  renderWithIntl(<RoutingHistoryPage />);
}

describe("RoutingHistoryPage", () => {
  beforeEach(() => {
    mocks.getOptimization.mockReset();
    mocks.searchParams = new URLSearchParams();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders routing timeline from a completed optimization without storage writes", async () => {
    const localSet = vi.spyOn(Storage.prototype, "setItem");
    mocks.getOptimization.mockResolvedValue({
      optimization_id: "opt-1",
      status: "completed",
      model_version: {
        provider_id: "highs",
        kind: "open_source",
        version: "1.7.0",
        provider_url: "https://highs.dev/",
      },
      solution: { x: [0, 10] },
      objective: 10,
      solve_seconds: 0.375,
      created_at: "2026-06-04T01:00:00Z",
      completed_at: "2026-06-04T01:00:01Z",
      citation: null,
      ip_attribution: null,
      routing_history: routingHistory,
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.change(screen.getByLabelText("Optimization ID"), { target: { value: "opt-1" } });
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    expect(mocks.getOptimization).toHaveBeenCalledWith("sk-test", "opt-1");
    expect(await screen.findByText("fallback")).toBeTruthy();
    expect(screen.getByText("terminal=optimal")).toBeTruthy();
    expect(screen.getByText("attempts=2")).toBeTruthy();
    expect(screen.getAllByRole("cell", { name: "terminal" })).toHaveLength(1);
    expect(screen.queryByText("sk-test")).toBeNull();
    expect(localSet).not.toHaveBeenCalled();
  });

  it("validates missing API key and optimization id", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    expect(await screen.findByText("请输入 API key。")).toBeTruthy();
    expect(mocks.getOptimization).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    expect(await screen.findByText("请输入 Optimization ID。")).toBeTruthy();
    expect(mocks.getOptimization).not.toHaveBeenCalled();
  });

  it("renders empty state when routing history is absent", async () => {
    mocks.getOptimization.mockResolvedValue({
      optimization_id: "legacy",
      status: "completed",
      model_version: null,
      solution: null,
      objective: null,
      solve_seconds: 0,
      created_at: "2026-06-04T01:00:00Z",
      completed_at: "2026-06-04T01:00:01Z",
      citation: null,
      ip_attribution: null,
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.change(screen.getByLabelText("Optimization ID"), { target: { value: "legacy" } });
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    expect(await screen.findByText("暂无 routing history")).toBeTruthy();
  });

  it("renders non-completed status without assuming completed-only fields", async () => {
    mocks.getOptimization.mockResolvedValue({
      optimization_id: "queued",
      status: "queued",
      model_version: {
        provider_id: "highs",
        kind: "open_source",
        version: "1.7.0",
        provider_url: "https://highs.dev/",
      },
      created_at: "2026-06-04T01:00:00Z",
      completed_at: null,
      progress_pct: 0,
      eta_seconds: null,
      routing_history: {
        ...routingHistory,
        executed_route: null,
        attempts: [],
        summary: {
          attempt_count: 0,
          fallback_used: false,
          terminal_status: null,
          terminal_attempt: null,
          exhausted: false,
          solve_seconds: 0,
        },
      },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.change(screen.getByLabelText("Optimization ID"), { target: { value: "queued" } });
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    expect(await screen.findByText("status=queued")).toBeTruthy();
    expect(screen.getByText("attempts=0")).toBeTruthy();
  });

  it("renders safe backend errors", async () => {
    mocks.getOptimization.mockRejectedValue({
      status: 404,
      title: "Not Found",
      detail: "optimization not found",
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.change(screen.getByLabelText("Optimization ID"), { target: { value: "missing" } });
    fireEvent.click(screen.getByRole("button", { name: "加载 routing history" }));

    await waitFor(() => {
      expect(screen.getByText("Not Found: optimization not found")).toBeTruthy();
    });
  });

  it("renders provider handoff context without auto-querying or filling credentials", async () => {
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    mocks.searchParams = new URLSearchParams({
      provider_id: "provider-alpha",
      tenant_id: "tenant 1",
      application_id: "app/alpha",
      period_month: "2026-06",
    });

    renderPage();

    expect(screen.getByText("Provider Console context")).toBeTruthy();
    expect(screen.getByText("provider-alpha")).toBeTruthy();
    expect(screen.getByText("tenant 1")).toBeTruthy();
    expect(screen.getByText("app/alpha")).toBeTruthy();
    expect(screen.getByText("2026-06")).toBeTruthy();
    expect(screen.getByLabelText("API key")).toHaveProperty("value", "");
    expect(screen.getByLabelText("Optimization ID")).toHaveProperty("value", "");
    expect(mocks.getOptimization).not.toHaveBeenCalled();
    expect(storageSet).not.toHaveBeenCalled();
  });
});
