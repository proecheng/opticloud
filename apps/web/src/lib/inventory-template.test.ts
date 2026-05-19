/** Inventory mapper tests — Story 3.E.5 AC5. */

import { describe, expect, it } from "vitest";

import type { ExcelWorkbookSummary } from "./excel";
import { buildInventoryPayload } from "./inventory-template";

function makeSummary(
  sheets: { name: string; headers: string[]; rows: unknown[][] }[],
): ExcelWorkbookSummary {
  return {
    sheets: sheets.map((s) => ({
      name: s.name,
      headers: s.headers,
      rowCount: s.rows.length,
      rows: s.rows,
    })),
    totalRows: sheets.reduce((sum, s) => sum + Math.max(0, s.rows.length - 1), 0),
  };
}

describe("buildInventoryPayload", () => {
  it("happy path: 3 sheets (SKU / 历史出货 / 季节性) → ok=true with counts", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku", "名称", "类别", "期初库存"],
        rows: [
          ["sku", "名称", "类别", "期初库存"],
          ["S1", "苹果", "水果", 100],
          ["S2", "香蕉", "水果", 50],
        ],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [
          ["sku", "日期", "销量"],
          ["S1", "2026-01-01", 10],
          ["S1", "2026-01-02", 15],
          ["S2", "2026-01-01", 8],
        ],
      },
      {
        name: "季节性",
        headers: ["sku", "季节", "系数"],
        rows: [
          ["sku", "季节", "系数"],
          ["S1", "Q1", 1.2],
          ["S2", "Q1", 0.8],
        ],
      },
    ]);

    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.sku_count).toBe(2);
      expect(result.history_count).toBe(3);
      expect(result.seasonality_count).toBe(2);
      expect(result.payload.task_type).toBe("inventory");
      expect(result.payload.skus[0]?.sku).toBe("S1");
      expect(result.payload.skus[0]?.name).toBe("苹果");
      expect(result.payload.skus[0]?.initial_stock).toBe(100);
      expect(result.payload.history[0]?.sku).toBe("S1");
      expect(result.payload.history[0]?.qty).toBe(10);
      expect(result.payload.seasonality[0]?.multiplier).toBe(1.2);
    }
  });

  it("missing SKU sheet → ok=false with error", () => {
    const summary = makeSummary([
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [["sku", "日期", "销量"], ["S1", "2026-01-01", 10]],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.sheet === "SKU")).toBe(true);
    }
  });

  it("missing 历史出货 sheet → ok=false with error", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku", "名称"],
        rows: [["sku", "名称"], ["S1", "苹果"]],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.sheet === "历史出货")).toBe(true);
    }
  });

  it("missing required column (qty) → ok=false with field-level error", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku"],
        rows: [["sku"], ["S1"]],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期"], // no qty
        rows: [["sku", "日期"], ["S1", "2026-01-01"]],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.field === "qty")).toBe(true);
    }
  });

  it("invalid qty (negative) → ok=false with row-level error", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku"],
        rows: [["sku"], ["S1"]],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [
          ["sku", "日期", "销量"],
          ["S1", "2026-01-01", -5], // negative qty
        ],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(
        result.errors.some(
          (e) => e.field === "qty" && e.message.includes("无效"),
        ),
      ).toBe(true);
    }
  });

  it("季节性 sheet absent → ok=true with warning + seasonality=[]", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku"],
        rows: [["sku"], ["S1"]],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [["sku", "日期", "销量"], ["S1", "2026-01-01", 10]],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.seasonality_count).toBe(0);
      expect(result.payload.seasonality).toEqual([]);
      expect(
        result.warnings.some((w) => w.includes("季节性") && w.includes("未找到")),
      ).toBe(true);
    }
  });

  it("history referencing unknown sku → row skipped with warning (does NOT fail)", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku"],
        rows: [["sku"], ["S1"]],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [
          ["sku", "日期", "销量"],
          ["S1", "2026-01-01", 10],
          ["S99", "2026-01-01", 5], // S99 not in SKU sheet
          ["S88", "2026-01-02", 3], // also unknown
        ],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.history_count).toBe(1); // only S1 row
      expect(
        result.warnings.some((w) => w.includes("2 行 sku 未在 SKU sheet")),
      ).toBe(true);
    }
  });

  it("empty SKU rows skipped with warning", () => {
    const summary = makeSummary([
      {
        name: "SKU",
        headers: ["sku"],
        rows: [
          ["sku"],
          ["S1"],
          [null],
          [""],
          ["S2"],
        ],
      },
      {
        name: "历史出货",
        headers: ["sku", "日期", "销量"],
        rows: [["sku", "日期", "销量"], ["S1", "2026-01-01", 10]],
      },
    ]);
    const result = buildInventoryPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.sku_count).toBe(2);
      expect(result.warnings.some((w) => w.includes("跳过 2 个空 SKU 行"))).toBe(
        true,
      );
    }
  });
});
