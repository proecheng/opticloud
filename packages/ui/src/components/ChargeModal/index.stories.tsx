import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { ChargeModal } from "./index";

const meta = {
  title: "Tier 1/ChargeModal",
  component: ChargeModal,
  parameters: { layout: "centered" },
  args: {
    onConfirm: fn(),
    onCancel: fn(),
    open: true,
    currency: "CNY",
    purpose: "Demo charge",
    referenceId: "00000000-0000-0000-0000-000000000000",
    ariaLabel: "charge.confirm",
  },
} satisfies Meta<typeof ChargeModal>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Default: ¥6 charge, ¥50 balance. */
export const Default: Story = {
  args: { amount: 6, balance: 50 },
};

/** Edge: balance equals charge amount. */
export const ExactBalance: Story = {
  args: { amount: 6, balance: 6 },
};

/** Edge: balance < charge. Confirm disabled. */
export const InsufficientBalance: Story = {
  args: { amount: 6, balance: 3 },
};

/** Loading state after Confirm click. */
export const Loading: Story = {
  args: { amount: 6, balance: 50, isLoading: true },
};

/** Server returned 422. */
export const WithError: Story = {
  args: {
    amount: 6,
    balance: 3,
    error: "Required: ¥6.00, available: ¥3.00",
  },
};

/** Story 5.A.3 — cap emphasis: title says "(cap)" + inline "≤ this amount" note. */
export const CapEmphasis_5A3: Story = {
  args: {
    amount: 6,
    balance: 50,
    purpose: "Solve LP (max 60s × ¥0.10/s = ¥6 cap)",
  },
};
