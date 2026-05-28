/** Excel parse + task_type detect tests — Story 3.E.2 AC6. */

import { utils as xlsxUtils, write as xlsxWrite } from "xlsx";
import { describe, expect, it } from "vitest";

import { parseExcel } from "./excel";
import { detectTaskType } from "./task-type-detect";

interface SheetSpec {
  name: string;
  rows: (string | number | null)[][];
}

function buildXlsxFile(name: string, sheets: SheetSpec[]): File {
  const wb = xlsxUtils.book_new();
  for (const sheet of sheets) {
    const ws = xlsxUtils.aoa_to_sheet(sheet.rows);
    xlsxUtils.book_append_sheet(wb, ws, sheet.name);
  }
  const buf = xlsxWrite(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
  return new File([buf], name, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

describe("parseExcel", () => {
  it("returns sheet names + headers + rowCount + totalRows", async () => {
    const file = buildXlsxFile("simple.xlsx", [
      {
        name: "Sheet1",
        rows: [
          ["name", "value"],
          ["a", 1],
          ["b", 2],
          ["c", 3],
        ],
      },
    ]);

    const summary = await parseExcel(file);
    expect(summary.sheets).toHaveLength(1);
    expect(summary.sheets[0]?.name).toBe("Sheet1");
    expect(summary.sheets[0]?.headers).toEqual(["name", "value"]);
    expect(summary.sheets[0]?.rowCount).toBe(4);
    expect(summary.totalRows).toBe(3);
  });

  it("sums totalRows across multiple sheets, excluding headers", async () => {
    const file = buildXlsxFile("multi.xlsx", [
      { name: "A", rows: [["h"], [1], [2]] },
      { name: "B", rows: [["h"], [1], [2], [3], [4]] },
    ]);
    const summary = await parseExcel(file);
    expect(summary.totalRows).toBe(2 + 4);
  });
});

describe("detectTaskType", () => {
  it("detects VRPTW from 客户/车辆/时间窗 sheets", () => {
    const summary = {
      sheets: [
        { name: "客户", headers: ["客户名", "经度", "纬度", "需求"], rowCount: 50 },
        { name: "车辆", headers: ["编号", "容量"], rowCount: 5 },
        { name: "时间窗", headers: ["客户名", "开始", "结束"], rowCount: 50 },
      ],
      totalRows: 102,
    };
    const result = detectTaskType(summary);
    expect(result.taskType).toBe("vrptw");
    expect(result.confidence).toBeGreaterThanOrEqual(0.2);
    expect(result.confidence).toBeLessThanOrEqual(1);
    expect(result.reasoning).toContain("VRPTW");
  });

  it("detects schedule from 任务/资源/工序 sheets", () => {
    const summary = {
      sheets: [
        { name: "任务", headers: ["任务名", "工期", "截止"], rowCount: 30 },
        { name: "资源", headers: ["资源", "数量"], rowCount: 10 },
      ],
      totalRows: 38,
    };
    const result = detectTaskType(summary);
    expect(result.taskType).toBe("schedule");
    expect(result.reasoning).toContain("排班/调度");
  });

  it("detects inventory from 出货/SKU/季节 sheets", () => {
    const summary = {
      sheets: [
        { name: "历史出货", headers: ["日期", "SKU", "销量"], rowCount: 1000 },
        { name: "季节性", headers: ["SKU", "季节性"], rowCount: 100 },
      ],
      totalRows: 1098,
    };
    const result = detectTaskType(summary);
    expect(result.taskType).toBe("inventory");
    expect(result.reasoning).toContain("库存预测");
  });

  it("returns unknown with explanation when no signals match", () => {
    const summary = {
      sheets: [
        { name: "RandomSheet", headers: ["foo", "bar", "baz"], rowCount: 10 },
      ],
      totalRows: 9,
    };
    const result = detectTaskType(summary);
    expect(result.taskType).toBe("unknown");
    expect(result.confidence).toBe(0);
    expect(result.reasoning).toContain("未匹配");
  });

  it("confidence stays in [0.2, 1] for matched cases", () => {
    const tests = [
      {
        sheets: [{ name: "客户", headers: ["lat"], rowCount: 5 }],
        totalRows: 4,
      },
      {
        sheets: [
          { name: "客户", headers: ["lat", "lng", "demand"], rowCount: 5 },
          { name: "车辆", headers: ["编号"], rowCount: 3 },
        ],
        totalRows: 6,
      },
    ];
    for (const summary of tests) {
      const r = detectTaskType(summary);
      expect(r.confidence).toBeGreaterThanOrEqual(0.2);
      expect(r.confidence).toBeLessThanOrEqual(1);
    }
  });

  it("alternatives list excludes the winner and includes other matches", () => {
    const summary = {
      sheets: [
        { name: "客户", headers: ["客户名", "lat", "lng"], rowCount: 50 },
        { name: "任务", headers: ["任务名"], rowCount: 30 },
      ],
      totalRows: 78,
    };
    const result = detectTaskType(summary);
    expect(result.alternatives).not.toContain(result.taskType);
    expect(result.alternatives).toContain("schedule");
  });
});

describe("parseExcel error path", () => {
  it("throws when given a non-xlsx blob", async () => {
    const garbage = new File([new Uint8Array([1, 2, 3, 4])], "garbage.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    await expect(parseExcel(garbage)).rejects.toThrow();
  });
});
