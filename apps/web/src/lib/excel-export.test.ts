/** Story 3.E.6/3.E.7 — excel-export.ts Vitest. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { Workbook } from "exceljs";
import * as XLSX from "xlsx";

import { buildResultWorkbook, type ExportRequest } from "./excel-export";
import type { ExcelWorkbookSummary } from "./excel";
import type { VRPTWPayload } from "./vrptw-template";
import type { SchedulePayload } from "./schedule-template";
import type { InventoryPayload } from "./inventory-template";

const PNG_1X1 =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lI3rWQAAAABJRU5ErkJggg==";

vi.mock("echarts", () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    on: vi.fn(),
    getDataURL: vi.fn(() => PNG_1X1),
    dispose: vi.fn(),
  })),
}));

const SRC_SHEET = {
  name: "Sheet1",
  headers: ["id", "value"],
  rowCount: 3,
  rows: [
    ["id", "value"],
    ["A", 1],
    ["B", 2],
  ],
};

function baseSource(): ExcelWorkbookSummary {
  return {
    sheets: [SRC_SHEET],
    totalRows: 2,
  };
}

const VRPTW: VRPTWPayload = {
  task_type: "vrptw",
  customers: [
    {
      id: "C1",
      lat: 1.0,
      lng: 2.0,
      demand: 10,
      time_window_start: "08:00",
      time_window_end: "10:00",
      service_minutes: 5,
    },
    {
      id: "C2",
      lat: 1.5,
      lng: 2.5,
      demand: 20,
      time_window_start: null,
      time_window_end: null,
      service_minutes: null,
    },
  ],
  vehicles: [{ id: "V1", capacity: 100 }],
};

const SCHEDULE: SchedulePayload = {
  task_type: "schedule",
  tasks: [
    {
      id: "T1",
      duration: 4,
      deadline: null,
      resource: null,
      earliest_start: null,
    },
    {
      id: "T2",
      duration: 3,
      deadline: null,
      resource: null,
      earliest_start: null,
    },
    {
      id: "T3",
      duration: 5,
      deadline: null,
      resource: null,
      earliest_start: null,
    },
  ],
  resources: [
    { id: "R1", capacity: 1, type: null },
    { id: "R2", capacity: 1, type: null },
  ],
  precedences: [],
};

const INVENTORY: InventoryPayload = {
  task_type: "inventory",
  skus: [
    { sku: "S1", name: null, category: null, initial_stock: null },
    { sku: "S2", name: null, category: null, initial_stock: null },
  ],
  history: [
    { sku: "S1", date: "2026-01-01", qty: 100 },
    { sku: "S1", date: "2026-02-01", qty: 120 },
    { sku: "S2", date: "2026-01-01", qty: 50 },
  ],
  seasonality: [],
};

async function readBack(blob: Blob): Promise<XLSX.WorkBook> {
  const buf = await blob.arrayBuffer();
  return XLSX.read(new Uint8Array(buf), { type: "array" });
}

async function readBackWithExcelJs(blob: Blob): Promise<Workbook> {
  const workbook = new Workbook();
  await workbook.xlsx.load((await blob.arrayBuffer()) as Buffer);
  return workbook;
}

function rowsToMap(rows: unknown[][]): Map<unknown, unknown> {
  return new Map(rows.map((row) => [row[0], row[1]]));
}

describe("buildResultWorkbook", () => {
  beforeEach(() => {
    const body = {
      appendChild: vi.fn(),
    } as unknown as HTMLElement;
    vi.stubGlobal("document", {
      body,
      createElement: vi.fn(() => ({
        style: {},
        remove: vi.fn(),
      })),
    });
    vi.stubGlobal("window", {
      setTimeout: (handler: TimerHandler) => setTimeout(handler, 0),
      clearTimeout,
    });
  });

  it("VRPTW demo: adds Chart Preview sheet with two embedded images and chart metadata", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: VRPTW,
      status: "demo",
    };
    const { blob, sheetNames } = await buildResultWorkbook(req);
    expect(sheetNames).toEqual([
      "输入 — Sheet1",
      "Results",
      "Summary",
      "Chart Preview",
    ]);

    const wb = await readBack(blob);
    expect(wb.SheetNames).toContain("Results");
    expect(wb.SheetNames).toContain("Summary");
    expect(wb.SheetNames).toContain("Chart Preview");

    const resultsRows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Results"],
      {
        header: 1,
      },
    );
    // header + 2 customers
    expect(resultsRows).toHaveLength(VRPTW.customers.length + 1);
    const lastRow = resultsRows[resultsRows.length - 1] as unknown[];
    expect(lastRow[lastRow.length - 1]).toBe("🚧 mock (M2-M3)");

    const summaryRows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Summary"],
      {
        header: 1,
      },
    );
    const summary = rowsToMap(summaryRows);
    expect(summary.get("chart_mode")).toBe("derived_preview");
    expect(summary.get("chart_source")).toBe("vrptw_payload");
    expect(summary.get("chart_sheet_name")).toBe("Chart Preview");

    const excelJsWorkbook = await readBackWithExcelJs(blob);
    const chartSheet = excelJsWorkbook.getWorksheet("Chart Preview");
    expect(chartSheet).toBeDefined();
    expect(chartSheet!.getImages()).toHaveLength(2);
    expect(excelJsWorkbook.model.media).toHaveLength(2);
  });

  it("Schedule demo: rows = task_count; resource assigned by modulo", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: SCHEDULE,
      status: "demo",
    };
    const { blob } = await buildResultWorkbook(req);
    const wb = await readBack(blob);
    expect(wb.SheetNames).toEqual(["输入 — Sheet1", "Results", "Summary"]);
    expect(wb.SheetNames).not.toContain("Chart Preview");
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
      header: 1,
    });
    expect(rows).toHaveLength(SCHEDULE.tasks.length + 1);
    // Task 0 → R1, Task 1 → R2, Task 2 → R1 (modulo 2)
    expect((rows[1] as unknown[])[1]).toBe("R1");
    expect((rows[2] as unknown[])[1]).toBe("R2");
    expect((rows[3] as unknown[])[1]).toBe("R1");
  });

  it("Inventory demo: rows = sku_count; forecast columns present", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: INVENTORY,
      status: "demo",
    };
    const { blob } = await buildResultWorkbook(req);
    const wb = await readBack(blob);
    expect(wb.SheetNames).toEqual(["输入 — Sheet1", "Results", "Summary"]);
    expect(wb.SheetNames).not.toContain("Chart Preview");
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
      header: 1,
    });
    expect(rows).toHaveLength(INVENTORY.skus.length + 1);
    const header = rows[0] as string[];
    expect(header).toContain("forecast_p10");
    expect(header).toContain("forecast_p50");
    expect(header).toContain("forecast_p90");
  });

  it("solved status: Summary.objective_value reflects realResult.objective", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: VRPTW,
      status: "solved",
      realResult: { objective: 42.5, solveSeconds: 1.23 },
    };
    const { blob } = await buildResultWorkbook(req);
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Summary"], {
      header: 1,
    });
    expect(wb.SheetNames).toContain("Chart Preview");
    const objRow = rows.find(
      (r) => Array.isArray(r) && (r as unknown[])[0] === "objective_value",
    ) as unknown[] | undefined;
    expect(objRow?.[1]).toBe(42.5);
    const statusRow = rows.find(
      (r) => Array.isArray(r) && (r as unknown[])[0] === "status",
    ) as unknown[] | undefined;
    expect(statusRow?.[1]).toBe("solved");
  });

  it("sheet name truncation: 50-char source name fits Excel 31-char cap with prefix", async () => {
    const longName = "Customer_Data_From_The_Big_System_2026_Export";
    const src: ExcelWorkbookSummary = {
      sheets: [{ ...SRC_SHEET, name: longName }],
      totalRows: 2,
    };
    const { sheetNames } = await buildResultWorkbook({
      source: src,
      payload: VRPTW,
      status: "demo",
    });
    const inputSheet = sheetNames.find((n) => n.startsWith("输入 — "));
    expect(inputSheet).toBeDefined();
    expect(inputSheet!.length).toBeLessThanOrEqual(31);
  });

  it("filename format matches opticloud_{taskType}_YYYYMMDDTHHmmssZ.xlsx", async () => {
    const { filename } = await buildResultWorkbook({
      source: baseSource(),
      payload: INVENTORY,
      status: "demo",
    });
    expect(filename).toMatch(/^opticloud_inventory_\d{8}T\d{6}Z\.xlsx$/);
  });

  it("throws when a source sheet has no rows (contract guard for includeRows: true)", async () => {
    const noRowsSource: ExcelWorkbookSummary = {
      sheets: [{ name: "Sheet1", headers: ["a"], rowCount: 1 }],
      totalRows: 0,
    };
    await expect(
      buildResultWorkbook({
        source: noRowsSource,
        payload: VRPTW,
        status: "demo",
      }),
    ).rejects.toThrow(/includeRows/);
  });
});
