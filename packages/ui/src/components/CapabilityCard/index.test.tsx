import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CapabilityCard, type CapabilityCardCapability } from "./index";

const optimizationCapability: CapabilityCardCapability = {
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
  sample_payload: {
    task_type: "lp",
    secret_internal_payload_marker: "must-not-render",
  },
};

describe("CapabilityCard", () => {
  it("renders benchmark capability metadata without raw sample payload", () => {
    render(<CapabilityCard capability={optimizationCapability} />);

    expect(screen.getByTestId("capability-card")).toBeInTheDocument();
    expect(screen.getByText("OR-Library AFIRO 线性规划模板")).toBeInTheDocument();
    expect(screen.getByText("OR-Lib")).toBeInTheDocument();
    expect(screen.getByText("linear-programming")).toBeInTheDocument();
    expect(screen.getByText("or-lib-afiro-lp")).toBeInTheDocument();
    expect(screen.getByText("benchmark://or-lib/afiro")).toBeInTheDocument();
    expect(screen.getByText("/v1/optimizations")).toBeInTheDocument();
    expect(screen.getByTestId("capability-discount")).toHaveTextContent(
      "50% Credits 折扣",
    );
    expect(screen.queryByText("secret_internal_payload_marker")).not.toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("fires import callback with benchmark id", () => {
    const onImport = vi.fn();
    render(<CapabilityCard capability={optimizationCapability} onImport={onImport} />);

    fireEvent.click(screen.getByTestId("capability-import"));

    expect(onImport).toHaveBeenCalledWith("or-lib-afiro-lp");
  });

  it("disables only the importing card state", () => {
    const onImport = vi.fn();
    const { rerender } = render(
      <CapabilityCard capability={optimizationCapability} onImport={onImport} />,
    );

    expect(screen.getByTestId("capability-import")).toBeEnabled();

    rerender(
      <CapabilityCard
        capability={optimizationCapability}
        onImport={onImport}
        isImporting
      />,
    );

    expect(screen.getByTestId("capability-import")).toBeDisabled();
    expect(screen.getByTestId("capability-import")).toHaveTextContent("生成中");
  });

  it("distinguishes prediction templates from billing-supported optimization entries", () => {
    render(
      <CapabilityCard
        capability={{
          ...optimizationCapability,
          benchmark_id: "m5-walmart-forecast",
          suite: "m5",
          domain: "forecast",
          task_type: "forecast",
          title_zh: "M5 零售销量预测模板",
          title_en: "M5 retail sales forecast template",
          import_kind: "prediction_request",
          target_endpoint: "/v1/predictions",
          discount: { ...optimizationCapability.discount, billing_supported: false },
        }}
      />,
    );

    expect(screen.getByTestId("capability-card")).toHaveAttribute(
      "data-billing-supported",
      "false",
    );
    expect(screen.getByTestId("capability-billing-warning")).toHaveTextContent(
      "预测计费折扣未在当前能力中落地",
    );
  });

  it("renders missing, unsafe or malformed source URLs as text instead of anchors", () => {
    const { rerender } = render(
      <CapabilityCard
        capability={{ ...optimizationCapability, source_url: null }}
      />,
    );

    expect(screen.queryByRole("link", { name: /OR-Library/ })).not.toBeInTheDocument();
    expect(screen.getByText("OR-Library")).toBeInTheDocument();

    rerender(
      <CapabilityCard
        capability={{ ...optimizationCapability, source_url: "javascript:alert(1)" }}
      />,
    );

    expect(screen.queryByRole("link", { name: /OR-Library/ })).not.toBeInTheDocument();
    expect(screen.getByText("OR-Library")).toBeInTheDocument();

    rerender(
      <CapabilityCard capability={{ ...optimizationCapability, source_url: "not a url" }} />,
    );

    expect(screen.queryByRole("link", { name: /OR-Library/ })).not.toBeInTheDocument();
    expect(screen.getByText("OR-Library")).toBeInTheDocument();

    rerender(
      <CapabilityCard
        capability={{ ...optimizationCapability, source_url: "https://example.com/safe" }}
      />,
    );

    const link = screen.getByRole("link", { name: /OR-Library/ });
    expect(link).toHaveAttribute("href", "https://example.com/safe");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("uses valid generated region and heading ids with unusual benchmark ids", () => {
    render(
      <CapabilityCard
        capability={{
          ...optimizationCapability,
          benchmark_id: "or/lib afiro with spaces",
        }}
      />,
    );

    const card = screen.getByTestId("capability-card");
    const labelId = card.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(labelId).not.toContain("or/lib afiro");
    expect(document.getElementById(labelId!)).toHaveTextContent(
      "OR-Library AFIRO 线性规划模板",
    );
  });

  it("accepts the web API benchmark item shape directly without adapters", () => {
    const directApiItem = {
      ...optimizationCapability,
      sample_payload: { task_type: "lp", hidden: "not-visible" },
    } satisfies CapabilityCardCapability;

    render(<CapabilityCard capability={directApiItem} />);

    expect(screen.getByText("or-lib-afiro-lp")).toBeInTheDocument();
    expect(screen.queryByText("not-visible")).not.toBeInTheDocument();
  });
});
