/**
 * Algorithm citation block E2E — Story 6.A.1 AC8 (FR R5).
 *
 * Verifies the citation surface on /algorithms/[k_algo]:
 *   1. citation block renders with authors / venue / year / BibTeX
 *   2. DOI link present for papers with DOI
 *   3. unaudited self-developed algorithms are not published publicly
 *   4. 📋 复制 button on the BibTeX block is reachable
 *
 * Replaces the 4 Vitest component cases referenced in the story (apps/web has
 * no jsdom/RTL infra; this file is the single FE rendering check).
 */

import { test, expect } from "../fixtures";

test.describe("Algorithm citation block (FR R5)", () => {
  test("highs-lp 详情页展示 citation + DOI 链接 + 复制按钮可工作", async ({ page }) => {
    await page.goto("/algorithms/highs-lp");

    const block = page.getByTestId("citation-block");
    await expect(block).toBeVisible({ timeout: 10_000 });

    // 学者信息 line
    await expect(block.getByTestId("citation-authors")).toContainText(
      "Huangfu & Hall (2018)",
    );
    await expect(block).toContainText("Mathematical Programming Computation");
    await expect(block).toContainText("2018");

    // DOI link routes via doi.org canonical resolver
    const doi = block.getByTestId("citation-doi");
    await expect(doi).toBeVisible();
    await expect(doi).toHaveAttribute(
      "href",
      "https://doi.org/10.1007/s12532-017-0130-5",
    );
    await expect(doi).toHaveAttribute("rel", /noopener/);
    await expect(doi).toHaveAttribute("target", "_blank");

    // BibTeX code block contains the canonical key
    const bibtex = block.getByTestId("citation-bibtex");
    await expect(bibtex).toContainText("@article{huangfu2018parallelizing,");

    // No 查看出处 link when DOI is present
    await expect(block.getByTestId("citation-url")).toHaveCount(0);

    // Copy button is reachable + carries the BibTeX-specific aria-label.
    // We do NOT click + assert the ✅ 已复制 state-toggle because headless
    // Chromium rejects navigator.clipboard.writeText() (no permission +
    // no user-activation context), so the React state never flips.
    // Matches the existing copy-button assertion pattern in
    // algorithm-details.spec.ts L44.
    const copyButton = bibtex.getByRole("button", { name: /复制 BibTeX/ });
    await expect(copyButton).toBeVisible();
    await expect(copyButton).toHaveAttribute("aria-label", "复制 BibTeX 代码");

    const attribution = page.getByTestId("ip-attribution-block");
    await expect(attribution).toBeVisible();
    await expect(attribution.getByTestId("attribution-badge-L3")).toBeVisible();
    await expect(attribution.getByTestId("ip-attribution-line")).toContainText(
      "开源 Runner",
    );
  });

  test("aqgs-acopf unaudited self algorithm detail is not published", async ({ page }) => {
    await page.goto("/algorithms/aqgs-acopf");

    const notFound = page.getByTestId("algorithm-detail-404");
    await expect(notFound).toBeVisible({ timeout: 10_000 });
    await expect(notFound).toContainText("aqgs-acopf");
    await expect(notFound).toContainText(
      "k_algo is not published: aqgs-acopf",
    );
    await expect(page.getByTestId("citation-block")).toHaveCount(0);
  });
});
