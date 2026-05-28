/** Story 3.E.6 + 3.E.7 — excel-export.ts Vitest. */

import { describe, expect, it } from "vitest";
import * as XLSX from "xlsx";

import { buildResultWorkbook, type ExportRequest } from "./excel-export";
import type { ExcelWorkbookSummary } from "./excel";
import type { VRPTWPayload } from "./vrptw-template";
import type { SchedulePayload } from "./schedule-template";
import type { InventoryPayload } from "./inventory-template";

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

describe("buildResultWorkbook", () => {
  it("VRPTW demo: input + Results + Summary sheets; rows = customer_count; demo_marker present", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: VRPTW,
      status: "demo",
    };
    const { blob, sheetNames } = await buildResultWorkbook(req);
    expect(sheetNames).toEqual([
      "输入 — Sheet1",
      "Results",
      "Chart Preview",
      "Summary",
    ]);

    const wb = await readBack(blob);
    expect(wb.SheetNames).toContain("Results");
    expect(wb.SheetNames).toContain("Chart Preview");
    expect(wb.SheetNames).toContain("Summary");

    const resultsRows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
      header: 1,
    });
    // header + 2 customers
    expect(resultsRows).toHaveLength(VRPTW.customers.length + 1);
    const lastRow = resultsRows[resultsRows.length - 1] as unknown[];
    expect(lastRow[lastRow.length - 1]).toBe("🚧 mock (M2-M3)");
  });

  it("VRPTW chart preview: route scatter and gantt sections survive round-trip", async () => {
    const { blob } = await buildResultWorkbook({
      source: baseSource(),
      payload: VRPTW,
      status: "demo",
    });
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Chart Preview"],
      { header: 1 },
    );
    const flattened = rows.flat().map(String);
    expect(flattened).toContain("VRPTW 路线散点图");
    expect(flattened).toContain("VRPTW 停靠顺序 / 甘特预览");
    expect(flattened).toContain("🚧 mock (M2-M3)");
    expect(flattened).toContain("C1");
    expect(flattened).toContain("C2");
  });

  it("VRPTW chart preview: scatter scaling uses customer coordinate bounds", async () => {
    const spreadPayload: VRPTWPayload = {
      ...VRPTW,
      customers: [
        { ...VRPTW.customers[0], lat: 31.2, lng: 121.1 },
        { ...VRPTW.customers[1], lat: 31.4, lng: 121.3 },
      ],
    };
    const { blob } = await buildResultWorkbook({
      source: baseSource(),
      payload: spreadPayload,
      status: "demo",
    });
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Chart Preview"],
      { header: 1 },
    );
    const flattened = rows.flat().map(String);
    expect(flattened).toContain("lat 31.2000..31.4000");
    expect(flattened).toContain("lng 121.1000..121.3000");
  });

  it("Schedule demo: rows = task_count; resource assigned by modulo", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: SCHEDULE,
      status: "demo",
    };
    const { blob } = await buildResultWorkbook(req);
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
      header: 1,
    });
    expect(rows).toHaveLength(SCHEDULE.tasks.length + 1);
    // Task 0 → R1, Task 1 → R2, Task 2 → R1 (modulo 2)
    expect((rows[1] as unknown[])[1]).toBe("R1");
    expect((rows[2] as unknown[])[1]).toBe("R2");
    expect((rows[3] as unknown[])[1]).toBe("R1");

    const chartRows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Chart Preview"],
      { header: 1 },
    );
    const flattened = chartRows.flat().map(String);
    expect(flattened).toContain("Schedule 资源甘特预览");
    expect(flattened).toContain("T1");
    expect(flattened).toContain("T2");
    expect(flattened).toContain("T3");
  });

  it("Inventory demo: rows = sku_count; forecast columns present", async () => {
    const req: ExportRequest = {
      source: baseSource(),
      payload: INVENTORY,
      status: "demo",
    };
    const { blob } = await buildResultWorkbook(req);
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets["Results"], {
      header: 1,
    });
    expect(rows).toHaveLength(INVENTORY.skus.length + 1);
    const header = rows[0] as string[];
    expect(header).toContain("forecast_p10");
    expect(header).toContain("forecast_p50");
    expect(header).toContain("forecast_p90");

    const chartRows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Chart Preview"],
      { header: 1 },
    );
    const flattened = chartRows.flat().map(String);
    expect(flattened).toContain("Inventory 预测带预览");
    expect(flattened).toContain("forecast_p10");
    expect(flattened).toContain("forecast_p50");
    expect(flattened).toContain("forecast_p90");
    expect(flattened).toContain("S1");
    expect(flattened).toContain("S2");
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
    const objRow = rows.find(
      (r) => Array.isArray(r) && (r as unknown[])[0] === "objective_value",
    ) as unknown[] | undefined;
    expect(objRow?.[1]).toBe(42.5);
    const statusRow = rows.find(
      (r) => Array.isArray(r) && (r as unknown[])[0] === "status",
    ) as unknown[] | undefined;
    expect(statusRow?.[1]).toBe("solved");
    const chartRow = rows.find(
      (r) => Array.isArray(r) && (r as unknown[])[0] === "chart_preview_sheet",
    ) as unknown[] | undefined;
    expect(chartRow?.[1]).toBe("Chart Preview");
  });

  it("VRPTW chart preview: degenerate coordinates still produce nonblank scatter", async () => {
    const sameCoordinatePayload: VRPTWPayload = {
      ...VRPTW,
      customers: VRPTW.customers.map((c) => ({ ...c, lat: 31.2, lng: 121.1 })),
    };
    const { blob } = await buildResultWorkbook({
      source: baseSource(),
      payload: sameCoordinatePayload,
      status: "demo",
    });
    const wb = await readBack(blob);
    const rows = XLSX.utils.sheet_to_json<unknown[]>(
      wb.Sheets["Chart Preview"],
      { header: 1 },
    );
    const flattened = rows.flat().map(String);
    expect(flattened).toContain("VRPTW 路线散点图");
    expect(flattened.some((cell) => cell.includes("1/2"))).toBe(true);
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
