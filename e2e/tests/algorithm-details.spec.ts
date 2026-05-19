/**
 * Algorithm detail page E2E — Story 2.2 AC6.
 *
 * Covers list→detail navigation, Python/cURL snippets, 404 path, and empty-examples
 * degraded state.
 */

import { test, expect } from "../fixtures";

test.describe("Algorithm details page", () => {
  test("从列表页点击 highs-lp 跳转到详情页", async ({ page }) => {
    await page.goto("/algorithms");

    const card = page
      .locator('[data-testid="algorithm-card"]')
      .filter({ hasText: "highs-lp" })
      .first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    // The wrapping Link inside the card carries aria-label "查看 highs-lp 详情"
    await card.getByRole("link", { name: /查看 highs-lp 详情/ }).click();

    await expect(page).toHaveURL(/\/algorithms\/highs-lp$/);
    await expect(
      page.getByTestId("algorithm-detail-header").getByRole("heading", { level: 1 }),
    ).toContainText("highs-lp");
    await expect(page.getByTestId("algorithm-detail-header")).toContainText(
      "https://highs.dev/",
    );
  });

  test("详情页展示 Python + cURL 两个代码段 + 复制按钮", async ({ page }) => {
    await page.goto("/algorithms/highs-lp");

    const pythonBlock = page.getByTestId("snippet-python");
    await expect(pythonBlock).toBeVisible();
    await expect(pythonBlock).toContainText("requests.post");
    await expect(pythonBlock).toContainText('"task_type": "lp"');

    const curlBlock = page.getByTestId("snippet-curl");
    await expect(curlBlock).toBeVisible();
    await expect(curlBlock).toContainText("curl -X POST");

    const copyButtons = page.getByRole("button", { name: /复制/ });
    expect(await copyButtons.count()).toBeGreaterThanOrEqual(2);
  });

  test("未知 k_algo 显示 404 状态卡", async ({ page }) => {
    await page.goto("/algorithms/does-not-exist");

    const notFound = page.getByTestId("algorithm-detail-404");
    await expect(notFound).toBeVisible({ timeout: 10_000 });
    await expect(notFound).toContainText("未知算法");
    await expect(page.getByRole("link", { name: /返回算法目录/ })).toBeVisible();
  });

  test("空 examples 的 SKU 也能打开详情页", async ({ page }) => {
    await page.goto("/algorithms/highs-milp");

    // Success path: header visible, NOT the 404 card
    await expect(
      page.getByTestId("algorithm-detail-header").getByRole("heading", { level: 1 }),
    ).toContainText("highs-milp");
    await expect(page.getByTestId("algorithm-detail-404")).toHaveCount(0);

    // Degraded path: placeholder snippet container with the "示例载荷待补充" note
    const placeholder = page.getByTestId("snippet-placeholder");
    await expect(placeholder).toBeVisible();
    await expect(placeholder).toContainText("示例载荷待补充");
  });
});
