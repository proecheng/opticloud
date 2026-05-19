/**
 * Console Excel E2E — Story 3.E.1 AC6.
 *
 * 验证 /console/excel 入口、成功态 + filename + 进度模拟、拒绝态 + actionable hint +
 * 教程链接、教程 stub 页非 404、重置回 idle.
 *
 * Note: Playwright drag-drop with File payload is brittle; we go through the
 * FilePicker fallback `<input type='file'>` (sr-only, inside ExcelDropZone) via
 * `setInputFiles`. The drop-handler path itself is covered by Vitest AC5 #1.
 */

import { expect, test } from "../fixtures";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

test.describe("Console Excel surface (3.E.1)", () => {
  test("访客可看到 /console/excel 入口 + DropZone 居中可见", async ({ page }) => {
    await page.goto("/console/excel");
    await expect(page.getByRole("heading", { name: /上传 Excel/ })).toBeVisible();
    await expect(page.getByTestId("excel-drop-zone")).toBeVisible();
  });

  test("选择合法 .xlsx 显示成功态 + 文件名 + 模拟进度切换", async ({ page }) => {
    await page.goto("/console/excel");

    await page.locator('input[type="file"]').setInputFiles({
      name: "small.xlsx",
      mimeType: XLSX_MIME,
      buffer: Buffer.alloc(1024, "a"),
    });

    const card = page.getByTestId("excel-received-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("small.xlsx");
    await expect(card).toContainText("MB");

    // setTimeout(2000ms) — after that the placeholder swap-in renders 下一步 copy
    await expect(page.getByText(/3\.E\.2 将自动识别 task_type/)).toBeVisible({
      timeout: 5_000,
    });
  });

  test("选择过大文件触发拒绝态 + actionable hint + 教程链接", async ({ page }) => {
    await page.goto("/console/excel");

    await page.locator('input[type="file"]').setInputFiles({
      name: "oversized.xlsx",
      mimeType: XLSX_MIME,
      buffer: Buffer.alloc(6 * 1024 * 1024, "b"),
    });

    const rejected = page.getByTestId("excel-rejected-card");
    await expect(rejected).toBeVisible();
    await expect(rejected).toContainText("文件过大");

    // Three actionable-hint bullets
    await expect(page.getByText(/删除多余 sheet/)).toBeVisible();
    await expect(page.getByText(/拆分为 2 个 \.xlsx/)).toBeVisible();
    await expect(page.getByText(/转 CSV/)).toBeVisible();

    const tutorialLink = page.getByRole("link", { name: /看教程/ });
    await expect(tutorialLink).toBeVisible();
    const href = await tutorialLink.getAttribute("href");
    expect(href).toContain("/docs/excel-upload-faq");
  });

  test("教程链接落地页存在且非 404", async ({ page }) => {
    await page.goto("/docs/excel-upload-faq");
    await expect(
      page.getByRole("heading", { name: /Excel 上传常见问题/ }),
    ).toBeVisible();
  });

  test("点击重置按钮恢复 idle 态（成功态 + 拒绝态各测一次）", async ({ page }) => {
    await page.goto("/console/excel");

    // 成功态 → reset
    await page.locator('input[type="file"]').setInputFiles({
      name: "small.xlsx",
      mimeType: XLSX_MIME,
      buffer: Buffer.alloc(1024, "a"),
    });
    await expect(page.getByTestId("excel-received-card")).toBeVisible();
    await page.getByTestId("excel-reset-button").click();
    await expect(page.getByTestId("excel-drop-zone")).toBeVisible();
    await expect(page.getByTestId("excel-received-card")).toHaveCount(0);

    // 拒绝态 → reset
    await page.locator('input[type="file"]').setInputFiles({
      name: "oversized.xlsx",
      mimeType: XLSX_MIME,
      buffer: Buffer.alloc(6 * 1024 * 1024, "b"),
    });
    await expect(page.getByTestId("excel-rejected-card")).toBeVisible();
    await page.getByTestId("excel-reset-button").click();
    await expect(page.getByTestId("excel-drop-zone")).toBeVisible();
    await expect(page.getByTestId("excel-rejected-card")).toHaveCount(0);
  });
});
