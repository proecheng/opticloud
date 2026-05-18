import type { Meta, StoryObj } from "@storybook/react";

import { SparklineKPI } from "./index";

const meta = { title: "Tier 1/SparklineKPI", component: SparklineKPI, parameters: { layout: "centered" } } satisfies Meta<typeof SparklineKPI>;
export default meta;
type Story = StoryObj<typeof meta>;

export const SevenDayCredits: Story = {
  args: { label: "7d Credits 消耗", ariaLabel: "kpi.credits_7d", values: [120, 145, 130, 168, 200, 175, 220], unit: "C" },
};
export const ApiLatency: Story = {
  args: { label: "API P95 (ms)", ariaLabel: "kpi.api_latency_p95", values: [180, 195, 175, 210, 165, 180, 188], unit: "ms" },
};
