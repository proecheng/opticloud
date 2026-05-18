import type { Meta, StoryObj } from "@storybook/react";

import { CreditsBalanceBucket } from "./index";

const meta = { title: "Tier 1/CreditsBalanceBucket", component: CreditsBalanceBucket, parameters: { layout: "centered" } } satisfies Meta<typeof CreditsBalanceBucket>;
export default meta;
type Story = StoryObj<typeof meta>;

export const TypicalFreeUser: Story = {
  args: {
    buckets: [
      { name: "monthly", labelZh: "月度赠送", balance: 200 },
      { name: "signup", labelZh: "注册奖励", balance: 100 },
    ],
  },
};

export const TypicalEduUser: Story = {
  args: {
    buckets: [
      { name: "edu_monthly", labelZh: "教育版月度", balance: 2000 },
      { name: "pro_trial", labelZh: "Pro 试用 (30d)", balance: 5000, expiresHint: "30 day 内有效" },
    ],
  },
};

export const PowerUser: Story = {
  args: {
    buckets: [
      { name: "monthly", labelZh: "月度赠送", balance: 1000 },
      { name: "topup", labelZh: "加油包", balance: 12450, expiresHint: "永不过期" },
    ],
  },
};
