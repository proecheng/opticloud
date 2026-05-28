/**
 * 老张 Excel vertical slice E2E — Story 3.E.9.
 *
 * Coverage matrix:
 * - multi-sheet handling: Inventory happy path (SKU / 历史出货 / 季节性)
 * - formula/cached-value tolerance: deferred risk for this story
 * - corrupt workbook recovery: existing console-excel.spec.ts parse-error case
 * - password-protected workbook: not applicable to 老张 Excel v1 path
 * - oversize recovery: existing console-excel.spec.ts oversize rejection case
 * - shared-device/session leakage: fresh user + fresh page/context in this spec
 * - route recovery: welcome page link -> /console/excel, after closing modal if needed
 */

import * as XLSX from "xlsx";
import { readFileSync } from "node:fs";

import { expect, test } from "../fixtures";
import { randomEmail, randomPhone } from "../fixtures/auth";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

interface SheetSpec {
  name: string;
  rows: (string | number | null)[][];
}

function buildXlsxBuffer(sheets: SheetSpec[]): Buffer {
  const wb = XLSX.utils.book_new();
  for (const sheet of sheets) {
    const ws = XLSX.utils.aoa_to_sheet(sheet.rows);
    XLSX.utils.book_append_sheet(wb, ws, sheet.name);
  }
  return Buffer.from(XLSX.write(wb, { bookType: "xlsx", type: "buffer" }));
}

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

test.describe.serial("老张 Excel vertical slice (3.E.9)", () => {
  test("老张从注册到下载库存结果 Excel 的完整路径", async ({ page }, testInfo) => {
    const phone = randomPhone();
    const email = randomEmail();

    await test.step("老张 1/7 - 从首页进入注册页", async () => {
      await page.goto("/");
      await page.getByRole("navigation").getByRole("link", { name: "立即注册" }).click();
      await expect(page).toHaveURL(/\/auth\/signup$/);
      await expect(page.getByTestId("signup-wizard")).toBeVisible();
    });

    await test.step("老张 2/7 - 完成 UI 注册并进入 welcome", async () => {
      await page.getByLabel("手机号").fill(phone);
      await page.getByLabel("邮箱").fill(email);
      await page.getByLabel("年龄").fill("18");
      await page.getByRole("button", { name: /立即注册/ }).click();

      await page.waitForURL(/\/welcome/, { timeout: 15_000 });
      await expect(page.getByText(/注册成功 — Hello World 立即开跑/)).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("signup-wizard")).toBeVisible();
    });

    await test.step("老张 3/7 - 关闭欢迎页 modal 并进入 Excel surface", async () => {
      if (await page.getByTestId("confirmation-modal").isVisible()) {
        await page.keyboard.press("Escape");
        await expect(page.getByTestId("confirmation-modal")).toBeHidden({
          timeout: 3_000,
        });
      }

      await expect(page.getByTestId("api-key-manager")).toBeVisible();
      await page.getByTestId("welcome-excel-upload-link").click();
      await expect(page).toHaveURL(/\/console\/excel$/);
      await expect(page.getByTestId("excel-drop-zone")).toBeVisible();
    });

    await test.step("老张 4/7 - 上传 Inventory workbook 并等待自然识别", async () => {
      await page.locator('input[type="file"]').setInputFiles({
        name: "inventory.xlsx",
        mimeType: XLSX_MIME,
        buffer: INVENTORY_BUFFER,
      });

      await expect(page.getByTestId("excel-received-card")).toBeVisible();
      await expect(page.getByTestId("excel-received-card")).toContainText(
        "已收到您的 Excel 文件",
      );
      await expect(page.getByTestId("excel-received-card")).toContainText(
        "本地解析",
      );

      const modal = page.getByTestId("confirmation-modal");
      await expect(modal).toBeVisible({ timeout: 10_000 });
      await expect(modal).toContainText(/系统判断/);
      await expect(modal).toContainText(/Inventory|库存预测/);
      await expect(page.getByTestId("detection-confidence")).toBeVisible();
      await expect(page.getByTestId("detection-override-select")).toBeVisible();
    });

    await test.step("老张 5/7 - 确认识别结果并进入库存预览", async () => {
      await page.getByRole("button", { name: "确认并继续" }).click();

      const preview = page.getByTestId("inventory-preview-card");
      await expect(preview).toBeVisible({ timeout: 10_000 });
      await expect(preview).toContainText(/库存预测/);
      await expect(preview).toContainText("SKU");
      await expect(preview).toContainText("历史行");
    });

    await test.step("老张 6/7 - 试跑并确认 demo/501 诚实状态", async () => {
      await page.getByTestId("inventory-submit-button").click();

      const demoCard = page.getByTestId("inventory-501-card");
      await expect(demoCard).toBeVisible({ timeout: 10_000 });
      await expect(demoCard).toContainText("M2-M3");
      await expect(demoCard).toContainText("库存预测引擎即将上线");
    });

    await test.step("老张 7/7 - 下载结果并解析 workbook", async () => {
      const downloadBtn = page.getByTestId("inventory-download-button");
      await expect(downloadBtn).toBeVisible();

      const [download] = await Promise.all([
        page.waitForEvent("download"),
        downloadBtn.click(),
      ]);

      expect(download.suggestedFilename()).toMatch(
        /^opticloud_inventory_\d{8}T\d{6}Z\.xlsx$/,
      );

      const outputPath = testInfo.outputPath(download.suggestedFilename());
      await download.saveAs(outputPath);

      const wb = XLSX.read(readFileSync(outputPath), { type: "buffer" });
      expect(wb.SheetNames).toEqual(
        expect.arrayContaining(["Results", "Chart Preview", "Summary"]),
      );
      expect(wb.SheetNames.some((name) => name.startsWith("输入 — "))).toBe(true);

      const results = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
        header: 1,
      });
      expect(results[0]).toEqual(
        expect.arrayContaining([
          "forecast_p10",
          "forecast_p50",
          "forecast_p90",
          "demo_marker",
        ]),
      );
      expect(results.length).toBeGreaterThanOrEqual(3);

      const summary = XLSX.utils.sheet_to_json<unknown[]>(
        wb.Sheets["Summary"],
        { header: 1 },
      );
      const summaryMap = new Map(summary.map((row) => [row[0], row[1]]));
      expect(summaryMap.get("status")).toBe("demo (M2-M3 待上线)");
      expect(summaryMap.get("source_filename")).toBe("inventory.xlsx");
      expect(summaryMap.get("source_total_rows")).toBe(6);
      expect(summaryMap.get("chart_preview_sheet")).toBe("Chart Preview");
      expect(summaryMap.get("generated_by")).toContain("/console/excel");

      const chartRows = XLSX.utils.sheet_to_json<unknown[]>(
        wb.Sheets["Chart Preview"],
        { header: 1 },
      );
      expect(chartRows.flat().map(String)).toContain("Inventory 预测带预览");
    });
  });
});
