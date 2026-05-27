/**
 * Academic attribution Console E2E — Story 6.A.5.
 *
 * Covers the read-only attribution review surface: summary counts, representative
 * L1/L3 rows, citation-key extraction, and contract anchors.
 */

import { test, expect } from "../fixtures";

test.describe("Academic attribution console (Story 6.A.5)", () => {
  test("Console lists attribution counts and representative rows", async ({ page }) => {
    await page.goto("/console/academic-attribution", { waitUntil: "networkidle" });

    await expect(
      page.getByRole("heading", { name: "Academic Attribution Review" }),
    ).toBeVisible();

    await expect(page.getByTestId("attribution-count-L1")).toContainText("0");
    await expect(page.getByTestId("attribution-count-L2")).toContainText("0");
    await expect(page.getByTestId("attribution-count-L3")).toContainText("7");

    await expect(page.getByTestId("attribution-row-aqgs-acopf")).toHaveCount(0);

    const highs = page.getByTestId("attribution-row-highs-lp");
    await expect(highs.getByTestId("attribution-badge-L3")).toBeVisible();
    await expect(highs).toContainText("huangfu2018parallelizing");
    await expect(highs).toContainText("docs/legal-templates.md Doc 1");
  });
});
