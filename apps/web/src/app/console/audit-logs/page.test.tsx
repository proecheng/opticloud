// @vitest-environment happy-dom

import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listMyAuditLogs: vi.fn(),
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
  listMyAuditLogs: mocks.listMyAuditLogs,
}));

import AuditLogsPage from "./page";

const firstPage = {
  items: [
    {
      id: "11111111-1111-4111-8111-111111111111",
      actor: "user",
      action: "api_key.created",
      resource_type: "api_key",
      resource_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      metadata: {
        label: "生产环境 Key",
        authorization: "Bearer should-not-render",
      },
      ip_address: "203.0.113.10",
      user_agent: "Mozilla/5.0",
      created_at: "2026-06-02T08:30:00Z",
    },
  ],
  next_cursor: "cursor-2",
  limit: 50,
  from: "2026-06-01T00:00:00Z",
  to: "2026-06-02T00:00:00Z",
};

const secondPage = {
  ...firstPage,
  items: [
    {
      ...firstPage.items[0],
      id: "22222222-2222-4222-8222-222222222222",
      action: "data_export.requested",
      resource_type: "data_export",
      resource_id: null,
      metadata: { format: "csv" },
      created_at: "2026-06-01T08:30:00Z",
    },
  ],
  next_cursor: null,
};

describe("AuditLogsPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listMyAuditLogs.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    renderWithIntl(<AuditLogsPage />);

    expect(mocks.push).toHaveBeenCalledWith("/auth/login");
    expect(mocks.listMyAuditLogs).not.toHaveBeenCalled();
  });

  it("loads and renders the first audit log page with JWT auth", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listMyAuditLogs.mockResolvedValue(firstPage);

    renderWithIntl(<AuditLogsPage />);

    expect(await screen.findByText("api_key.created")).toBeTruthy();
    expect(screen.getByText("生产环境 Key")).toBeTruthy();
    expect(screen.queryByText(/should-not-render/i)).toBeNull();
    expect(mocks.listMyAuditLogs).toHaveBeenCalledWith("jwt-test", { limit: 50 });
  });

  it("applies a server time range as a fresh first-page request", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listMyAuditLogs.mockResolvedValue(firstPage);

    renderWithIntl(<AuditLogsPage />);
    await screen.findByText("api_key.created");

    fireEvent.change(screen.getByLabelText("开始时间"), {
      target: { value: "2026-06-01T09:00" },
    });
    fireEvent.change(screen.getByLabelText("结束时间"), {
      target: { value: "2026-06-02T18:30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用时间范围" }));

    await waitFor(() => {
      expect(mocks.listMyAuditLogs).toHaveBeenLastCalledWith(
        "jwt-test",
        expect.objectContaining({
          limit: 50,
          cursor: undefined,
        }),
      );
    });
    const filters = mocks.listMyAuditLogs.mock.calls.at(-1)?.[1] as {
      from?: string;
      to?: string;
    };
    expect(filters.from).toMatch(/Z$/);
    expect(filters.to).toMatch(/Z$/);
  });

  it("ignores stale responses when a newer time-filter request finishes first", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    let resolveInitial: (value: typeof firstPage) => void = () => undefined;
    const initialPromise = new Promise<typeof firstPage>((resolve) => {
      resolveInitial = resolve;
    });
    mocks.listMyAuditLogs
      .mockReturnValueOnce(initialPromise)
      .mockResolvedValueOnce(secondPage);

    renderWithIntl(<AuditLogsPage />);

    fireEvent.change(screen.getByLabelText("开始时间"), {
      target: { value: "2026-06-01T09:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用时间范围" }));

    expect(await screen.findByText("data_export.requested")).toBeTruthy();

    await act(async () => {
      resolveInitial(firstPage);
      await initialPromise;
    });

    expect(screen.getByText("data_export.requested")).toBeTruthy();
    expect(screen.queryByText("api_key.created")).toBeNull();
  });

  it("loads the next cursor page without writing sensitive storage", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listMyAuditLogs.mockResolvedValueOnce(firstPage).mockResolvedValueOnce(secondPage);
    const storageSet = vi.spyOn(Storage.prototype, "setItem");

    renderWithIntl(<AuditLogsPage />);
    await screen.findByText("api_key.created");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    });

    await screen.findByText("data_export.requested");
    expect(mocks.listMyAuditLogs).toHaveBeenLastCalledWith("jwt-test", {
      limit: 50,
      from: firstPage.from,
      to: firstPage.to,
      cursor: "cursor-2",
    });
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/audit|cursor|metadata|token|api_key/i),
      expect.any(String),
    );
  });

  it("keeps the table shell visible on API errors", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listMyAuditLogs.mockRejectedValue(
      new Error("audit service unavailable"),
    );

    renderWithIntl(<AuditLogsPage />);

    expect(await screen.findByText(/audit service unavailable/)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "审计日志" })).toBeTruthy();
  });

  it("keeps audit logs discoverable from console navigation", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listMyAuditLogs.mockResolvedValue({ ...firstPage, items: [], next_cursor: null });

    renderWithIntl(<AuditLogsPage />);

    await screen.findByText("暂无审计日志");
    const nav = screen.getByRole("navigation", { name: "Console governance navigation" });
    expect(
      within(nav).getByRole("link", { name: "审计日志", current: "page" }).getAttribute("href"),
    ).toBe("/console/audit-logs");
    expect(within(nav).getByRole("link", { name: "账单" }).getAttribute("href")).toBe(
      "/console/billing/invoices",
    );
  });
});
