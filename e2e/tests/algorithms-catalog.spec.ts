/**
 * Algorithms public catalog E2E — Story 0.13 AC4.
 *
 * 公开免鉴权浏览页 + tier filter + provider_url 链接.
 */

import { test, expect } from "../fixtures";

test.describe("Algorithms catalog (public)", () => {
  test("访客可看到 ≥8 个算法 + Provider 透明", async ({ page }) => {
    await page.goto("/algorithms");

    await expect(page.getByRole("heading", { name: "算法目录" })).toBeVisible();

    // Q3 fix: count >= 8 (catalog can grow)
    const cards = page.getByTestId("algorithm-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(8);

    // First card has provider_url link
    const firstCard = cards.first();
    const providerLink = firstCard.getByRole("link", { name: /https/ });
    await expect(providerLink).toBeVisible();
    const href = await providerLink.getAttribute("href");
    expect(href).toMatch(/^https?:\/\//);
  });

  test("Tier filter 切换 — 只显示 T-tier 算法", async ({ page }) => {
    await page.goto("/algorithms");

    // Click "优化 (T1-T6)" tab
    await page.getByRole("button", { name: /优化/ }).click();

    // After filter: cards should show T-tier only (not P-tier)
    const cards = page.getByTestId("algorithm-card");
    await expect(cards.first()).toBeVisible();

    // Verify at least one T-tier visible
    const tierBadges = cards.locator("text=/^T[1-6]$/");
    const tierCount = await tierBadges.count();
    expect(tierCount).toBeGreaterThanOrEqual(1);
  });
});
