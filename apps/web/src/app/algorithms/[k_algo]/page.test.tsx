// @vitest-environment happy-dom

import { render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OptiCloudClientError, type Algorithm } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  getAlgorithm: vi.fn(),
  kAlgo: "highs-lp",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ k_algo: mocks.kAlgo }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getAlgorithm: mocks.getAlgorithm,
  };
});

import AlgorithmDetailPage from "./page";

const baseAlgorithm: Algorithm = {
  k_algo: "highs-lp",
  task_type: "lp",
  tier: "T1",
  status: "v1",
  model_version: {
    provider_id: "highs",
    kind: "open_source",
    version: "1.7.0",
    provider_url: "https://highs.dev/",
  },
  description_zh: "HiGHS 线性规划",
  description_en: "HiGHS Linear Programming",
  examples: [
    {
      name: "Hello World LP",
      input: {
        task_type: "lp",
        minimize: { c: [1, 1] },
        st: { A: [[1, 1]], b: [10] },
      },
      description: "最小 LP",
    },
  ],
  supported_solvers: ["highs"],
  citation: {
    bibtex: "@article{huangfu2018parallelizing}",
    authors_label_zh: "Huangfu & Hall (2018)",
    year: 2018,
    venue: "Mathematical Programming Computation",
    doi: "10.1007/s12532-017-0130-5",
    url: "https://doi.org/10.1007/s12532-017-0130-5",
  },
  ip_attribution: {
    tier: "L3",
    label_zh: "L3 · License-Only",
    display_name_zh: "HiGHS open-source project",
    summary_zh: "开源 Runner：遵守 MIT license 与论文引用。",
    visibility: "license_only",
    contract_anchor: "docs/legal-templates.md",
  },
  provenance: {
    theory_zh: "线性规划把目标函数和约束都表达为线性关系。",
    theory_en: "Linear programming models objective and constraints as linear relations.",
    configuration_parameters: [
      {
        name: "建模形式",
        value_zh: "线性目标与线性不等式约束",
        description_zh: "公开请求体需要给出目标向量、约束矩阵和右端项。",
        source: "request_schema",
      },
      {
        name: "执行策略",
        value_zh: "同步求解优先",
        description_zh: "目录页只解释可见策略。",
        source: "runtime_policy",
      },
      {
        name: "可解释输出",
        value_zh: "最优目标值、解向量和求解耗时",
        description_zh: "结果字段面向复现实验和教学演示。",
        source: "documentation",
      },
      {
        name: "目录字段",
        value_zh: "公开 catalog 提供的事实",
        description_zh: "页面从算法主字段读取，不在 provenance 中复制。",
        source: "catalog_field",
      },
    ],
    applicable_scenarios_zh: ["连续资源分配", "课堂演示线性约束", "松弛基线"],
    limitations_zh: ["不能直接表达整数决策", "不暴露全部调参选项"],
    citation_source: "catalog_citation",
  },
};

describe("AlgorithmDetailPage provenance", () => {
  beforeEach(() => {
    mocks.getAlgorithm.mockReset();
    mocks.kAlgo = "highs-lp";
  });

  it("renders algorithm provenance without duplicating DOI or BibTeX", async () => {
    mocks.getAlgorithm.mockResolvedValue(baseAlgorithm);

    render(<AlgorithmDetailPage />);

    const provenance = await screen.findByTestId("algorithm-provenance");
    expect(within(provenance).getByText("Algorithm Provenance")).toBeTruthy();
    expect(within(provenance).getByText("线性规划把目标函数和约束都表达为线性关系。")).toBeTruthy();
    expect(
      within(provenance).getByText(
        "Linear programming models objective and constraints as linear relations.",
      ),
    ).toBeTruthy();
    expect(within(provenance).getByText("建模形式")).toBeTruthy();
    expect(within(provenance).getByText("Request schema")).toBeTruthy();
    expect(within(provenance).getByText("Runtime policy")).toBeTruthy();
    expect(within(provenance).getByText("Documentation")).toBeTruthy();
    expect(within(provenance).getByText("Catalog")).toBeTruthy();
    expect(within(provenance).getByText("连续资源分配")).toBeTruthy();
    expect(within(provenance).getByText("不能直接表达整数决策")).toBeTruthy();
    expect(
      within(provenance).getByText(
        "Huangfu & Hall (2018) · Mathematical Programming Computation · 2018",
      ),
    ).toBeTruthy();
    expect(within(provenance).queryByText("10.1007/s12532-017-0130-5")).toBeNull();
    expect(within(provenance).queryByText("@article{huangfu2018parallelizing}")).toBeNull();
    expect(within(provenance).queryByRole("button")).toBeNull();
  });

  it("renders a bounded empty state when provenance is null", async () => {
    mocks.getAlgorithm.mockResolvedValue({ ...baseAlgorithm, provenance: null });

    render(<AlgorithmDetailPage />);

    const provenance = await screen.findByTestId("algorithm-provenance");
    expect(within(provenance).getByText("Provenance 元数据暂未接入")).toBeTruthy();
    expect(screen.getByTestId("citation-block")).toBeTruthy();
    expect(screen.getByTestId("ip-attribution-block")).toBeTruthy();
  });

  it("keeps hidden self-audit rows on the existing 404 path", async () => {
    mocks.kAlgo = "aqgs-acopf";
    mocks.getAlgorithm.mockRejectedValue(
      new OptiCloudClientError({
        status: 404,
        title: "Not Found",
        detail: "k_algo is not published: aqgs-acopf",
      }),
    );

    render(<AlgorithmDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("algorithm-detail-404")).toBeTruthy();
    });
    expect(screen.queryByTestId("algorithm-provenance")).toBeNull();
  });
});
