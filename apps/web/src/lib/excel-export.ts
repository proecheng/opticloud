/** Excel result-workbook exporter — Story 3.E.6 (FR E11).
 *
 * Pure utility that takes the user's parsed source workbook + the
 * mapper-built payload (VRPTW / Schedule / Inventory) + a status flag
 * (real `solved` solution vs `demo` mock placeholder for the M2-M3 gap)
 * and returns a downloadable .xlsx Blob with three kinds of sheets:
 *
 *   1. "输入 — {original sheet name}" — echo of user's input (preserved)
 *   2. "Results" — per-task-type structured output (mock or real)
 *   3. "Summary" — key/value run metadata
 *
 * Implementation note: `xlsx` (SheetJS) is dynamic-imported inside
 * `buildResultWorkbook` so the ~600KB lib only loads when the user
 * clicks download — keeps the /console/excel initial bundle small
 * (per the design note in excel.ts:7-9 left by 3.E.2).
 */

import type { ExcelWorkbookSummary } from "./excel";
import type { InventoryPayload } from "./inventory-template";
import type { SchedulePayload } from "./schedule-template";
import type { VRPTWPayload } from "./vrptw-template";
import {
  buildVrptwChartArtifact,
  type VrptwChartContract,
  type VrptwChartRequest,
} from "./vrptw-chart";

export type ExportablePayload =
  | VRPTWPayload
  | SchedulePayload
  | InventoryPayload;

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
  /** Optional chart hook reserved for VRPTW route-backed previews. */
  chart?: VrptwChartRequest;
}

export interface ExportedWorkbook {
  blob: Blob;
  filename: string;
  sheetNames: string[];
}

const SHEET_NAME_CAP = 31; // Excel hard limit
const INPUT_SHEET_PREFIX = "输入 — ";

const DEMO_MARKER = "🚧 mock (M2-M3)";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

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
function truncateInputSheetName(rawName: string, used: Set<string>): string {
  const allowed = SHEET_NAME_CAP - INPUT_SHEET_PREFIX.length;
  const base = INPUT_SHEET_PREFIX + rawName.slice(0, allowed);
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  for (let i = 2; i < 1000; i++) {
    const suffix = ` (${i})`;
    const trimmedBase = rawName.slice(0, Math.max(0, allowed - suffix.length));
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
  chartMeta?: ChartSummaryMeta,
): unknown[][] {
  const objective =
    req.realResult?.objective !== undefined && req.realResult.objective !== null
      ? req.realResult.objective
      : "(demo)";
  const solveSeconds =
    req.realResult?.solveSeconds !== undefined
      ? req.realResult.solveSeconds
      : "(demo)";
  const rows: unknown[][] = [
    ["Key", "Value"],
    ["task_type", req.payload.task_type],
    ["status", req.status === "solved" ? "solved" : "demo (M2-M3 待上线)"],
    ["submitted_at", submittedAt],
    ["source_filename", req.sourceFilename ?? "(unknown)"],
    ["source_total_rows", source.totalRows],
    ["primary_count", primaryCount(req.payload)],
    ["secondary_count", secondaryCount(req.payload)],
    ["objective_value", objective],
    ["solve_seconds", solveSeconds],
    ["generated_by", "OptiCloud /console/excel (3.E.6)"],
    ["generated_at", generatedAt],
  ];
  if (chartMeta) {
    rows.push(
      ["chart_mode", chartMeta.mode],
      ["chart_source", chartMeta.source],
      ["chart_sheet_name", chartMeta.sheetName],
    );
  }
  return rows;
}

interface ChartSummaryMeta {
  mode: VrptwChartContract["mode"];
  source: VrptwChartContract["source"];
  sheetName: string;
}

async function buildSheetJsWorkbook(
  req: ExportRequest,
  submittedAt: string,
  generatedAt: string,
): Promise<ExportedWorkbook> {
  const XLSX = await import("xlsx");
  const wb = XLSX.utils.book_new();

  const usedNames = new Set<string>();
  const sheetNames: string[] = [];

  for (const s of req.source.sheets) {
    const sheetName = truncateInputSheetName(s.name || "sheet", usedNames);
    const ws = XLSX.utils.aoa_to_sheet(s.rows ?? []);
    XLSX.utils.book_append_sheet(wb, ws, sheetName);
    sheetNames.push(sheetName);
  }

  const resultsWs = XLSX.utils.aoa_to_sheet(buildResultsRows(req.payload));
  XLSX.utils.book_append_sheet(wb, resultsWs, "Results");
  sheetNames.push("Results");

  const summaryWs = XLSX.utils.aoa_to_sheet(
    buildSummaryRows(req, req.source, submittedAt, generatedAt),
  );
  XLSX.utils.book_append_sheet(wb, summaryWs, "Summary");
  sheetNames.push("Summary");

  const buf = XLSX.write(wb, {
    type: "array",
    bookType: "xlsx",
  }) as ArrayBuffer;
  const blob = new Blob([buf], { type: XLSX_MIME });

  const filename = `opticloud_${req.payload.task_type}_${utcStampForFilename(new Date(generatedAt))}.xlsx`;
  return { blob, filename, sheetNames };
}

async function buildVrptwWorkbook(
  req: ExportRequest & { payload: VRPTWPayload },
  submittedAt: string,
  generatedAt: string,
): Promise<ExportedWorkbook> {
  const { Workbook } = await import("exceljs");
  const workbook = new Workbook();
  const chartArtifact = await buildVrptwChartArtifact(req.payload, req.chart);

  const usedNames = new Set<string>();
  const sheetNames: string[] = [];

  for (const s of req.source.sheets) {
    const sheetName = truncateInputSheetName(s.name || "sheet", usedNames);
    const ws = workbook.addWorksheet(sheetName);
    ws.addRows(s.rows ?? []);
    sheetNames.push(sheetName);
  }

  const resultsSheet = workbook.addWorksheet("Results");
  resultsSheet.addRows(buildResultsRows(req.payload));
  sheetNames.push("Results");

  const summarySheet = workbook.addWorksheet("Summary");
  summarySheet.addRows(
    buildSummaryRows(req, req.source, submittedAt, generatedAt, {
      ...chartArtifact.contract,
      sheetName: chartArtifact.sheetName,
    }),
  );
  summarySheet.getColumn(1).width = 22;
  summarySheet.getColumn(2).width = 42;
  sheetNames.push("Summary");

  const chartSheet = workbook.addWorksheet(chartArtifact.sheetName);
  chartSheet.addRows(chartArtifact.sheetRows);
  chartSheet.getRow(1).height = 24;
  chartSheet.getRow(10).height = 10;
  chartSheet.getRow(26).height = 10;
  chartSheet.getColumn(1).width = 24;
  chartSheet.getColumn(2).width = 22;
  chartSheet.getColumn(3).width = 22;
  chartSheet.getColumn(4).width = 22;
  chartSheet.getColumn(5).width = 22;
  for (const image of chartArtifact.images) {
    const imageId = workbook.addImage({
      base64: image.base64,
      extension: image.extension,
    });
    chartSheet.addImage(imageId, {
      tl: image.position.tl,
      ext: image.position.ext,
    });
  }
  sheetNames.push(chartArtifact.sheetName);

  const buf = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buf], { type: XLSX_MIME });
  const filename = `opticloud_${req.payload.task_type}_${utcStampForFilename(
    new Date(generatedAt),
  )}.xlsx`;
  return { blob, filename, sheetNames };
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

  const now = new Date();
  const submittedAt = req.submittedAt ?? now.toISOString();
  const generatedAt = now.toISOString();
  if (req.payload.task_type === "vrptw") {
    return buildVrptwWorkbook(
      { ...req, payload: req.payload },
      submittedAt,
      generatedAt,
    );
  }
  return buildSheetJsWorkbook(req, submittedAt, generatedAt);
}
