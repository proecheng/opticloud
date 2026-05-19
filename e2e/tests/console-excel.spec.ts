/**
 * Console Excel E2E — Story 3.E.1 + 3.E.2.
 *
 * 3.E.1: 入口、成功态 + filename + 进度模拟、拒绝态 + actionable hint +
 *        教程链接、教程 stub 页非 404、重置回 idle.
 * 3.E.2: 真 .xlsx 解析 → Confirm Modal → 推荐 + 手动 override + handoff card;
 *        50K-row 上限拒绝;解析失败错误卡.
 *
 * Note: Playwright drag-drop with File payload is brittle; we go through the
 * FilePicker fallback `<input type='file'>` (sr-only, inside ExcelDropZone) via
 * `setInputFiles`. The drop-handler path itself is covered by Vitest AC5 #1.
 */

import { utils as xlsxUtils, write as xlsxWrite } from "xlsx";

import { expect, test } from "../fixtures";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

interface SheetSpec {
  name: string;
  rows: (string | number | null)[][];
}

function buildXlsxBuffer(sheets: SheetSpec[]): Buffer {
  const wb = xlsxUtils.book_new();
  for (const s of sheets) {
    const ws = xlsxUtils.aoa_to_sheet(s.rows);
    xlsxUtils.book_append_sheet(wb, ws, s.name);
  }
  return Buffer.from(xlsxWrite(wb, { bookType: "xlsx", type: "buffer" }));
}

// Build fixtures once per worker — keeps file IO out of the test bodies.
const VRPTW_BUFFER = buildXlsxBuffer([
  {
    name: "客户",
    rows: [
      ["客户名", "经度", "纬度", "需求"],
      ["A", 121.1, 31.2, 5],
      ["B", 121.3, 31.4, 7],
    ],
  },
  {
    name: "车辆",
    rows: [
      ["编号", "容量"],
      ["V1", 50],
    ],
  },
  {
    name: "时间窗",
    rows: [
      ["客户名", "开始", "结束"],
      ["A", "08:00", "12:00"],
      ["B", "10:00", "14:00"],
    ],
  },
]);

const SCHEDULE_BUFFER = buildXlsxBuffer([
  {
    name: "任务",
    rows: [
      ["任务名", "工期", "截止"],
      ["T1", 4, "2026-06-01"],
    ],
  },
  {
    name: "资源",
    rows: [
      ["资源", "数量"],
      ["机床A", 2],
    ],
  },
]);

function buildLargeBuffer(rows: number): Buffer {
  const data: (string | number)[][] = [["客户名", "经度", "纬度"]];
  for (let i = 0; i < rows; i++) {
    data.push([`C${i}`, 121 + (i % 10) * 0.01, 31 + (i % 10) * 0.01]);
  }
  return buildXlsxBuffer([{ name: "客户", rows: data }]);
}

test.describe("Console Excel surface (3.E.1)", () => {
  test("访客可看到 /console/excel 入口 + DropZone 居中可见", async ({ page }) => {
    await page.goto("/console/excel");
    await expect(page.getByRole("heading", { name: /上传 Excel/ })).toBeVisible();
    await expect(page.getByTestId("excel-drop-zone")).toBeVisible();
  });

  test("选择合法 .xlsx — 显示 received card + 解析中提示", async ({ page }) => {
    await page.goto("/console/excel");

    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    const card = page.getByTestId("excel-received-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("vrptw.xlsx");
    await expect(card).toContainText("MB");
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

  test("拒绝态 → 点击重试恢复 idle (3.E.1 path)", async ({ page }) => {
    await page.goto("/console/excel");

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

  // ===== Story 3.E.2 — real parse + detect + Modal =====

  test("拖入 VRPTW workbook → 显示 confirm modal + 推荐 vrptw", async ({ page }) => {
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    const modal = page.getByTestId("confirmation-modal");
    await expect(modal).toBeVisible({ timeout: 10_000 });
    await expect(modal).toContainText(/VRPTW/);
    await expect(page.getByRole("button", { name: "确认" })).toBeVisible();
    await expect(page.getByTestId("detection-confidence")).toContainText(/可信度/);
  });

  test("点击确认 → 展示 placeholder handoff card", async ({ page }) => {
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "确认" }).click();

    const handoff = page.getByTestId("excel-confirmed-card");
    await expect(handoff).toBeVisible();
    await expect(handoff).toContainText(/VRPTW/);
  });

  test("'其它' 切换为 schedule → 确认后 handoff 展示 schedule + 覆盖说明", async ({ page }) => {
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page
      .getByTestId("detection-override-select")
      .selectOption({ value: "schedule" });
    await page.getByRole("button", { name: "确认" }).click();

    const handoff = page.getByTestId("excel-confirmed-card");
    await expect(handoff).toBeVisible();
    await expect(handoff).toContainText(/Schedule/);
    await expect(handoff).toContainText(/覆盖系统推荐/);
  });

  test("解析失败的文件显示 parse-error 卡", async ({ page }) => {
    await page.goto("/console/excel");
    // 200B garbage with .xlsx suffix — passes 3.E.1 size + suffix checks,
    // fails 3.E.2 parse (not a real workbook).
    await page.locator('input[type="file"]').setInputFiles({
      name: "garbage.xlsx",
      mimeType: XLSX_MIME,
      buffer: Buffer.alloc(200, "z"),
    });

    const errCard = page.getByTestId("excel-parse-error-card");
    await expect(errCard).toBeVisible({ timeout: 10_000 });
    await expect(errCard).toContainText(/无法解析/);
  });
});
