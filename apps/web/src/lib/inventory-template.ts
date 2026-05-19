/** Inventory prediction schema mapper — Story 3.E.5 (PMR6).
 *
 * Reads parsed Excel rows for SKU / 历史出货 / 季节性 sheets and builds an
 * OptiCloud inventory prediction payload. Pure function. Third occurrence of
 * the per-template mapper pattern; uses extracted helpers (excel-helpers.ts).
 *
 * Note: while semantically a *prediction* (Story 3.2 territory), v1 submits to
 * `/v1/optimizations/demo` for the 501 short-circuit — same as vrptw + schedule.
 * When `/v1/predictions` lands (M2-M3 backend), 3.E.5 FE swaps endpoint only.
 */

import type { ExcelWorkbookSummary } from "./excel";
import {
  findColumn,
  findSheet,
  toCellString,
  toNumber,
} from "./excel-helpers";

export interface InventorySKU {
  sku: string;
  name: string | null;
  category: string | null;
  initial_stock: number | null;
}

export interface InventoryHistoryRecord {
  sku: string;
  date: string;
  qty: number;
}

export interface InventorySeasonalityRecord {
  sku: string;
  season: string;
  multiplier: number;
}

export interface InventoryPayload {
  task_type: "inventory";
  skus: InventorySKU[];
  history: InventoryHistoryRecord[];
  seasonality: InventorySeasonalityRecord[];
  options?: { forecast_horizon_days?: number };
}

export interface InventoryErrorDetail {
  sheet: string;
  field?: string;
  message: string;
}

export type InventoryMappingResult =
  | {
      ok: true;
      payload: InventoryPayload;
      sku_count: number;
      history_count: number;
      seasonality_count: number;
      warnings: string[];
    }
  | {
      ok: false;
      errors: InventoryErrorDetail[];
    };

const SIGNALS = {
  skuSheet: ["sku", "商品", "产品"],
  historySheet: ["出货", "历史", "销量", "sales", "history"],
  seasonalitySheet: ["季节", "season"],
  skuId: ["sku", "商品编号", "编号", "id"],
  skuName: ["商品名", "名称", "name"],
  skuCategory: ["类别", "category", "type"],
  initialStock: ["期初库存", "库存", "stock", "initial"],
  histSku: ["sku", "商品编号", "编号", "id"],
  histDate: ["日期", "date"],
  histQty: ["销量", "数量", "qty", "quantity"],
  seasonSku: ["sku", "商品编号", "编号", "id"],
  seasonName: ["季节", "周期", "season", "period"],
  seasonMultiplier: ["系数", "倍数", "multiplier", "factor"],
};

export function buildInventoryPayload(
  summary: ExcelWorkbookSummary,
): InventoryMappingResult {
  const errors: InventoryErrorDetail[] = [];
  const warnings: string[] = [];

  const skuSheet = findSheet(summary, SIGNALS.skuSheet);
  const historySheet = findSheet(summary, SIGNALS.historySheet);
  const seasonSheet = findSheet(summary, SIGNALS.seasonalitySheet);

  if (!skuSheet) {
    errors.push({
      sheet: "SKU",
      message: "未找到 SKU sheet（期望包含 'sku' / '商品' / '产品' 字样）",
    });
  }
  if (!historySheet) {
    errors.push({
      sheet: "历史出货",
      message: "未找到历史出货 sheet（期望包含 '出货' / '历史' / 'sales' / 'history' 字样）",
    });
  }

  if (errors.length > 0 || !skuSheet || !historySheet) {
    return { ok: false, errors };
  }

  if (!skuSheet.rows || !historySheet.rows) {
    return {
      ok: false,
      errors: [
        {
          sheet: "(workbook)",
          message:
            "rows 未填充 — 请用 parseExcel(file, {includeRows: true}) 重新解析",
        },
      ],
    };
  }

  // SKU mapping
  const sHeaders = skuSheet.headers;
  const sIdIdx = findColumn(sHeaders, SIGNALS.skuId);
  const sNameIdx = findColumn(sHeaders, SIGNALS.skuName);
  const sCatIdx = findColumn(sHeaders, SIGNALS.skuCategory);
  const sStockIdx = findColumn(sHeaders, SIGNALS.initialStock);

  if (sIdIdx === -1)
    errors.push({
      sheet: skuSheet.name,
      field: "sku",
      message: "缺少 sku / 商品编号 / id 列",
    });

  // History mapping
  const hHeaders = historySheet.headers;
  const hSkuIdx = findColumn(hHeaders, SIGNALS.histSku);
  const hDateIdx = findColumn(hHeaders, SIGNALS.histDate);
  const hQtyIdx = findColumn(hHeaders, SIGNALS.histQty);

  if (hSkuIdx === -1)
    errors.push({
      sheet: historySheet.name,
      field: "sku",
      message: "缺少 sku 列",
    });
  if (hDateIdx === -1)
    errors.push({
      sheet: historySheet.name,
      field: "date",
      message: "缺少日期 / date 列",
    });
  if (hQtyIdx === -1)
    errors.push({
      sheet: historySheet.name,
      field: "qty",
      message: "缺少销量 / qty 列",
    });

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  // Build SKUs
  const skus: InventorySKU[] = [];
  let skippedSRows = 0;
  for (let i = 1; i < skuSheet.rows.length; i++) {
    const row = skuSheet.rows[i];
    if (!row || row.length === 0) {
      skippedSRows++;
      continue;
    }
    const rawId = row[sIdIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedSRows++;
      continue;
    }
    const sku = String(rawId).trim();
    const stock = sStockIdx !== -1 ? toNumber(row[sStockIdx]) : null;
    if (stock !== null && stock < 0) {
      errors.push({
        sheet: skuSheet.name,
        field: "initial_stock",
        message: `第 ${i + 1} 行 "${sku}" 期初库存无效 (${row[sStockIdx]})`,
      });
      continue;
    }
    skus.push({
      sku,
      name: sNameIdx !== -1 ? toCellString(row[sNameIdx]) : null,
      category: sCatIdx !== -1 ? toCellString(row[sCatIdx]) : null,
      initial_stock: stock,
    });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedSRows > 0) {
    warnings.push(`跳过 ${skippedSRows} 个空 SKU 行`);
  }
  if (skus.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: skuSheet.name, message: "SKU sheet 没有任何有效数据行" },
      ],
    };
  }

  const skuIds = new Set(skus.map((s) => s.sku));

  // Build history
  const history: InventoryHistoryRecord[] = [];
  let skippedHRows = 0;
  let unknownHistorySkus = 0;
  for (let i = 1; i < historySheet.rows.length; i++) {
    const row = historySheet.rows[i];
    if (!row || row.length === 0) {
      skippedHRows++;
      continue;
    }
    const rawId = row[hSkuIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedHRows++;
      continue;
    }
    const sku = String(rawId).trim();
    if (!skuIds.has(sku)) {
      unknownHistorySkus++;
      continue;
    }
    const date = toCellString(row[hDateIdx]);
    if (date === null) {
      errors.push({
        sheet: historySheet.name,
        field: "date",
        message: `第 ${i + 1} 行 "${sku}" 日期为空`,
      });
      continue;
    }
    const qty = toNumber(row[hQtyIdx]);
    if (qty === null || qty < 0) {
      errors.push({
        sheet: historySheet.name,
        field: "qty",
        message: `第 ${i + 1} 行 "${sku}" 销量无效 (${row[hQtyIdx]})`,
      });
      continue;
    }
    history.push({ sku, date, qty });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedHRows > 0) {
    warnings.push(`跳过 ${skippedHRows} 个空历史出货行`);
  }
  if (unknownHistorySkus > 0) {
    warnings.push(`历史出货有 ${unknownHistorySkus} 行 sku 未在 SKU sheet 中定义 — 已忽略`);
  }
  if (history.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: historySheet.name, message: "历史出货 sheet 没有任何有效数据行" },
      ],
    };
  }

  // Optional seasonality
  const seasonality: InventorySeasonalityRecord[] = [];
  if (!seasonSheet) {
    warnings.push("季节性 sheet 未找到 — 已默认无季节性约束");
  } else if (seasonSheet.rows && seasonSheet.rows.length > 1) {
    const pHeaders = seasonSheet.headers;
    const pSkuIdx = findColumn(pHeaders, SIGNALS.seasonSku);
    const pNameIdx = findColumn(pHeaders, SIGNALS.seasonName);
    const pMulIdx = findColumn(pHeaders, SIGNALS.seasonMultiplier);

    if (pSkuIdx === -1 || pNameIdx === -1 || pMulIdx === -1) {
      warnings.push("季节性 sheet 缺少必要列 (sku / 季节 / 系数) — 已忽略");
    } else {
      let unknownSeasonSkus = 0;
      for (let i = 1; i < seasonSheet.rows.length; i++) {
        const row = seasonSheet.rows[i];
        if (!row || row.length === 0) continue;
        const rawId = row[pSkuIdx];
        if (
          rawId === null ||
          rawId === undefined ||
          String(rawId).trim() === ""
        )
          continue;
        const sku = String(rawId).trim();
        if (!skuIds.has(sku)) {
          unknownSeasonSkus++;
          continue;
        }
        const season = toCellString(row[pNameIdx]);
        const multiplier = toNumber(row[pMulIdx]);
        if (season === null || multiplier === null || multiplier <= 0) {
          continue;
        }
        seasonality.push({ sku, season, multiplier });
      }
      if (unknownSeasonSkus > 0) {
        warnings.push(
          `季节性 sheet 有 ${unknownSeasonSkus} 行 sku 未在 SKU sheet 中定义 — 已忽略`,
        );
      }
    }
  }

  return {
    ok: true,
    payload: {
      task_type: "inventory",
      skus,
      history,
      seasonality,
    },
    sku_count: skus.length,
    history_count: history.length,
    seasonality_count: seasonality.length,
    warnings,
  };
}
