import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

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
      id: "event-1",
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

const meta = {
  title: "Tier 2/BudgetAlertCard",
  component: BudgetAlertCard,
  parameters: { layout: "padded" },
  args: {
    budget,
    amountValue: "100.00",
    onAmountChange: fn(),
    onSave: fn(),
    onDisable: fn(),
  },
} satisfies Meta<typeof BudgetAlertCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const LoadingEmpty: Story = {
  args: {
    budget: null,
    amountValue: "",
    isLoading: true,
  },
};

export const PausedWithError: Story = {
  args: {
    budget: {
      ...budget,
      status: "paused",
      paused: true,
      paused_at: "2026-06-03T00:00:00Z",
      monthly_budget_amount: "80.00",
      actual_spend: "100.00",
      percent_used: "1.2500",
    },
    amountValue: "80.00",
    error: "预算已触发暂停，请提高或停用预算后继续。",
  },
};

export const SavedMessage: Story = {
  args: {
    message: "预算已更新。",
  },
};

export const LongContent: Story = {
  args: {
    budget: {
      ...budget,
      monthly_budget_amount: "9999999999.99",
      actual_spend: "123456789.99",
      percent_used: "12.3456",
      recent_events: [
        {
          ...budget.recent_events[0]!,
          id: "very-long-budget-event-id-1234567890abcdef1234567890abcdef",
          channels: ["email", "webhook", "in_app"],
        },
      ],
    },
    amountValue: "9999999999.99",
  },
};
