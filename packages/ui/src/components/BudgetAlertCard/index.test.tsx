import { fireEvent, render, screen } from "@testing-library/react";
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
  recent_events: [
    {
      id: "event-with-sensitive-looking-id-authorization-token",
      event_type: "billing.budget.alerted",
      period_start: "2026-06-01T00:00:00Z",
      period_end: "2026-07-01T00:00:00Z",
      occurred_at: "2026-06-03T00:00:00Z",
      budget_amount: "100.00",
      actual_spend: "80.00",
      percent_used: "0.8000",
      channels: ["email", "in_app"],
    },
  ],
};

describe("BudgetAlertCard", () => {
  it("renders budget status and events without raw event ids", () => {
    render(
      <BudgetAlertCard
        budget={budget}
        amountValue="100.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
      />,
    );

    expect(screen.getByTestId("budget-alert-card")).toBeInTheDocument();
    expect(screen.getByTestId("budget-status")).toHaveTextContent("启用中");
    expect(screen.getByText("¥100.00")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
    expect(screen.getByText(/已提醒/)).toBeInTheDocument();
    expect(screen.queryByText(/authorization-token|event-with-sensitive/i)).not.toBeInTheDocument();
  });

  it("wires controlled input and parent callbacks", () => {
    const onAmountChange = vi.fn();
    const onSave = vi.fn();
    const onDisable = vi.fn();
    render(
      <BudgetAlertCard
        budget={budget}
        amountValue="120.00"
        onAmountChange={onAmountChange}
        onSave={onSave}
        onDisable={onDisable}
      />,
    );

    fireEvent.change(screen.getByLabelText("预算金额"), { target: { value: "130.00" } });
    fireEvent.click(screen.getByTestId("budget-save"));
    fireEvent.click(screen.getByTestId("budget-disable"));

    expect(onAmountChange).toHaveBeenCalledWith("130.00");
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onDisable).toHaveBeenCalledTimes(1);
  });

  it("keeps first-use empty state usable and disables unavailable actions", () => {
    render(
      <BudgetAlertCard
        budget={null}
        amountValue=""
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
      />,
    );

    expect(screen.getByTestId("budget-status")).toHaveTextContent("未设置");
    expect(screen.getByTestId("budget-save")).toBeDisabled();
    expect(screen.getByTestId("budget-disable")).toBeDisabled();
    expect(screen.getByLabelText("预算金额")).toBeEnabled();
  });

  it("renders parent-owned loading, success, error, and percent boundaries", () => {
    const { rerender } = render(
      <BudgetAlertCard
        budget={{ ...budget, percent_used: "Infinity" }}
        amountValue="100.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
        isLoading
      />,
    );

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByTestId("budget-card-message")).toHaveTextContent("预算加载中");

    rerender(
      <BudgetAlertCard
        budget={{ ...budget, status: "paused", percent_used: "1.2345" }}
        amountValue="90.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
        message="预算已更新。"
        error="should not hide success"
      />,
    );

    expect(screen.getByText("123%")).toBeInTheDocument();
    expect(screen.getByTestId("budget-card-message")).toHaveTextContent("预算已更新。");
    expect(screen.queryByText(/should not hide success/)).not.toBeInTheDocument();
  });

  it("uses warning semantics after alert threshold but before pause", () => {
    render(
      <BudgetAlertCard
        budget={{ ...budget, alert_threshold_reached: true, percent_used: "0.8000" }}
        amountValue="100.00"
        onAmountChange={vi.fn()}
        onSave={vi.fn()}
        onDisable={vi.fn()}
      />,
    );

    expect(screen.getByTestId("budget-alert-card")).toHaveAttribute(
      "data-budget-status",
      "warning",
    );
    expect(screen.getByTestId("budget-status")).toHaveTextContent("接近上限");
  });
});
