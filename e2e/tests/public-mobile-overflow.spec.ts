/**
 * Public mobile layout regression checks.
 *
 * These assertions catch document-level horizontal scrolling, which component
 * tests cannot measure because happy-dom does not compute real layout.
 */

import type { Page } from "@playwright/test";

import { expect, test } from "../fixtures";

const MOBILE_VIEWPORT = { width: 390, height: 844 };

async function expectNoDocumentHorizontalOverflow(page: Page): Promise<void> {
  const widths = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    bodyClientWidth: document.body.clientWidth,
    docScrollWidth: document.documentElement.scrollWidth,
    docClientWidth: document.documentElement.clientWidth,
    windowInnerWidth: window.innerWidth,
  }));

  const maxScrollWidth = Math.max(widths.bodyScrollWidth, widths.docScrollWidth);
  expect(
    maxScrollWidth,
    JSON.stringify(widths),
  ).toBeLessThanOrEqual(widths.windowInnerWidth);
}

test.describe("public mobile overflow", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test("docs index stays within mobile viewport", async ({ page }) => {
    await page.goto("/docs", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "文档" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Public navigation" })).toBeVisible();
    await expect(page.getByRole("link", { name: /网站操作说明/ }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Hello World Quickstart/ })).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("user guide stays within mobile viewport", async ({ page }) => {
    await page.goto("/docs/user-guide", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "网站操作说明" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "操作说明目录" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "控制台入口" })).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("algorithms catalog stays within mobile viewport", async ({ page }) => {
    await page.goto("/algorithms", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "算法目录" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Public navigation" })).toBeVisible();
    await expect(page.getByTestId("algorithm-card").first()).toBeVisible({ timeout: 10_000 });

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("algorithm detail page stays within mobile viewport", async ({ page }) => {
    await page.goto("/algorithms/highs-lp");

    await expect(page.getByTestId("snippet-python")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("snippet-curl")).toBeVisible();
    await expect(page.getByTestId("citation-bibtex")).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("security disclosure page stays within mobile viewport", async ({ page }) => {
    await page.goto("/security");

    await expect(page.getByRole("heading", { name: "Security Disclosure" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Mermaid flow source" })).toBeVisible();
    await expect(page.getByRole("list", { name: "J9 hardening checklist" })).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("console Excel workbench stays within mobile viewport", async ({ page }) => {
    await page.goto("/console/excel", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: /上传 Excel/ })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Console navigation" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Excel workflow stages" })).toBeVisible();
    await expect(page.getByTestId("excel-drop-zone")).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  test("authenticated provider console stays within mobile viewport", async ({ page }) => {
    await page.addInitScript(() => {
      window.sessionStorage.setItem("jwt_access", "e2e-layout-jwt");
    });
    await page.goto("/console/providers", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Provider Console" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Console navigation" })).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Console governance navigation mobile" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "加载 Provider Console" })).toBeVisible();

    await expectNoDocumentHorizontalOverflow(page);
  });

  for (const route of [
    "/console/predictions",
    "/console/repro",
    "/console/data-exports",
    "/console/classroom",
    "/console/routing-history",
    "/console/legal-inquiry",
    "/console/billing/invoices",
    "/console/audit-logs",
  ]) {
    test(`console route ${route} stays within mobile viewport`, async ({ page }) => {
      await page.addInitScript(() => {
        window.sessionStorage.setItem("jwt_access", "e2e-layout-jwt");
      });
      await page.goto(route, { waitUntil: "domcontentloaded" });

      await expect(page.getByRole("navigation", { name: "Console navigation" })).toBeVisible();
      await expectNoDocumentHorizontalOverflow(page);
    });
  }
});
