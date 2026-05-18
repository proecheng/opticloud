import type { Meta, StoryObj } from "@storybook/react";

import { EmptyState } from "./index";

const meta = { title: "Tier 1/EmptyState", component: EmptyState, parameters: { layout: "centered" } } satisfies Meta<typeof EmptyState>;
export default meta;
type Story = StoryObj<typeof meta>;

export const NoTasksYet: Story = {
  args: {
    ariaLabel: "empty.no_tasks",
    icon: "📋",
    title: "暂无任务",
    description: "你的优化 / 预测请求会显示在这里。复制 Hello World cURL 跑通第一个 LP？",
    action: (
      <a
        href="/docs/quickstart"
        className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary-600"
      >
        查看 Quickstart
      </a>
    ),
  },
};

export const NoApiKeys: Story = {
  args: { ariaLabel: "empty.no_keys", icon: "🔑", title: "暂无 API Key", description: "点击 + 新建 API Key 开始" },
};
