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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

import UserGuidePage from "./page";

describe("UserGuidePage", () => {
  it("renders the HTML operation manual and links to core workflows", () => {
    renderWithIntl(<UserGuidePage />);

    expect(screen.getByRole("heading", { name: "网站操作说明" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "操作说明目录" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "快速开始" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "常用流程" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "控制台入口" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "排障与支持" })).toBeTruthy();

    const publicNav = screen.getByRole("navigation", { name: "Public navigation" });
    expect(within(publicNav).getByRole("link", { name: "文档", current: "page" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "开始注册" }).getAttribute("href")).toBe(
      "/auth/signup",
    );
    expect(screen.getByRole("link", { name: "查看 Quickstart" }).getAttribute("href")).toBe(
      "/docs/quickstart",
    );
    expect(screen.getByRole("link", { name: "打开 Excel 控制台" }).getAttribute("href")).toBe(
      "/console/excel",
    );
    expect(screen.getByRole("link", { name: "浏览算法目录" }).getAttribute("href")).toBe(
      "/algorithms",
    );
    expect(screen.getByRole("link", { name: "账单发票" }).getAttribute("href")).toBe(
      "/console/billing/invoices",
    );
  });
});
