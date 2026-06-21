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

import DocsIndexPage from "./page";

describe("DocsIndexPage", () => {
  it("renders a real /docs index with current product documentation links", () => {
    renderWithIntl(<DocsIndexPage />);

    expect(screen.getByRole("heading", { name: "文档" })).toBeTruthy();
    const primaryNav = screen.getByRole("navigation", { name: "Public navigation" });
    expect(primaryNav).toBeTruthy();
    expect(
      within(primaryNav).getByRole("link", { name: "文档", current: "page" }).getAttribute("href"),
    ).toBe("/docs");
    expect(within(primaryNav).getByRole("link", { name: "算法目录" }).getAttribute("href")).toBe(
      "/algorithms",
    );
    expect(screen.getByRole("link", { name: "立即注册" }).getAttribute("href")).toBe(
      "/auth/signup",
    );
    expect(screen.getByRole("heading", { name: "开始接入" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "推荐阅读顺序" })).toBeTruthy();
    expect(
      screen
        .getAllByRole("link", { name: /网站操作说明/ })
        .some((link) => link.getAttribute("href") === "/docs/user-guide"),
    ).toBe(true);
    expect(screen.getByRole("link", { name: /Hello World Quickstart/ }).getAttribute("href")).toBe(
      "/docs/quickstart",
    );
    expect(screen.getByRole("link", { name: /Excel 上传常见问题/ }).getAttribute("href")).toBe(
      "/docs/excel-upload-faq",
    );
    expect(
      screen.getByRole("link", { name: /Academic Provider Handbook/ }).getAttribute("href"),
    ).toBe("/docs/academic-provider-handbook");
    expect(screen.getByRole("link", { name: /Academic Onboarding FAQ/ }).getAttribute("href")).toBe(
      "/docs/customer-faqs/academic-onboarding-faq",
    );
  });
});
