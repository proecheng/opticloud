/** Schedule mapper tests — Story 3.E.4 AC5. */

import { describe, expect, it } from "vitest";

import type { ExcelWorkbookSummary } from "./excel";
import { buildSchedulePayload } from "./schedule-template";

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

describe("buildSchedulePayload", () => {
  it("happy path: 3 sheets complete → ok=true with counts + precedences", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期", "截止", "资源"],
        rows: [
          ["任务名", "工期", "截止", "资源"],
          ["T1", 4, "2026-06-01", "R1"],
          ["T2", 2, "2026-06-02", "R1"],
          ["T3", 6, "2026-06-03", "R2"],
        ],
      },
      {
        name: "资源",
        headers: ["编号", "容量", "类型"],
        rows: [
          ["编号", "容量", "类型"],
          ["R1", 2, "机器"],
          ["R2", 1, "人工"],
        ],
      },
      {
        name: "工序",
        headers: ["前驱", "后继"],
        rows: [
          ["前驱", "后继"],
          ["T1", "T2"],
          ["T2", "T3"],
        ],
      },
    ]);

    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.task_count).toBe(3);
      expect(result.resource_count).toBe(2);
      expect(result.precedence_count).toBe(2);
      expect(result.payload.task_type).toBe("schedule");
      expect(result.payload.tasks[0]?.id).toBe("T1");
      expect(result.payload.tasks[0]?.duration).toBe(4);
      expect(result.payload.tasks[0]?.resource).toBe("R1");
      expect(result.payload.resources[0]?.type).toBe("机器");
      expect(result.payload.precedences).toEqual([
        { predecessor: "T1", successor: "T2" },
        { predecessor: "T2", successor: "T3" },
      ]);
    }
  });

  it("missing 任务 sheet → ok=false with error", () => {
    const summary = makeSummary([
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.sheet === "任务")).toBe(true);
    }
  });

  it("missing 资源 sheet → ok=false with error", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期"],
        rows: [["任务名", "工期"], ["T1", 4]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.sheet === "资源")).toBe(true);
    }
  });

  it("missing required column (duration) → ok=false with field-level error", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "截止"], // no duration
        rows: [["任务名", "截止"], ["T1", "2026-06-01"]],
      },
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.some((e) => e.field === "duration")).toBe(true);
    }
  });

  it("invalid duration (<= 0) → ok=false with row-level error", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期"],
        rows: [
          ["任务名", "工期"],
          ["T1", 0], // invalid: must be > 0
        ],
      },
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(
        result.errors.some(
          (e) => e.field === "duration" && e.message.includes("无效"),
        ),
      ).toBe(true);
    }
  });

  it("工序 sheet absent → ok=true with warning + precedences=[]", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期"],
        rows: [
          ["任务名", "工期"],
          ["T1", 4],
          ["T2", 2],
        ],
      },
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.precedence_count).toBe(0);
      expect(result.payload.precedences).toEqual([]);
      expect(
        result.warnings.some((w) => w.includes("工序") && w.includes("未找到")),
      ).toBe(true);
    }
  });

  it("precedence referencing unknown task id → warning + skipped", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期"],
        rows: [
          ["任务名", "工期"],
          ["T1", 4],
          ["T2", 2],
        ],
      },
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
      {
        name: "工序",
        headers: ["前驱", "后继"],
        rows: [
          ["前驱", "后继"],
          ["T1", "T2"],
          ["T1", "T999"], // T999 doesn't exist
          ["TX", "T2"], // TX doesn't exist
        ],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.precedence_count).toBe(1); // only T1→T2 valid
      expect(
        result.warnings.some((w) => w.includes("2 行引用了未知任务 id")),
      ).toBe(true);
    }
  });

  it("empty task rows skipped with warning", () => {
    const summary = makeSummary([
      {
        name: "任务",
        headers: ["任务名", "工期"],
        rows: [
          ["任务名", "工期"],
          ["T1", 4],
          [null, null],
          ["", ""],
          ["T2", 6],
        ],
      },
      {
        name: "资源",
        headers: ["编号", "容量"],
        rows: [["编号", "容量"], ["R1", 2]],
      },
    ]);
    const result = buildSchedulePayload(summary);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.task_count).toBe(2);
      expect(result.warnings.some((w) => w.includes("跳过 2 个空任务行"))).toBe(
        true,
      );
    }
  });
});
