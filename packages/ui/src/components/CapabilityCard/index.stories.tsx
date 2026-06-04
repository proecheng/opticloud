import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { CapabilityCard, type CapabilityCardCapability } from "./index";

const capability: CapabilityCardCapability = {
  benchmark_id: "or-lib-afiro-lp",
  suite: "or-lib",
  domain: "linear-programming",
  task_type: "lp",
  title_zh: "OR-Library AFIRO 线性规划模板",
  title_en: "OR-Library AFIRO linear programming template",
  source_name: "OR-Library",
  source_url: "https://example.com/or-lib",
  license_note_zh: "仅引用公开来源；模板不是完整数据集镜像。",
  import_kind: "optimization_request",
  target_endpoint: "/v1/optimizations",
  discount: {
    kind: "benchmark_library",
    label_zh: "50% Credits 折扣",
    discount_multiplier: 0.5,
    billing_supported: true,
  },
  dataset_ref: "benchmark://or-lib/afiro",
  sample_payload: { task_type: "lp" },
};

const meta = {
  title: "Tier 2/CapabilityCard",
  component: CapabilityCard,
  parameters: { layout: "padded" },
  args: {
    capability,
    onImport: fn(),
  },
} satisfies Meta<typeof CapabilityCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Optimization: Story = {};

export const PredictionBillingNotSupported: Story = {
  args: {
    capability: {
      ...capability,
      benchmark_id: "m5-walmart-forecast",
      suite: "m5",
      domain: "forecast",
      task_type: "forecast",
      title_zh: "M5 零售销量预测模板",
      title_en: "M5 retail sales forecast template",
      import_kind: "prediction_request",
      target_endpoint: "/v1/predictions",
      discount: { ...capability.discount, billing_supported: false },
    },
  },
};

export const Importing: Story = {
  args: {
    isImporting: true,
  },
};

export const UnsafeSourceUrl: Story = {
  args: {
    capability: {
      ...capability,
      source_url: "javascript:alert(1)",
    },
  },
};

export const MissingSourceUrl: Story = {
  args: {
    capability: {
      ...capability,
      source_url: null,
    },
  },
};

export const LongContent: Story = {
  args: {
    capability: {
      ...capability,
      benchmark_id: "or/lib afiro with spaces and punctuation !@#$%",
      title_zh:
        "非常长的经典算例库能力标题用于验证移动端和桌面端换行不会产生水平滚动或遮挡",
      title_en:
        "Very long benchmark capability title for validating responsive wrapping without overflow",
      source_name: "Very Long Public Benchmark Source Name With Many Words",
      target_endpoint: "/v1/optimizations/with/a/very/long/endpoint/name",
      dataset_ref:
        "benchmark://or-lib/very/long/reference/value/with/many/segments/and-identifiers",
      license_note_zh:
        "这是一段很长的许可说明，用于验证卡片在中文长文本、英文长词和混合标点下仍然保持可读布局。",
    },
  },
};
