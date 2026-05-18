import type { Meta, StoryObj } from "@storybook/react";

import { StatusCard } from "./index";

const meta = {
  title: "Tier 1/StatusCard",
  component: StatusCard,
  parameters: { layout: "centered" },
} satisfies Meta<typeof StatusCard>;
export default meta;
type Story = StoryObj<typeof meta>;

export const OK: Story = { args: { variant: "ok", title: "All systems operational", ariaLabel: "status.ok" } };
export const Warning: Story = { args: { variant: "warning", title: "Elevated latency", description: "API P95 = 320ms (target 200ms)", ariaLabel: "status.warning" } };
export const Error: Story = { args: { variant: "error", title: "Outage in solver-orchestrator", ariaLabel: "status.error" } };
