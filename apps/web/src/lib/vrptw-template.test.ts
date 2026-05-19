/** VRPTW mapper tests — Story 3.E.3 AC6. */

import { describe, expect, it } from "vitest";

import type { ExcelWorkbookSummary } from "./excel";
import { buildVrptwPayload } from "./vrptw-template";

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

describe("buildVrptwPayload", () => {
  it("happy path: 3 sheets complete → ok=true with counts", () => {
    const summary = makeSummary([
      {
        name: "客户",
        headers: ["客户名", "纬度", "经度", "需求"],
        rows: [
          ["客户名", "纬度", "经度", "需求"],
          ["A", 31.2, 121.1, 5],
          ["B", 31.3, 121.2, 8],
          ["C", 31.4, 121.3, 3],
        ],
      },
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [
          ["编号", "容量"],
          ["V1", 50],
          ["V2", 80],
        ],
      },
      {
        name: "时间窗",
        headers: ["客户名", "开始", "结束"],
        rows: [
          ["客户名", "开始", "结束"],
          ["A", "08:00", "12:00"],
          ["B", "10:00", "14:00"],
        ],
      },
    ]);

    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.customer_count).toBe(3);
      expect(result.vehicle_count).toBe(2);
      expect(result.payload.task_type).toBe("vrptw");
      expect(result.payload.customers[0]?.id).toBe("A");
      expect(result.payload.customers[0]?.time_window_start).toBe("08:00");
      // C has no time window — should still be in payload
      const cust_c = result.payload.customers.find((c) => c.id === "C");
      expect(cust_c?.time_window_start).toBeNull();
      // Warning about C missing time window
      expect(result.warnings.some((w) => w.includes("没有时间窗"))).toBe(true);
    }
  });

  it("missing customer sheet → ok=false with error", () => {
    const summary = makeSummary([
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["V1", 50]],
      },
    ]);
    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.sheet === "客户")).toBe(true);
    }
  });

  it("missing required column (lat) → ok=false with field-level error", () => {
    const summary = makeSummary([
      {
        name: "客户",
        headers: ["客户名", "经度", "需求"], // no lat
        rows: [["客户名", "经度", "需求"], ["A", 121.1, 5]],
      },
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["V1", 50]],
      },
    ]);
    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.field === "lat")).toBe(true);
    }
  });

  it("invalid lat (out of range) → ok=false with row-level error", () => {
    const summary = makeSummary([
      {
        name: "客户",
        headers: ["客户名", "纬度", "经度", "需求"],
        rows: [
          ["客户名", "纬度", "经度", "需求"],
          ["A", 999, 121.1, 5], // lat way out of range
        ],
      },
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["V1", 50]],
      },
    ]);
    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(
        result.errors.some(
          (e) => e.field === "lat" && e.message.includes("无效"),
        ),
      ).toBe(true);
    }
  });

  it("time-window sheet absent → ok=true; customers default to null windows", () => {
    const summary = makeSummary([
      {
        name: "客户",
        headers: ["客户名", "纬度", "经度", "需求"],
        rows: [
          ["客户名", "纬度", "经度", "需求"],
          ["A", 31.2, 121.1, 5],
        ],
      },
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["V1", 50]],
      },
    ]);
    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.payload.customers[0]?.time_window_start).toBeNull();
      expect(result.payload.customers[0]?.time_window_end).toBeNull();
    }
  });

  it("empty customer rows skipped with warning", () => {
    const summary = makeSummary([
      {
        name: "客户",
        headers: ["客户名", "纬度", "经度", "需求"],
        rows: [
          ["客户名", "纬度", "经度", "需求"],
          ["A", 31.2, 121.1, 5],
          [null, null, null, null],
          ["", "", "", ""],
          ["B", 31.3, 121.2, 7],
        ],
      },
      {
        name: "车辆",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["V1", 50]],
      },
    ]);
    const result = buildVrptwPayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.customer_count).toBe(2);
      expect(result.warnings.some((w) => w.includes("跳过 2 个空客户行"))).toBe(true);
    }
  });
});
