/**
 * Story 3.11 — Lina CSV recovery vertical slice.
 *
 * Browser-only CSV parse: 1000 rows → row 847 invalid → replace failed row
 * → submit existing /v1/predictions contract → render P10/P50/P90.
 */

import { expect, test } from "../fixtures";

function buildCsv(rows = 1000, invalidDataRow?: number): string {
  const lines = ["商品编号,月份,销量"];
  for (let i = 1; i <= rows; i++) {
    const sku = `SKU-${String((i % 30) + 1).padStart(2, "0")}`;
    const month = `2026-${String((i % 12) + 1).padStart(2, "0")}`;
    const value = invalidDataRow === i ? "BAD_VALUE" : String(100 + i);
    lines.push(`${sku},${month},${value}`);
  }
  return lines.join("\n");
}

test.describe("Lina CSV prediction recovery", () => {
  test("repairs row 847 and renders prediction quantiles", async ({ page }) => {
    let postedBody: Record<string, unknown> | null = null;

    await page.route("**/v1/predictions", async (route) => {
      postedBody = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          prediction_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
          status: "completed",
          family: "chronos",
          horizon: 3,
          prediction: {
            p10: [10, 11, 12],
            p50: [12, 13, 14],
            p90: [14, 15, 16],
          },
          drift_score: 0.12,
          disclaimer: {
            zh: "本预测仅供参考",
            en: "This forecast is for reference only",
            bilingual: "本预测仅供参考 / This forecast is for reference only",
          },
          model_version: {
            provider_id: "chronos",
            kind: "open_source",
            version: "mock-v1",
            provider_url: "https://example.com/chronos",
          },
          predict_seconds: 0.03,
          created_at: "2026-05-28T01:00:00Z",
          completed_at: "2026-05-28T01:00:01Z",
        }),
      });
    });

    await page.goto("/console/predictions");
    await page.locator('input[type="file"]').setInputFiles({
      name: "lina.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(buildCsv(1000, 847), "utf8"),
    });

    const invalid = page.getByTestId("csv-invalid-card");
    await expect(invalid).toBeVisible({ timeout: 10_000 });
    await expect(invalid).toContainText("rows[847].value");
    await expect(invalid).toContainText("文件第 848 行");
    await expect(page.getByTestId("confirmation-modal")).toBeVisible();

    await page.getByLabel("替换行 CSV").fill("SKU-08,2026-08,8470");
    await page.getByRole("button", { name: "仅替换失败行" }).click();

    await expect(page.getByTestId("csv-ready-card")).toBeVisible();
    await expect(page.getByTestId("csv-ready-card")).toContainText("1,000");
    await page.getByLabel("API key").fill("sk-test");
    await page.getByTestId("prediction-submit").click();

    const result = page.getByTestId("prediction-result");
    await expect(result).toBeVisible({ timeout: 10_000 });
    await expect(result).toContainText("P10");
    await expect(result).toContainText("P50");
    await expect(result).toContainText("P90");
    await expect(result).toContainText("本预测仅供参考");
    expect(postedBody).toMatchObject({
      family: "chronos",
      horizon: 3,
    });
    expect(postedBody?.data).toHaveLength(12);
    expect(JSON.stringify(postedBody)).not.toContain("BAD_VALUE");
    expect(JSON.stringify(postedBody)).not.toContain("商品编号");
  });
});
