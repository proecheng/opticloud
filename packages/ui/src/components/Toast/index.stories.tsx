import type { Meta, StoryObj } from "@storybook/react";

import { Toast } from "./index";

const meta = { title: "Tier 1/Toast", component: Toast, parameters: { layout: "centered" } } satisfies Meta<typeof Toast>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Success: Story = { args: { variant: "success", message: "API Key 已生成", ariaLabel: "toast.api_key_created", durationMs: 999999 } };
export const Warning: Story = { args: { variant: "warning", message: "余额不足，预估 605 Credits", ariaLabel: "toast.balance_low", durationMs: 999999 } };
export const Danger: Story = { args: { variant: "danger", message: "求解失败（infeasible）", ariaLabel: "toast.solve_failed", durationMs: 999999 } };
