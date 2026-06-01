import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { BudgetAlertCard, type BudgetAlertBudget } from "./index";

const budget: BudgetAlertBudget = {
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

describe("BudgetAlertCard a11y", () => {
  it("default state has no violations", async () => {
    const { container } = render(
      <BudgetAlertCard
        budget={budget}
        amountValue="100.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("paused error state has no violations", async () => {
    const { container } = render(
      <BudgetAlertCard
        budget={{ ...budget, status: "paused", paused: true, paused_at: "2026-06-03T00:00:00Z" }}
        amountValue="100.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
        error="预算已触发暂停。"
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("empty loading state has no violations", async () => {
    const { container } = render(
      <BudgetAlertCard
        budget={null}
        amountValue=""
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
        isLoading
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
