// @vitest-environment happy-dom

import { screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

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

import ConsoleExcelPage from "./page";

describe("ConsoleExcelPage", () => {
  it("renders the console shell, workflow stages, and idle upload surface", () => {
    renderWithIntl(<ConsoleExcelPage />);

    expect(screen.getByRole("heading", { name: "上传 Excel，自动求解" })).toBeTruthy();

    const workflowNav = screen.getByRole("navigation", { name: "Console navigation" });
    expect(
      within(workflowNav).getByRole("link", { name: "Excel", current: "page" }).getAttribute("href"),
    ).toBe("/console/excel");
    expect(within(workflowNav).getByRole("link", { name: "预测" }).getAttribute("href")).toBe(
      "/console/predictions",
    );
    const governanceNav = screen.getByRole("navigation", {
      name: "Console governance navigation",
    });
    expect(within(governanceNav).getByRole("link", { name: "账单" }).getAttribute("href")).toBe(
      "/console/billing/invoices",
    );

    const supportNav = screen.getByRole("navigation", { name: "Console support navigation" });
    expect(within(supportNav).getByRole("link", { name: "文档" }).getAttribute("href")).toBe(
      "/docs",
    );
    expect(within(supportNav).getByRole("link", { name: "算法目录" }).getAttribute("href")).toBe(
      "/algorithms",
    );

    const stageRail = screen.getByRole("region", { name: "Excel workflow stages" });
    expect(within(stageRail).getByText("上传")).toBeTruthy();
    expect(within(stageRail).getByText("识别")).toBeTruthy();
    expect(within(stageRail).getByText("预览")).toBeTruthy();
    expect(within(stageRail).getByText("结果/下载")).toBeTruthy();

    expect(screen.getByTestId("excel-drop-zone")).toBeTruthy();
    expect(screen.getByText("本地处理边界")).toBeTruthy();
    expect(screen.getByText("最多 50,000 行")).toBeTruthy();
    expect(screen.getByRole("link", { name: "查看 Excel 上传 FAQ" }).getAttribute("href")).toBe(
      "/docs/excel-upload-faq",
    );
  });
});
