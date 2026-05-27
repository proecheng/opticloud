/**
 * /academic page E2E — Story 6.A.2 AC9 (Epic 6.A.2 — BibTeX 营销 Landing 页).
 *
 * Covers: hero + published citation cards + edu CTA, BibTeX/DOI conditional rendering,
 * unaudited self-developed hiding, the 4-card 飞轮 diagram, and the landing-page
 * 学术合作 nav cross-link.
 */

import { test, expect } from "../fixtures";

test.describe("Academic landing page (Epic 6.A.2)", () => {
  test("学者访问 /academic 看到 hero + 已发布引用卡 + edu CTA", async ({ page }) => {
    await page.goto("/academic", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "可复现、可引用、可被发现",
    );

    // Public academic page renders published algorithms only.
    for (const kAlgo of [
      "highs-lp",
      "highs-milp",
      "or-tools-vrptw",
      "or-tools-cp-sat",
      "chronos-t5-forecast",
      "arima-forecast",
      "lstm-forecast",
    ]) {
      await expect(page.getByTestId(`citation-card-${kAlgo}`)).toBeVisible();
    }
    await expect(page.getByTestId("citation-card-aqgs-acopf")).toHaveCount(0);

    const eduCta = page.getByTestId("edu-cta-signup");
    await expect(eduCta).toBeVisible();
    await expect(eduCta).toHaveAttribute("href", "/auth/signup");
  });

  test("highs-lp citation card 内 BibTeX + DOI 链接均渲染", async ({ page }) => {
    await page.goto("/academic", { waitUntil: "networkidle" });

    const card = page.getByTestId("citation-card-highs-lp");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("bibtex-highs-lp")).toContainText(
      "@article{huangfu2018parallelizing,",
    );

    const doi = card.getByTestId("doi-highs-lp");
    await expect(doi).toBeVisible();
    await expect(doi).toHaveAttribute(
      "href",
      "https://doi.org/10.1007/s12532-017-0130-5",
    );
    await expect(doi).toHaveAttribute("rel", /noopener/);
  });

  test("unaudited aqgs-acopf 自研算法不出现在公开 academic 引用列表", async ({ page }) => {
    await page.goto("/academic", { waitUntil: "networkidle" });

    await expect(page.getByTestId("citation-card-aqgs-acopf")).toHaveCount(0);
    await expect(page.getByTestId("attribution-line-aqgs-acopf")).toHaveCount(0);
  });

  test("highs-lp citation card 显示 L3 license-only attribution", async ({ page }) => {
    await page.goto("/academic", { waitUntil: "networkidle" });

    const card = page.getByTestId("citation-card-highs-lp");
    await expect(card.getByTestId("attribution-badge-L3")).toBeVisible();
    await expect(page.getByTestId("attribution-line-highs-lp")).toContainText(
      "开源 Runner",
    );
  });

  test("学界变现飞轮 4 张卡都可见且文案完整", async ({ page }) => {
    await page.goto("/academic", { waitUntil: "networkidle" });

    for (let step = 1; step <= 4; step++) {
      await expect(page.getByTestId(`flywheel-step-${step}`)).toBeVisible();
    }
    await expect(page.getByTestId("flywheel-step-1")).toContainText("学者免费");
    await expect(page.getByTestId("flywheel-step-2")).toContainText("学者发论文");
    await expect(page.getByTestId("flywheel-step-3")).toContainText("论文带来新学者");
    await expect(
      page.getByRole("heading", { name: /学界变现飞轮/ }),
    ).toBeVisible();
  });

  test('Landing page header "学术合作" 链接跳到 /academic', async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "学术合作" }).click();
    await expect(page).toHaveURL(/\/academic$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "可复现、可引用、可被发现",
    );
  });
});
