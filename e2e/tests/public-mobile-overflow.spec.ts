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
});
