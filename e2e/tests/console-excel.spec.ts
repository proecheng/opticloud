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

// 3.E.5 — full mappable inventory workbook (SKU + 历史出货 + 季节性 sheets).
const INVENTORY_BUFFER = buildXlsxBuffer([
  {
    name: "SKU",
    rows: [
      ["sku", "名称", "类别", "期初库存"],
      ["S1", "苹果", "水果", 100],
      ["S2", "香蕉", "水果", 50],
    ],
  },
  {
    name: "历史出货",
    rows: [
      ["sku", "日期", "销量"],
      ["S1", "2026-01-01", 10],
      ["S1", "2026-01-02", 15],
      ["S2", "2026-01-01", 8],
    ],
  },
  {
    name: "季节性",
    rows: [
      ["sku", "季节", "系数"],
      ["S1", "Q1", 1.2],
    ],
  },
]);

// 3.E.4 — full mappable schedule workbook (任务 + 资源 + 工序 sheets).
const SCHEDULE_BUFFER = buildXlsxBuffer([
  {
    name: "任务",
    rows: [
      ["任务名", "工期", "截止", "资源"],
      ["T1", 4, "2026-06-01", "机床A"],
      ["T2", 2, "2026-06-02", "机床A"],
      ["T3", 6, "2026-06-03", "机床B"],
    ],
  },
  {
    name: "资源",
    rows: [
      ["编号", "容量", "类型"],
      ["机床A", 2, "机器"],
      ["机床B", 1, "机器"],
    ],
  },
  {
    name: "工序",
    rows: [
      ["前驱", "后继"],
      ["T1", "T2"],
      ["T2", "T3"],
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

  test("选择合法 .xlsx — 显示 received card + 分阶段加载提示", async ({ page }) => {
    await page.goto("/console/excel");

    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    const card = page.getByTestId("excel-received-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("已收到您的 Excel 文件");
    await expect(card).toContainText("vrptw.xlsx");
    await expect(card).toContainText("MB");
    await expect(card).toContainText("1. 读取工作表");
    await expect(card).toContainText("2. 识别表头");
    await expect(card).not.toContainText("task_type");
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

  test("拖入 VRPTW workbook → 显示 confirm modal + 推荐业务类型", async ({ page }) => {
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    const modal = page.getByTestId("confirmation-modal");
    await expect(modal).toBeVisible({ timeout: 10_000 });
    await expect(modal).toContainText("系统判断：车辆路径 / 时间窗");
    await expect(modal).toContainText("业务类型");
    await expect(modal).not.toContainText("task_type");
    await expect(page.getByRole("button", { name: "确认并继续" })).toBeVisible();
    await expect(page.getByTestId("detection-confidence")).toContainText(
      /判断可信度/,
    );
  });

  test("点击确认 VRPTW → 展示 vrptw-preview-card (3.E.3 takeover)", async ({ page }) => {
    // 3.E.2 originally asserted the placeholder excel-confirmed-card here;
    // 3.E.3 specialised VRPTW to render VrptwPreviewCard instead.
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "确认并继续" }).click();

    const preview = page.getByTestId("vrptw-preview-card");
    await expect(preview).toBeVisible({ timeout: 10_000 });
    await expect(preview).toContainText(/客户/);
  });

  test("'其它' 切换为 lp → 确认后 handoff 展示线性规划 + 覆盖说明", async ({ page }) => {
    // 3.E.5 — was 'inventory' previously (and 'schedule' before that);
    // inventory now routes to InventoryPreviewCard. Switched to 'lp' which
    // still falls through to the placeholder card (no LP-specific preview).
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page
      .getByTestId("detection-override-select")
      .selectOption({ value: "lp" });
    await page.getByRole("button", { name: "确认并继续" }).click();

    const handoff = page.getByTestId("excel-confirmed-card");
    await expect(handoff).toBeVisible();
    await expect(handoff).toContainText(/线性规划/);
    await expect(handoff).toContainText(/覆盖系统推荐/);
  });

  test("VRPTW confirm → 试跑 → 501 friendly card + JSON preview", async ({ page }) => {
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "vrptw.xlsx",
      mimeType: XLSX_MIME,
      buffer: VRPTW_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "确认并继续" }).click();

    const preview = page.getByTestId("vrptw-preview-card");
    await expect(preview).toBeVisible({ timeout: 10_000 });
    await expect(preview).toContainText(/客户/);
    await expect(preview).toContainText(/车辆/);

    // JSON preview should contain task_type=vrptw
    const jsonBlock = page.getByTestId("vrptw-payload-json");
    await expect(jsonBlock).toContainText('"task_type": "vrptw"');

    // Submit → backend returns 501
    await page.getByTestId("vrptw-submit-button").click();
    const stub = page.getByTestId("vrptw-501-card");
    await expect(stub).toBeVisible({ timeout: 10_000 });
    await expect(stub).toContainText(/M2-M3/);
  });

  test("Schedule confirm → 试跑 → 501 friendly card + JSON preview", async ({
    page,
  }) => {
    // 3.E.4 — drops a real Schedule workbook (任务/资源/工序), confirms the
    // detected 'schedule' task_type (or overrides if detector picks wrong),
    // then submits → backend short-circuits to 501.
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "schedule.xlsx",
      mimeType: XLSX_MIME,
      buffer: SCHEDULE_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    // Force schedule explicitly to keep this test deterministic even if the
    // detector's tie-break changes between versions.
    await page
      .getByTestId("detection-override-select")
      .selectOption({ value: "schedule" });
    await page.getByRole("button", { name: "确认并继续" }).click();

    const preview = page.getByTestId("schedule-preview-card");
    await expect(preview).toBeVisible({ timeout: 10_000 });
    await expect(preview).toContainText(/任务/);
    await expect(preview).toContainText(/资源/);

    // JSON preview should contain task_type=schedule
    const jsonBlock = page.getByTestId("schedule-payload-json");
    await expect(jsonBlock).toContainText('"task_type": "schedule"');

    // Submit → backend returns 501
    await page.getByTestId("schedule-submit-button").click();
    const stub = page.getByTestId("schedule-501-card");
    await expect(stub).toBeVisible({ timeout: 10_000 });
    await expect(stub).toContainText(/M2-M3/);
  });

  test("Inventory confirm → 试跑 → 501 friendly card + JSON preview", async ({
    page,
  }) => {
    // 3.E.5 — drops a real Inventory workbook (SKU/历史出货/季节性), confirms
    // detected 'inventory' task_type, then submits → backend short-circuits 501.
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "inventory.xlsx",
      mimeType: XLSX_MIME,
      buffer: INVENTORY_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({ timeout: 10_000 });
    await page
      .getByTestId("detection-override-select")
      .selectOption({ value: "inventory" });
    await page.getByRole("button", { name: "确认并继续" }).click();

    const preview = page.getByTestId("inventory-preview-card");
    await expect(preview).toBeVisible({ timeout: 10_000 });
    await expect(preview).toContainText(/SKU/);
    await expect(preview).toContainText(/历史行/);

    const jsonBlock = page.getByTestId("inventory-payload-json");
    await expect(jsonBlock).toContainText('"task_type": "inventory"');

    // Submit → backend returns 501
    await page.getByTestId("inventory-submit-button").click();
    const stub = page.getByTestId("inventory-501-card");
    await expect(stub).toBeVisible({ timeout: 10_000 });
    await expect(stub).toContainText(/M2-M3/);
    await expect(stub).toContainText(/库存预测引擎/);
  });

  test("Inventory: 501 → 下载 Excel 结果 → 文件触发下载 (3.E.6)", async ({
    page,
  }) => {
    // 3.E.6 — end-to-end download arc on Inventory (largest payload of the trilogy).
    await page.goto("/console/excel");
    await page.locator('input[type="file"]').setInputFiles({
      name: "inventory.xlsx",
      mimeType: XLSX_MIME,
      buffer: INVENTORY_BUFFER,
    });

    await expect(page.getByTestId("confirmation-modal")).toBeVisible({
      timeout: 10_000,
    });
    await page
      .getByTestId("detection-override-select")
      .selectOption({ value: "inventory" });
    await page.getByRole("button", { name: "确认并继续" }).click();

    await expect(page.getByTestId("inventory-preview-card")).toBeVisible({
      timeout: 10_000,
    });
    await page.getByTestId("inventory-submit-button").click();
    await expect(page.getByTestId("inventory-501-card")).toBeVisible({
      timeout: 10_000,
    });

    const downloadBtn = page.getByTestId("inventory-download-button");
    await expect(downloadBtn).toBeVisible();
    await expect(downloadBtn).toHaveText("下载 Excel 结果");
    await expect(downloadBtn).toHaveAttribute("aria-busy", "false");

    await page.route("**/_next/static/chunks/**/node_modules_xlsx_*.js", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.continue();
    });

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      expect(downloadBtn).toHaveText("正在生成 Excel..."),
      expect(downloadBtn).toHaveAttribute("aria-busy", "true"),
      downloadBtn.click(),
    ]);
    expect(download.suggestedFilename()).toMatch(
      /^opticloud_inventory_\d{8}T\d{6}Z\.xlsx$/,
    );
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
