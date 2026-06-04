import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

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

describe("CapabilityCard a11y", () => {
  it("default optimization state has no violations", async () => {
    const { container } = render(<CapabilityCard capability={capability} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("prediction billing-not-supported state has no violations", async () => {
    const { container } = render(
      <CapabilityCard
        capability={{
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
        }}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("importing state has no violations", async () => {
    const { container } = render(
      <CapabilityCard capability={capability} onImport={vi.fn()} isImporting />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("long content state has no violations", async () => {
    const { container } = render(
      <CapabilityCard
        capability={{
          ...capability,
          benchmark_id: "or/lib afiro with spaces and punctuation !@#$%",
          title_zh:
            "非常长的经典算例库能力标题用于验证移动端和桌面端换行不会产生水平滚动或遮挡",
          title_en:
            "Very long benchmark capability title for validating responsive wrapping without overflow",
          source_name: "Very Long Public Benchmark Source Name With Many Words",
          dataset_ref:
            "benchmark://or-lib/very/long/reference/value/with/many/segments/and-identifiers",
          license_note_zh:
            "这是一段很长的许可说明，用于验证卡片在中文长文本、英文长词和混合标点下仍然保持可读布局。",
        }}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
