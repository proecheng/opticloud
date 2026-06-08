/**
 * Algorithms public catalog E2E — Story 0.13 AC4.
 *
 * 公开免鉴权浏览页 + tier filter + provider_url 链接.
 */

import type { Page } from "@playwright/test";

import { test, expect } from "../fixtures";

const CATALOG_FIXTURE = [
  catalogItem("highs-lp", "lp", "T1", "HiGHS 线性规划", "HiGHS Linear Programming"),
  catalogItem("arima-forecast", "forecast", "P1", "ARIMA 时间序列预测", "ARIMA forecasting"),
  catalogItem("ortools-cp-sat", "cp_sat", "T2", "OR-Tools CP-SAT", "OR-Tools CP-SAT"),
  catalogItem("chronos-forecast", "forecast", "P2", "Chronos 预测", "Chronos forecasting"),
  catalogItem("milp-basic", "milp", "T3", "MILP 基础求解", "MILP basic solver"),
  catalogItem("vrptw-routing", "vrptw", "T4", "VRPTW 路由", "VRPTW routing"),
  catalogItem("inventory-baseline", "inventory", "P3", "库存预测基线", "Inventory baseline"),
] as const;

function catalogItem(
  kAlgo: string,
  taskType: string,
  tier: string,
  descriptionZh: string,
  descriptionEn: string,
) {
  return {
    k_algo: kAlgo,
    task_type: taskType,
    tier,
    status: "v1",
    model_version: {
      provider_id: `${kAlgo}-provider`,
      kind: "open_source",
      version: "1.0.0",
      provider_url: `https://example.com/${kAlgo}`,
    },
    description_zh: descriptionZh,
    description_en: descriptionEn,
    examples: [
      {
        name: `${kAlgo} example`,
        input: { task_type: taskType },
        description: `${descriptionZh} 示例`,
      },
    ],
    supported_solvers: [kAlgo],
    citation: null,
    ip_attribution: {
      tier: "L3",
      label_zh: "L3 · License-Only",
      display_name_zh: `${kAlgo} provider`,
      summary_zh: "测试 fixture provider attribution。",
      visibility: "license_only",
      contract_anchor: "e2e-fixture",
    },
    provenance: null,
  };
}

async function mockCatalogApi(page: Page): Promise<void> {
  await page.route("**/v1/algorithms**", async (route) => {
    const corsHeaders = {
      "Access-Control-Allow-Headers": "Accept-Language, Content-Type",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Origin": "*",
    };
    const url = new URL(route.request().url());
    if (!url.pathname.endsWith("/v1/algorithms")) {
      await route.continue();
      return;
    }

    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: corsHeaders,
      });
      return;
    }

    const tierParam = url.searchParams.get("tier");
    const selectedTiers = new Set(
      (tierParam ?? "")
        .split(",")
        .map((tier) => tier.trim())
        .filter(Boolean),
    );
    const items =
      selectedTiers.size > 0
        ? CATALOG_FIXTURE.filter((item) => selectedTiers.has(item.tier))
        : CATALOG_FIXTURE;

    await route.fulfill({
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify(items),
    });
  });
}

async function gotoAlgorithms(page: Page, path = "/algorithms"): Promise<void> {
  await mockCatalogApi(page);
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "算法目录" })).toBeVisible();
}

async function waitForCatalogLoaded(page: Page): Promise<void> {
  await expect(page.getByTestId("algorithm-card").first()).toBeVisible({ timeout: 20_000 });
}

test.describe.configure({ mode: "serial" });

test.describe("Algorithms catalog (public)", () => {
  test("访客可看到已发布算法 + Provider 透明", async ({ page }) => {
    await gotoAlgorithms(page);

    // Story 2.8: public catalog excludes unaudited self-developed algorithms.
    const cards = page.getByTestId("algorithm-card");
    await waitForCatalogLoaded(page);
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
    await gotoAlgorithms(page);
    await waitForCatalogLoaded(page);
    await page.getByTestId("tier-chip-T1").click();

    const cards = page.getByTestId("algorithm-card");
    await expect(cards).toHaveCount(1, { timeout: 10_000 });
    await expect(cards.first()).toContainText("highs-lp");
  });

  test("点击 T1 + P1 chip 显示两个 SKU", async ({ page }) => {
    await gotoAlgorithms(page);
    await waitForCatalogLoaded(page);
    await page.getByTestId("tier-chip-T1").click();
    await page.getByTestId("tier-chip-P1").click();

    const cards = page.getByTestId("algorithm-card");
    await expect(cards).toHaveCount(2, { timeout: 10_000 });
    const allText = (await cards.allTextContents()).join(" ");
    expect(allText).toContain("highs-lp");
    expect(allText).toContain("arima-forecast");
  });

  test("URL ?tier=T1,P1 hydrates 初始 chip 选中状态", async ({ page }) => {
    await gotoAlgorithms(page, "/algorithms?tier=T1,P1");

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
