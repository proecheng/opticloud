import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { AuditLogTable, type AuditLogTableItem } from "./index";

const item: AuditLogTableItem = {
  id: "11111111-1111-4111-8111-111111111111",
  actor: "user",
  action: "api_key.created",
  resource_type: "api_key",
  resource_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  metadata: { label: "生产环境 Key", authorization: "Bearer hidden" },
  ip_address: "203.0.113.10",
  user_agent: "Mozilla/5.0",
  created_at: "2026-06-02T08:30:00Z",
};

describe("AuditLogTable a11y", () => {
  it("default table state has no violations", async () => {
    const { container } = render(
      <AuditLogTable
        items={[item]}
        nextCursor="cursor-1"
        onLoadNext={vi.fn()}
        onApplyTimeRange={vi.fn()}
      />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("loading state has no violations", async () => {
    const { container } = render(<AuditLogTable items={[]} isLoading />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("error and empty states have no violations", async () => {
    const errorRender = render(<AuditLogTable items={[]} error="请求失败" />);
    expect(await axe(errorRender.container)).toHaveNoViolations();
    errorRender.unmount();

    const emptyRender = render(<AuditLogTable items={[]} />);
    expect(await axe(emptyRender.container)).toHaveNoViolations();
  });
});
