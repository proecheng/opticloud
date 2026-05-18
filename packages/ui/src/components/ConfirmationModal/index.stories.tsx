import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { ConfirmationModal } from "./index";

const meta = {
  title: "Tier 1/ConfirmationModal",
  component: ConfirmationModal,
  parameters: { layout: "centered" },
  args: { onClose: fn(), onConfirm: fn(), open: true, ariaLabel: "modal.demo" },
} satisfies Meta<typeof ConfirmationModal>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Story 1.1b J1 Vertical Slice — 注册成功 modal. */
export const SignupSuccess: Story = {
  args: {
    variant: "signup_success",
    ariaLabel: "modal.signup.success",
    title: "🎉 注册成功",
    description: "你的 API Key 已生成。请立即复制（不会再显示）。",
    body: (
      <pre className="overflow-x-auto rounded bg-muted p-3 font-mono text-xs">
        {`curl -X POST https://api.opticloud.cn/v1/optimizations \\
  -H "Authorization: Bearer sk-xxx_***" \\
  -d '{"task_type":"lp","minimize":{"c":[1,1]}}'`}
      </pre>
    ),
    confirmLabel: "复制 cURL + 导入 Postman",
  },
};

/** FR B2 + B6 — 余额警示. */
export const BalanceWarning: Story = {
  args: {
    variant: "balance_warn",
    ariaLabel: "modal.balance.warn",
    title: "⚠️ 余额不足",
    description: "当前 50 Credits，本次预估消耗 605 Credits。继续将自动暂停 budget。",
    confirmLabel: "去加油",
    cancelLabel: "取消",
  },
};

/** FR P5 调用警示. */
export const P5Alert: Story = {
  args: {
    variant: "p5_alert",
    ariaLabel: "modal.p5.alert",
    title: "🟡 T5/T6/P5 调用确认",
    description: "本次为 T5 级别求解（≥500 客户 VRPTW），预计 60s + 605 Credits。",
    confirmLabel: "我知道，继续",
  },
};

/** FR A6 destructive — 账户删除. */
export const Destructive: Story = {
  args: {
    variant: "destructive",
    ariaLabel: "modal.account.delete",
    title: "🔴 删除账户（PIPL）",
    description: "7 day 内 hard-delete 全部 PII 数据。此操作不可撤销。",
    confirmLabel: "确认删除",
  },
};
