// @vitest-environment happy-dom

import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

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

import DocsIndexPage from "./page";

describe("DocsIndexPage", () => {
  it("renders a real /docs index with current product documentation links", () => {
    render(<DocsIndexPage />);

    expect(screen.getByRole("heading", { name: "文档" })).toBeTruthy();
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
