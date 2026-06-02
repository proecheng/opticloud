import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuditLogTable, type AuditLogTableItem } from "./index";

const rows: AuditLogTableItem[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    actor: "user",
    action: "api_key.created",
    resource_type: "api_key",
    resource_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    metadata: {
      label: "生产环境 Key",
      scope: ["optimization:write"],
      authorization: "Bearer should-not-render",
      nested: {
        api_key: "sk-secret-should-not-render",
        webhook_url_configured: true,
      },
    },
    ip_address: "203.0.113.10",
    user_agent: "Mozilla/5.0 Very Long Agent ".repeat(5),
    created_at: "2026-06-02T08:30:00Z",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    actor: "system",
    action: "data_export.requested",
    resource_type: "data_export",
    resource_id: null,
    metadata: {
      format: "csv",
      package_bytes: 2048,
      token_like_value: "eyJhbGciOiJIUzI1NiJ9.aaa.bbb",
    },
    ip_address: null,
    user_agent: null,
    created_at: "not-a-date",
  },
];

describe("AuditLogTable", () => {
  it("renders semantic audit rows and masks sensitive metadata", () => {
    render(<AuditLogTable items={rows} />);

    const table = screen.getByRole("table", { name: "审计日志表格" });
    expect(within(table).getByRole("columnheader", { name: "时间" })).toBeInTheDocument();
    expect(screen.getByText("api_key.created")).toBeInTheDocument();
    expect(screen.getByText("data_export.requested")).toBeInTheDocument();
    expect(screen.getByText("生产环境 Key")).toBeInTheDocument();
    expect(screen.getByText(/optimization:write/)).toBeInTheDocument();
    expect(screen.getByText(/webhook_url_configured/)).toBeInTheDocument();
    expect(screen.getAllByText("[REDACTED]").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/should-not-render|sk-secret|eyJhbGci/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date|NaN|null|undefined/i)).not.toBeInTheDocument();
  });

  it("filters the current page by action, actor, resource, and metadata text", () => {
    render(<AuditLogTable items={rows} />);

    fireEvent.change(screen.getByLabelText("搜索当前页"), {
      target: { value: "csv" },
    });

    expect(screen.queryByText("api_key.created")).not.toBeInTheDocument();
    expect(screen.getByText("data_export.requested")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索当前页"), {
      target: { value: "api_key" },
    });

    expect(screen.getByText("api_key.created")).toBeInTheDocument();
    expect(screen.queryByText("data_export.requested")).not.toBeInTheDocument();
  });

  it("submits server time filters and exposes pagination callbacks", () => {
    const onApplyTimeRange = vi.fn();
    const onLoadNext = vi.fn();
    render(
      <AuditLogTable
        items={rows}
        nextCursor="cursor-1"
        from="2026-06-01T00:00:00Z"
        to="2026-06-02T00:00:00Z"
        onApplyTimeRange={onApplyTimeRange}
        onLoadNext={onLoadNext}
      />,
    );

    fireEvent.change(screen.getByLabelText("开始时间"), {
      target: { value: "2026-06-01T09:00" },
    });
    fireEvent.change(screen.getByLabelText("结束时间"), {
      target: { value: "2026-06-02T18:30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用时间范围" }));

    expect(onApplyTimeRange).toHaveBeenCalledTimes(1);
    const payload = onApplyTimeRange.mock.calls[0]?.[0] as { from?: string; to?: string };
    expect(payload.from).toMatch(/2026-06-01T/);
    expect(payload.from).toMatch(/Z$/);
    expect(payload.to).toMatch(/2026-06-02T/);
    expect(payload.to).toMatch(/Z$/);

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(onLoadNext).toHaveBeenCalledWith("cursor-1");
  });

  it("renders loading, error, empty, and filtered-empty states", () => {
    const { rerender } = render(<AuditLogTable items={[]} isLoading />);
    expect(screen.getByRole("status", { name: "审计日志加载状态" })).toHaveTextContent("加载中");

    rerender(<AuditLogTable items={[]} error="Unauthorized: 登录状态已失效" />);
    expect(screen.getByRole("status", { name: "审计日志错误" })).toHaveTextContent("登录状态已失效");

    rerender(<AuditLogTable items={[]} />);
    expect(screen.getByText("暂无审计日志")).toBeInTheDocument();

    rerender(<AuditLogTable items={rows} />);
    fireEvent.change(screen.getByLabelText("搜索当前页"), {
      target: { value: "no-match-value" },
    });
    expect(screen.getByText("当前筛选无结果")).toBeInTheDocument();
  });

  it("disables next page when cursor is absent", () => {
    render(<AuditLogTable items={rows} />);

    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  });
});
