import type { Meta, StoryObj } from "@storybook/react";

import { ConfidenceLabel } from "./index";

const meta = {
  title: "Tier 1/ConfidenceLabel",
  component: ConfidenceLabel,
  parameters: { layout: "centered" },
} satisfies Meta<typeof ConfidenceLabel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const HighConfidence: Story = {
  args: { score: 0.92, reasoning: "Critic 验证通过：约束 + 目标解一致" },
};
export const MidConfidence: Story = {
  args: { score: 0.72, reasoning: "部分变量边界可能漂移；建议复核" },
};
export const LowConfidence: Story = {
  args: { score: 0.45, reasoning: "Critic 标记 escalate（FR N9 < 0.6 阈值）" },
};
export const Compact: Story = { args: { score: 0.88, compact: true } };
