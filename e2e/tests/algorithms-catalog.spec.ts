/**
 * Algorithms public catalog E2E — Story 0.13 AC4.
 *
 * 公开免鉴权浏览页 + tier filter + provider_url 链接.
 */

import { test, expect } from "../fixtures";

test.describe("Algorithms catalog (public)", () => {
  test("访客可看到已发布算法 + Provider 透明", async ({ page }) => {
    await page.goto("/algorithms");

    await expect(page.getByRole("heading", { name: "算法目录" })).toBeVisible();

    // Story 2.8: public catalog excludes unaudited self-developed algorithms.
    const cards = page.getByTestId("algorithm-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(7);
    expect((await cards.allTextContents()).join(" ")).not.toContain("aqgs-acopf");

    // First card has provider_url link
    const firstCard = cards.first();
    const providerLink = firstCard.getByRole("link", { name: /https/ });
    await expect(providerLink).toBeVisible();
    const href = await providerLink.getAttribute("href");
    expect(href).toMatch(/^https?:\/\//);
  });

  // Story 2.3 — per-tier chip filtering (replaces the old optimization/prediction button)
  test("点击 T1 chip 只显示 T1 SKU", async ({ page }) => {
    await page.goto("/algorithms");
    await page.getByTestId("tier-chip-T1").click();

    const cards = page.getByTestId("algorithm-card");
    await expect(cards).toHaveCount(1, { timeout: 10_000 });
    await expect(cards.first()).toContainText("highs-lp");
  });

  test("点击 T1 + P1 chip 显示两个 SKU", async ({ page }) => {
    await page.goto("/algorithms");
    await page.getByTestId("tier-chip-T1").click();
    await page.getByTestId("tier-chip-P1").click();

    const cards = page.getByTestId("algorithm-card");
    await expect(cards).toHaveCount(2, { timeout: 10_000 });
    const allText = (await cards.allTextContents()).join(" ");
    expect(allText).toContain("highs-lp");
    expect(allText).toContain("arima-forecast");
  });

  test("URL ?tier=T1,P1 hydrates 初始 chip 选中状态", async ({ page }) => {
    await page.goto("/algorithms?tier=T1,P1");

    // Chips reflect URL state (aria-pressed=true)
    await expect(page.getByTestId("tier-chip-T1")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("tier-chip-P1")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("tier-chip-T2")).toHaveAttribute("aria-pressed", "false");

    // Cards match the filter
    const cards = page.getByTestId("algorithm-card");
    await expect(cards).toHaveCount(2, { timeout: 10_000 });

    // URL kept stable after settle
    await expect(page).toHaveURL(/tier=P1%2CT1|tier=T1%2CP1|tier=T1,P1|tier=P1,T1/);
  });
});
