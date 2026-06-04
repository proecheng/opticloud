// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BenchmarkImportResponse, BenchmarkLibraryItem } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  listBenchmarkLibrary: vi.fn(),
  importBenchmarkLibraryItem: vi.fn(),
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

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    listBenchmarkLibrary: mocks.listBenchmarkLibrary,
    importBenchmarkLibraryItem: mocks.importBenchmarkLibraryItem,
  };
});

import BenchmarkLibraryPage from "./page";

const discountSupported = {
  kind: "benchmark_library",
  label_zh: "50% Credits 折扣",
  discount_multiplier: 0.5,
  billing_supported: true,
} as const;

const discountPrediction = {
  ...discountSupported,
  billing_supported: false,
} as const;

function item(
  benchmark_id: string,
  suite: BenchmarkLibraryItem["suite"],
  domain: string,
  task_type: string,
  title_zh: string,
  billingSupported = true,
): BenchmarkLibraryItem {
  return {
    benchmark_id,
    suite,
    domain,
    task_type,
    title_zh,
    title_en: `${title_zh} en`,
    source_name: `${suite} source`,
    source_url: `https://example.com/${suite}`,
    license_note_zh: "仅引用公开来源；模板不是完整数据集镜像。",
    import_kind: billingSupported ? "optimization_request" : "prediction_request",
    target_endpoint: billingSupported ? "/v1/optimizations" : "/v1/predictions",
    discount: billingSupported ? discountSupported : discountPrediction,
    dataset_ref: `benchmark://${suite}/${benchmark_id}`,
    sample_payload: { task_type },
  };
}

const benchmarkItems = [
  item("ieee-14-dc-opf-lp", "ieee", "power", "lp", "IEEE 14 节点 DC-OPF 教学模板"),
  item("cvrplib-a-n32-k5-vrptw", "cvrplib", "routing", "lp", "CVRPLIB A-n32-k5 容量松弛 LP 模板"),
  item("or-lib-afiro-lp", "or-lib", "linear-programming", "lp", "OR-Library AFIRO 线性规划模板"),
  item("m5-walmart-forecast", "m5", "forecast", "forecast", "M5 零售销量预测模板", false),
  item("uci-energy-forecast", "uci", "forecast", "forecast", "UCI Appliances Energy 能耗预测模板", false),
  item("nab-real-known-cause", "nab", "forecast", "forecast", "NAB realKnownCause 异常检测预测模板", false),
];

const optimizationImport: BenchmarkImportResponse = {
  benchmark_id: "or-lib-afiro-lp",
  import_kind: "optimization_request",
  target_endpoint: "/v1/optimizations",
  request_payload: {
    task_type: "lp",
    minimize: { c: [1, 1] },
    st: { A: [[1, 1]], b: [10] },
    options: {
      benchmark_library: true,
      benchmark_id: "or-lib-afiro-lp",
    },
  },
  discount: discountSupported,
  dataset_ref: "benchmark://or-lib/afiro",
  disclaimer_zh: "该 import payload 是最小模板，不是完整数据集镜像。",
  disclaimer_en: "This import payload is a minimal template.",
};

describe("BenchmarkLibraryPage", () => {
  beforeEach(() => {
    mocks.listBenchmarkLibrary.mockReset();
    mocks.importBenchmarkLibraryItem.mockReset();
    mocks.listBenchmarkLibrary.mockResolvedValue(benchmarkItems);
    mocks.importBenchmarkLibraryItem.mockResolvedValue(optimizationImport);
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders public benchmark cards for all six suites without browser storage writes", async () => {
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("page should use API helpers, not submit tasks directly");
    });

    render(<BenchmarkLibraryPage />);

    expect(await screen.findByText("IEEE 14 节点 DC-OPF 教学模板")).toBeTruthy();
    expect(screen.getByText("CVRPLIB A-n32-k5 容量松弛 LP 模板")).toBeTruthy();
    expect(screen.getByText("OR-Library AFIRO 线性规划模板")).toBeTruthy();
    expect(screen.getByText("M5 零售销量预测模板")).toBeTruthy();
    expect(screen.getByText("UCI Appliances Energy 能耗预测模板")).toBeTruthy();
    expect(screen.getByText("NAB realKnownCause 异常检测预测模板")).toBeTruthy();
    expect(screen.getByTestId("benchmark-card-list").querySelectorAll("li")).toHaveLength(6);
    expect(screen.getByRole("link", { name: "返回算法目录" }).getAttribute("href")).toBe(
      "/algorithms",
    );
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("calls list API with suite/domain/task filters and renders empty state", async () => {
    mocks.listBenchmarkLibrary
      .mockResolvedValueOnce(benchmarkItems)
      .mockResolvedValueOnce(benchmarkItems.filter((entry) => entry.suite === "m5"))
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);

    render(<BenchmarkLibraryPage />);

    await screen.findByText("M5 零售销量预测模板");
    fireEvent.change(screen.getByLabelText("Suite"), { target: { value: "m5" } });

    await waitFor(() => {
      expect(mocks.listBenchmarkLibrary).toHaveBeenLastCalledWith({
        suite: "m5",
        domain: undefined,
        taskType: undefined,
      });
    });

    fireEvent.change(screen.getByLabelText("Domain"), { target: { value: "forecast" } });
    await waitFor(() => {
      expect(mocks.listBenchmarkLibrary).toHaveBeenLastCalledWith({
        suite: "m5",
        domain: "forecast",
        taskType: undefined,
      });
    });

    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "forecast" } });
    expect(await screen.findByText("暂无匹配 benchmark")).toBeTruthy();
    expect(mocks.listBenchmarkLibrary).toHaveBeenLastCalledWith({
      suite: "m5",
      domain: "forecast",
      taskType: "forecast",
    });
  });

  it("renders one-click import endpoint and formatted JSON without auto-submitting tasks", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("import view must not POST optimization or prediction tasks");
    });

    render(<BenchmarkLibraryPage />);

    const cards = await screen.findAllByTestId("benchmark-card");
    const orLibCard = cards.find((card) => card.textContent?.includes("or-lib-afiro-lp"));
    expect(orLibCard).toBeTruthy();
    fireEvent.click(within(orLibCard!).getByRole("button", { name: "一键 import" }));

    expect(mocks.importBenchmarkLibraryItem).toHaveBeenCalledWith("or-lib-afiro-lp");
    const panel = await screen.findByTestId("benchmark-import-panel");
    expect(within(panel).getByText("/v1/optimizations")).toBeTruthy();
    expect(within(panel).getByText(/"benchmark_library": true/)).toBeTruthy();
    expect(within(panel).getByText(/"benchmark_id": "or-lib-afiro-lp"/)).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("disables only the importing card and keeps import errors page-owned", async () => {
    let resolveImport: (value: BenchmarkImportResponse) => void = () => undefined;
    mocks.importBenchmarkLibraryItem
      .mockImplementationOnce(
        () =>
          new Promise<BenchmarkImportResponse>((resolve) => {
            resolveImport = resolve;
          }),
      )
      .mockRejectedValueOnce(new Error("import service unavailable"));

    render(<BenchmarkLibraryPage />);

    const cards = await screen.findAllByTestId("benchmark-card");
    const ieeeCard = cards.find((card) => card.textContent?.includes("ieee-14-dc-opf-lp"));
    const orLibCard = cards.find((card) => card.textContent?.includes("or-lib-afiro-lp"));
    expect(ieeeCard).toBeTruthy();
    expect(orLibCard).toBeTruthy();

    fireEvent.click(within(ieeeCard!).getByRole("button", { name: "一键 import" }));
    expect(
      (within(ieeeCard!).getByRole("button", { name: "生成中" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (within(orLibCard!).getByRole("button", { name: "一键 import" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);

    resolveImport(optimizationImport);
    await screen.findByTestId("benchmark-import-panel");

    fireEvent.click(within(orLibCard!).getByRole("button", { name: "一键 import" }));
    expect(await screen.findByText(/import service unavailable/)).toBeTruthy();
    expect(screen.getByTestId("benchmark-import-panel")).toBeTruthy();
  });
});
