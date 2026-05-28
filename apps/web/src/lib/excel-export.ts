/** Excel result-workbook exporter — Story 3.E.6 + 3.E.7 (FR E11).
 *
 * Pure utility that takes the user's parsed source workbook + the
 * mapper-built payload (VRPTW / Schedule / Inventory) + a status flag
 * (real `solved` solution vs `demo` mock placeholder for the M2-M3 gap)
 * and returns a downloadable .xlsx Blob with four kinds of sheets:
 *
 *   1. "输入 — {original sheet name}" — echo of user's input (preserved)
 *   2. "Results" — per-task-type structured output (mock or real)
 *   3. "Chart Preview" — spreadsheet-native visual previews
 *   4. "Summary" — key/value run metadata
 *
 * Implementation note: `xlsx-js-style` is dynamic-imported inside
 * `buildResultWorkbook` so the writer only loads when the user clicks
 * download — keeps the /console/excel initial bundle small
 * (per the design note in excel.ts:7-9 left by 3.E.2).
 */

import type { ExcelWorkbookSummary } from "./excel";
import type { InventoryPayload } from "./inventory-template";
import type { SchedulePayload } from "./schedule-template";
import type { VRPTWPayload } from "./vrptw-template";

export type ExportablePayload = VRPTWPayload | SchedulePayload | InventoryPayload;

export type ExportResultStatus = "solved" | "demo";

export interface ExportRequest {
  source: ExcelWorkbookSummary;
  payload: ExportablePayload;
  status: ExportResultStatus;
  realResult?: {
    objective: number | null;
    solveSeconds: number;
    solution?: { x?: number[] } | null;
  };
  submittedAt?: string;
  /** Optional original filename — surfaced in Summary sheet only (NOT used in output filename). */
  sourceFilename?: string;
}

export interface ExportedWorkbook {
  blob: Blob;
  filename: string;
  sheetNames: string[];
}

const SHEET_NAME_CAP = 31; // Excel hard limit
const INPUT_SHEET_PREFIX = "输入 — ";
const CHART_PREVIEW_SHEET = "Chart Preview";

const DEMO_MARKER = "🚧 mock (M2-M3)";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

type StyledCell = {
  v: string | number | boolean | null;
  t?: "s" | "n" | "b" | "z";
  s?: Record<string, unknown>;
};

type SheetCell = string | number | boolean | null | StyledCell;

const STYLE = {
  title: {
    font: { bold: true, sz: 14, color: { rgb: "1F2937" } },
    fill: { fgColor: { rgb: "E0F2FE" } },
    alignment: { horizontal: "left", vertical: "center" },
  },
  subtitle: {
    font: { bold: true, color: { rgb: "374151" } },
    fill: { fgColor: { rgb: "F3F4F6" } },
  },
  header: {
    font: { bold: true, color: { rgb: "111827" } },
    fill: { fgColor: { rgb: "E5E7EB" } },
    border: {
      top: { style: "thin", color: { rgb: "CBD5E1" } },
      bottom: { style: "thin", color: { rgb: "CBD5E1" } },
      left: { style: "thin", color: { rgb: "CBD5E1" } },
      right: { style: "thin", color: { rgb: "CBD5E1" } },
    },
  },
  marker: {
    font: { bold: true, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "FDE68A" } },
    alignment: { horizontal: "center", vertical: "center" },
    border: {
      top: { style: "thin", color: { rgb: "D97706" } },
      bottom: { style: "thin", color: { rgb: "D97706" } },
      left: { style: "thin", color: { rgb: "D97706" } },
      right: { style: "thin", color: { rgb: "D97706" } },
    },
  },
  bar: {
    fill: { fgColor: { rgb: "BFDBFE" } },
    border: {
      top: { style: "thin", color: { rgb: "3B82F6" } },
      bottom: { style: "thin", color: { rgb: "3B82F6" } },
      left: { style: "thin", color: { rgb: "3B82F6" } },
      right: { style: "thin", color: { rgb: "3B82F6" } },
    },
  },
  forecastMid: { fill: { fgColor: { rgb: "93C5FD" } } },
  demo: { font: { color: { rgb: "B45309" }, bold: true } },
} satisfies Record<string, Record<string, unknown>>;

function styled(
  value: string | number | boolean | null,
  style: Record<string, unknown>,
): StyledCell {
  return { v: value, s: style };
}

function styledRow(values: Array<string | number | boolean | null>): SheetCell[] {
  return values.map((v) => styled(v, STYLE.header));
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function utcStampForFilename(d: Date): string {
  return (
    `${d.getUTCFullYear()}${pad2(d.getUTCMonth() + 1)}${pad2(d.getUTCDate())}` +
    `T${pad2(d.getUTCHours())}${pad2(d.getUTCMinutes())}${pad2(d.getUTCSeconds())}Z`
  );
}

/** Truncate a sheet name to fit Excel's 31-char cap when combined with the input prefix.
 * Appends "(2)", "(3)", ... when the truncated name collides with an earlier sheet. */
function truncateInputSheetName(
  rawName: string,
  used: Set<string>,
): string {
  const allowed = SHEET_NAME_CAP - INPUT_SHEET_PREFIX.length;
  const base = INPUT_SHEET_PREFIX + rawName.slice(0, allowed);
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  for (let i = 2; i < 1000; i++) {
    const suffix = ` (${i})`;
    const trimmedBase = rawName.slice(
      0,
      Math.max(0, allowed - suffix.length),
    );
    const candidate = `${INPUT_SHEET_PREFIX}${trimmedBase}${suffix}`;
    if (!used.has(candidate)) {
      used.add(candidate);
      return candidate;
    }
  }
  // Fallback (shouldn't happen for any realistic workbook)
  const fallback = `${INPUT_SHEET_PREFIX}sheet${used.size}`;
  used.add(fallback);
  return fallback;
}

function buildVrptwResultsRows(payload: VRPTWPayload): unknown[][] {
  const header = [
    "route_id",
    "vehicle_id",
    "stop_sequence",
    "customer_id",
    "arrival_time",
    "departure_time",
    "demand_served",
    "demo_marker",
  ];
  const rows: unknown[][] = [header];
  const vehicleCount = Math.max(1, payload.vehicles.length);
  payload.customers.forEach((c, i) => {
    const vehicle = payload.vehicles[i % vehicleCount];
    rows.push([
      `ROUTE-${pad2(Math.floor(i / Math.max(1, payload.customers.length / vehicleCount)) + 1)}`,
      vehicle?.id ?? "V-DEMO",
      (i % Math.max(1, payload.customers.length / vehicleCount)) + 1,
      c.id,
      c.time_window_start ?? "08:00",
      c.time_window_end ?? "17:00",
      c.demand,
      DEMO_MARKER,
    ]);
  });
  return rows;
}

function buildScheduleResultsRows(payload: SchedulePayload): unknown[][] {
  const header = [
    "task_id",
    "resource_id",
    "start_time",
    "end_time",
    "duration",
    "demo_marker",
  ];
  const rows: unknown[][] = [header];
  const resourceCount = Math.max(1, payload.resources.length);
  let cursor = 0;
  payload.tasks.forEach((t, i) => {
    const resource = payload.resources[i % resourceCount];
    const start = cursor;
    const end = start + t.duration;
    cursor = end;
    rows.push([
      t.id,
      resource?.id ?? "RES-DEMO",
      start,
      end,
      t.duration,
      DEMO_MARKER,
    ]);
  });
  return rows;
}

function buildInventoryResultsRows(payload: InventoryPayload): unknown[][] {
  const header = [
    "sku",
    "period",
    "forecast_p10",
    "forecast_p50",
    "forecast_p90",
    "demo_marker",
  ];
  const rows: unknown[][] = [header];

  // Compute mean qty per SKU for deterministic placeholder; falls back to a constant.
  const totalsBySku = new Map<string, { sum: number; n: number }>();
  for (const h of payload.history) {
    const prev = totalsBySku.get(h.sku) ?? { sum: 0, n: 0 };
    prev.sum += h.qty;
    prev.n += 1;
    totalsBySku.set(h.sku, prev);
  }
  for (const sku of payload.skus) {
    const stat = totalsBySku.get(sku.sku);
    const mean = stat && stat.n > 0 ? stat.sum / stat.n : 100;
    const p50 = Math.round(mean);
    rows.push([
      sku.sku,
      "2026-Q2",
      Math.max(0, Math.round(mean * 0.8)),
      p50,
      Math.round(mean * 1.2),
      DEMO_MARKER,
    ]);
  }
  return rows;
}

function buildResultsRows(payload: ExportablePayload): unknown[][] {
  switch (payload.task_type) {
    case "vrptw":
      return buildVrptwResultsRows(payload);
    case "schedule":
      return buildScheduleResultsRows(payload);
    case "inventory":
      return buildInventoryResultsRows(payload);
  }
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asString(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function emptyRow(): SheetCell[] {
  return [];
}

function demoBanner(status: ExportResultStatus): SheetCell[] {
  return status === "demo"
    ? [styled(DEMO_MARKER, STYLE.demo)]
    : [styled("solved", STYLE.subtitle)];
}

function normalizeToIndex(value: number, min: number, max: number, cap: number): number {
  if (cap <= 1) return 0;
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return Math.floor((cap - 1) / 2);
  const raw = Math.round(((value - min) / span) * (cap - 1));
  return Math.min(cap - 1, Math.max(0, raw));
}

function buildBarCells(
  start: number,
  end: number,
  min: number,
  max: number,
  width: number,
): SheetCell[] {
  const safeEnd = Math.max(start, end);
  const startIdx = normalizeToIndex(start, min, max, width);
  const endIdx = Math.max(startIdx, normalizeToIndex(safeEnd, min, max, width));
  return Array.from({ length: width }, (_, i) =>
    i >= startIdx && i <= endIdx ? styled(" ", STYLE.bar) : "",
  );
}

function buildVrptwScatterRows(payload: VRPTWPayload): SheetCell[][] {
  const width = 20;
  const height = 12;
  const customers = payload.customers;
  const lats = customers.map((c) => c.lat);
  const lngs = customers.map((c) => c.lng);
  const minLat = lats.length > 0 ? Math.min(...lats) : 0;
  const maxLat = lats.length > 0 ? Math.max(...lats) : 0;
  const minLng = lngs.length > 0 ? Math.min(...lngs) : 0;
  const maxLng = lngs.length > 0 ? Math.max(...lngs) : 0;
  const grid = Array.from({ length: height }, () =>
    Array.from({ length: width }, () => "" as SheetCell),
  );

  customers.forEach((customer, i) => {
    const x = normalizeToIndex(customer.lng, minLng, maxLng, width);
    const y = height - 1 - normalizeToIndex(customer.lat, minLat, maxLat, height);
    const prev = grid[y][x];
    const marker = String(i + 1);
    const prevValue =
      typeof prev === "object" && prev !== null && "v" in prev ? prev.v : prev;
    grid[y][x] = styled(
      prev ? `${asString(prevValue)}/${marker}` : marker,
      STYLE.marker,
    );
  });

  return [
    [styled("VRPTW 路线散点图", STYLE.title)],
    [
      `lat ${minLat.toFixed(4)}..${maxLat.toFixed(4)}`,
      `lng ${minLng.toFixed(4)}..${maxLng.toFixed(4)}`,
      `customers ${customers.length}`,
    ],
    ...grid,
    styledRow(["marker", "customer_id", "lat", "lng", "demand"]),
    ...customers.map((c, i) => [i + 1, c.id, c.lat, c.lng, c.demand]),
  ];
}

function buildVrptwChartPreviewRows(
  payload: VRPTWPayload,
  resultsRows: unknown[][],
  status: ExportResultStatus,
): SheetCell[][] {
  const rows: SheetCell[][] = [
    [styled("OptiCloud Chart Preview", STYLE.title)],
    demoBanner(status),
    emptyRow(),
    ...buildVrptwScatterRows(payload),
    emptyRow(),
    [styled("VRPTW 停靠顺序 / 甘特预览", STYLE.title)],
    styledRow([
      "route_id",
      "vehicle_id",
      "stop_sequence",
      "customer_id",
      "arrival_time",
      "departure_time",
      "demand_served",
      "timeline",
    ]),
  ];

  for (const r of resultsRows.slice(1)) {
    rows.push([
      asString(r[0]),
      asString(r[1]),
      asNumber(r[2]),
      asString(r[3]),
      asString(r[4]),
      asString(r[5]),
      asNumber(r[6]),
      styled("#".repeat(Math.max(1, Math.min(24, asNumber(r[2], 1)))), STYLE.bar),
    ]);
  }

  return rows;
}

function buildScheduleChartPreviewRows(
  resultsRows: unknown[][],
  status: ExportResultStatus,
): SheetCell[][] {
  const dataRows = resultsRows.slice(1);
  const starts = dataRows.map((r) => asNumber(r[2]));
  const ends = dataRows.map((r) => asNumber(r[3]));
  const min = Math.min(...starts, 0);
  const max = Math.max(...ends, 1);
  const width = 24;

  return [
    [styled("OptiCloud Chart Preview", STYLE.title)],
    demoBanner(status),
    emptyRow(),
    [styled("Schedule 资源甘特预览", STYLE.title)],
    styledRow([
      "task_id",
      "resource_id",
      "start_time",
      "end_time",
      "duration",
      "timeline",
      ...Array.from({ length: width }, (_, i) => i + 1),
    ]),
    ...dataRows.map((r) => [
      asString(r[0]),
      asString(r[1]),
      asNumber(r[2]),
      asNumber(r[3]),
      asNumber(r[4]),
      `${asString(r[0])}: ${asNumber(r[2])}-${asNumber(r[3])}`,
      ...buildBarCells(asNumber(r[2]), asNumber(r[3]), min, max, width),
    ]),
  ];
}

function buildInventoryChartPreviewRows(
  resultsRows: unknown[][],
  status: ExportResultStatus,
): SheetCell[][] {
  const dataRows = resultsRows.slice(1);
  const maxForecast = Math.max(
    1,
    ...dataRows.flatMap((r) => [asNumber(r[2]), asNumber(r[3]), asNumber(r[4])]),
  );

  return [
    [styled("OptiCloud Chart Preview", STYLE.title)],
    demoBanner(status),
    emptyRow(),
    [styled("Inventory 预测带预览", STYLE.title)],
    styledRow([
      "sku",
      "period",
      "forecast_p10",
      "forecast_p50",
      "forecast_p90",
      "band_preview",
    ]),
    ...dataRows.map((r) => {
      const p10 = Math.max(0, asNumber(r[2]));
      const p50 = Math.max(0, asNumber(r[3]));
      const p90 = Math.max(0, asNumber(r[4]));
      const low = Math.max(1, Math.round((p10 / maxForecast) * 10));
      const mid = Math.max(low, Math.round((p50 / maxForecast) * 10));
      const high = Math.max(mid, Math.round((p90 / maxForecast) * 10));
      return [
        asString(r[0]),
        asString(r[1]),
        p10,
        p50,
        p90,
        styled(
          `${".".repeat(low)}${"-".repeat(Math.max(1, mid - low))}${"=".repeat(
            Math.max(1, high - mid),
          )}`,
          STYLE.forecastMid,
        ),
      ];
    }),
  ];
}

function buildChartPreviewRows(
  payload: ExportablePayload,
  resultsRows: unknown[][],
  status: ExportResultStatus,
): SheetCell[][] {
  switch (payload.task_type) {
    case "vrptw":
      return buildVrptwChartPreviewRows(payload, resultsRows, status);
    case "schedule":
      return buildScheduleChartPreviewRows(resultsRows, status);
    case "inventory":
      return buildInventoryChartPreviewRows(resultsRows, status);
  }
}

function primaryCount(payload: ExportablePayload): number {
  switch (payload.task_type) {
    case "vrptw":
      return payload.customers.length;
    case "schedule":
      return payload.tasks.length;
    case "inventory":
      return payload.skus.length;
  }
}

function secondaryCount(payload: ExportablePayload): number {
  switch (payload.task_type) {
    case "vrptw":
      return payload.vehicles.length;
    case "schedule":
      return payload.resources.length;
    case "inventory":
      return payload.history.length;
  }
}

function buildSummaryRows(
  req: ExportRequest,
  source: ExcelWorkbookSummary,
  submittedAt: string,
  generatedAt: string,
): unknown[][] {
  const objective =
    req.realResult?.objective !== undefined && req.realResult.objective !== null
      ? req.realResult.objective
      : "(demo)";
  const solveSeconds =
    req.realResult?.solveSeconds !== undefined
      ? req.realResult.solveSeconds
      : "(demo)";
  return [
    ["Key", "Value"],
    ["task_type", req.payload.task_type],
    [
      "status",
      req.status === "solved" ? "solved" : "demo (M2-M3 待上线)",
    ],
    ["submitted_at", submittedAt],
    ["source_filename", req.sourceFilename ?? "(unknown)"],
    ["source_total_rows", source.totalRows],
    ["primary_count", primaryCount(req.payload)],
    ["secondary_count", secondaryCount(req.payload)],
    ["objective_value", objective],
    ["solve_seconds", solveSeconds],
    ["chart_preview_sheet", CHART_PREVIEW_SHEET],
    ["generated_by", "OptiCloud /console/excel (3.E.7)"],
    ["generated_at", generatedAt],
  ];
}

export async function buildResultWorkbook(
  req: ExportRequest,
): Promise<ExportedWorkbook> {
  // Contract guard: source sheets MUST carry rows (preview cards always pass
  // includeRows: true on the parseExcel call). Surface this loudly rather than
  // silently shipping an empty workbook.
  for (const s of req.source.sheets) {
    if (!s.rows) {
      throw new Error(
        `excel-export: source sheet "${s.name}" has no rows — caller must use parseExcel(file, {includeRows: true})`,
      );
    }
  }

  const XLSX = await import("xlsx-js-style");
  const wb = XLSX.utils.book_new();

  const usedNames = new Set<string>();
  const sheetNames: string[] = [];

  for (const s of req.source.sheets) {
    const sheetName = truncateInputSheetName(s.name || "sheet", usedNames);
    const ws = XLSX.utils.aoa_to_sheet(s.rows ?? []);
    XLSX.utils.book_append_sheet(wb, ws, sheetName);
    sheetNames.push(sheetName);
  }

  const resultsRows = buildResultsRows(req.payload);
  const resultsWs = XLSX.utils.aoa_to_sheet(resultsRows);
  XLSX.utils.book_append_sheet(wb, resultsWs, "Results");
  sheetNames.push("Results");

  const chartPreviewWs = XLSX.utils.aoa_to_sheet(
    buildChartPreviewRows(req.payload, resultsRows, req.status),
  );
  chartPreviewWs["!cols"] = [
    { wch: 18 },
    { wch: 16 },
    { wch: 12 },
    { wch: 12 },
    { wch: 12 },
    { wch: 28 },
  ];
  XLSX.utils.book_append_sheet(wb, chartPreviewWs, CHART_PREVIEW_SHEET);
  sheetNames.push(CHART_PREVIEW_SHEET);

  const now = new Date();
  const submittedAt = req.submittedAt ?? now.toISOString();
  const generatedAt = now.toISOString();
  const summaryWs = XLSX.utils.aoa_to_sheet(
    buildSummaryRows(req, req.source, submittedAt, generatedAt),
  );
  XLSX.utils.book_append_sheet(wb, summaryWs, "Summary");
  sheetNames.push("Summary");

  const buf = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
  const blob = new Blob([buf], { type: XLSX_MIME });

  const filename = `opticloud_${req.payload.task_type}_${utcStampForFilename(now)}.xlsx`;
  return { blob, filename, sheetNames };
}
