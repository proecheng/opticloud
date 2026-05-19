/**
 * Algorithm citation block E2E — Story 6.A.1 AC8 (FR R5).
 *
 * Verifies the citation surface on /algorithms/[k_algo]:
 *   1. citation block renders with authors / venue / year / BibTeX
 *   2. DOI link present for papers with DOI
 *   3. URL-only entries (aqgs-acopf) show 查看出处 instead of DOI
 *   4. 📋 复制 button on the BibTeX block toggles to ✅ 已复制
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

    // Copy button toggles to ✅ 已复制 (proxy for clipboard success)
    const copyButton = bibtex.getByRole("button", { name: /复制 BibTeX/ });
    await copyButton.click();
    await expect(copyButton).toContainText("已复制", { timeout: 2_000 });
  });

  test("aqgs-acopf (自研, 无 DOI) 展示 查看出处 链接而非 DOI", async ({ page }) => {
    await page.goto("/algorithms/aqgs-acopf");

    const block = page.getByTestId("citation-block");
    await expect(block).toBeVisible({ timeout: 10_000 });

    // 学者信息 学界 团队
    await expect(block.getByTestId("citation-authors")).toContainText(
      "OptiCloud / Trust-Tech 团队",
    );
    await expect(block).toContainText("Software (Apache 2.0)");
    await expect(block).toContainText("2025");

    // No DOI link
    await expect(block.getByTestId("citation-doi")).toHaveCount(0);

    // URL fallback link
    const url = block.getByTestId("citation-url");
    await expect(url).toBeVisible();
    await expect(url).toHaveAttribute(
      "href",
      "https://github.com/opticloud/aqgs",
    );

    // BibTeX uses @software entry type
    await expect(block.getByTestId("citation-bibtex")).toContainText(
      "@software{aqgs2025opticloud,",
    );
  });
});
