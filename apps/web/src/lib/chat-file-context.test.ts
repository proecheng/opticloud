import { utils as xlsxUtils, write as xlsxWrite } from "xlsx";
import { describe, expect, it } from "vitest";

import { parseChatFileContext } from "./chat-file-context";

function buildFile(name: string, text: string, type: string): File {
  return new File([text], name, { type });
}

function buildXlsxFile(name: string): File {
  const wb = xlsxUtils.book_new();
  const tasks = xlsxUtils.aoa_to_sheet([
    ["任务", "工期", "资源"],
    ["cut", 2, "A"],
    ["pack", 1, "B"],
  ]);
  const resources = xlsxUtils.aoa_to_sheet([
    ["资源", "数量"],
    ["A", 1],
  ]);
  xlsxUtils.book_append_sheet(wb, tasks, "任务");
  xlsxUtils.book_append_sheet(wb, resources, "资源");
  const buf = xlsxWrite(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
  return new File([buf], name, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

describe("parseChatFileContext", () => {
  it("parses CSV into bounded snake_case metadata without raw rows", async () => {
    const file = buildFile(
      "demand.csv",
      "sku,month,demand\nA,2026-01,10\nB,2026-02,20\n",
      "text/csv",
    );

    const context = await parseChatFileContext(file);

    expect(context).toEqual({
      source: "parsed_browser_file_context_v1",
      kind: "csv",
      filename: "demand.csv",
      size_bytes: file.size,
      mime_type: "text/csv",
      row_count: 2,
      sheet_count: 0,
      sheets: [],
      top_level_keys: [],
      detected_fields: ["sku", "month", "demand"],
      summary: "csv rows=2 headers=sku, month, demand",
    });
    expect(JSON.stringify(context)).not.toContain("2026-01");
    expect(JSON.stringify(context)).not.toContain("A,");
  });

  it("parses Excel by reusing bounded workbook summary metadata", async () => {
    const file = buildXlsxFile("schedule.xlsx");

    const context = await parseChatFileContext(file);

    expect(context.kind).toBe("excel");
    expect(context.filename).toBe("schedule.xlsx");
    expect(context.row_count).toBe(3);
    expect(context.sheet_count).toBe(2);
    expect(context.sheets).toEqual([
      { name: "任务", headers: ["任务", "工期", "资源"], row_count: 3 },
      { name: "资源", headers: ["资源", "数量"], row_count: 2 },
    ]);
    expect(context.detected_fields).toEqual(["任务", "工期", "资源", "数量"]);
  });

  it("parses JSON shape without raw values", async () => {
    const file = buildFile(
      "payload.json",
      JSON.stringify({
        customers: [{ name: "secret-customer", demand: 10 }],
        vehicles: [{ plate: "沪A12345" }],
      }),
      "application/json",
    );

    const context = await parseChatFileContext(file);

    expect(context.kind).toBe("json");
    expect(context.top_level_keys).toEqual(["customers", "vehicles"]);
    expect(context.detected_fields).toEqual(["customers", "vehicles"]);
    expect(context.summary).toBe("json object keys=customers, vehicles");
    expect(JSON.stringify(context)).not.toContain("secret-customer");
    expect(JSON.stringify(context)).not.toContain("沪A12345");
  });

  it("rejects files larger than 5MB", async () => {
    const file = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "large.csv", {
      type: "text/csv",
    });

    await expect(parseChatFileContext(file)).rejects.toMatchObject({
      code: "too_large",
      max_mb: "5",
    });
  });

  it("rejects unsupported file types and path-like names", async () => {
    await expect(
      parseChatFileContext(buildFile("notes.txt", "hello", "text/plain")),
    ).rejects.toMatchObject({ code: "unsupported_type" });

    await expect(
      parseChatFileContext(buildFile("notes.txt", "a,b\n1,2\n", "text/csv")),
    ).rejects.toMatchObject({ code: "unsupported_type" });

    await expect(
      parseChatFileContext(buildFile("demand.csv", "a,b\n1,2\n", "application/json")),
    ).rejects.toMatchObject({ code: "unsupported_type" });

    await expect(
      parseChatFileContext(buildFile("../secret.csv", "a,b\n1,2\n", "text/csv")),
    ).rejects.toMatchObject({ code: "invalid_filename" });
  });

  it("redacts secret-like headers from metadata", async () => {
    const context = await parseChatFileContext(
      buildFile("secrets.csv", "sku,api_key,demand\nA,sk-test-secret,10\n", "text/csv"),
    );

    const serialized = JSON.stringify(context).toLowerCase();
    expect(serialized).not.toContain("api_key");
    expect(serialized).not.toContain("sk-test-secret");
    expect(context.detected_fields).toEqual(["sku", "demand"]);
  });
});
