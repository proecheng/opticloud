import { describe, expect, it } from "vitest";

import {
  buildPredictionRequest,
  parsePredictionCsv,
  replaceInvalidPredictionRows,
} from "./csv-prediction";

function buildCsv(rows = 1000, invalidDataRow?: number): string {
  const lines = ["商品编号,月份,销量"];
  for (let i = 1; i <= rows; i++) {
    const sku = `SKU-${String((i % 30) + 1).padStart(2, "0")}`;
    const month = `2026-${String((i % 12) + 1).padStart(2, "0")}`;
    const value = invalidDataRow === i ? "BAD_VALUE" : String(100 + i);
    lines.push(`${sku},${month},${value}`);
  }
  return lines.join("\n");
}

function csvFile(name: string, content: string): File {
  return new File([content], name, { type: "text/csv" });
}

describe("parsePredictionCsv", () => {
  it("parses mixed Chinese headers into a canonical prediction series", async () => {
    const result = await parsePredictionCsv(csvFile("sales.csv", buildCsv(12)));

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.records).toHaveLength(12);
    expect(result.summary.rowCount).toBe(12);
    expect(result.summary.skuCount).toBeGreaterThan(0);
    expect(result.series.length).toBe(12);
    expect(result.defaultFamily).toBe("chronos");
    expect(result.defaultHorizon).toBe(3);
  });

  it("keeps row identity for the 847th data row", async () => {
    const result = await parsePredictionCsv(csvFile("lina.csv", buildCsv(1000, 847)));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.summary.rowCount).toBe(1000);
    expect(result.invalidRows).toHaveLength(1);
    expect(result.invalidRows[0]).toMatchObject({
      dataRowNumber: 847,
      rowNumber: 848,
      fieldPath: "rows[847].value",
      constraint: "value must be a finite number",
      value: "BAD_VALUE",
    });
  });

  it("supports quoted cells and English aliases", async () => {
    const csv = [
      "SKU,date,sales",
      '"SKU,1",2026-01,10',
      '"SKU,1",2026-02,20',
      '"SKU,2",2026-01,5',
      '"SKU,2",2026-03,7',
    ].join("\r\n");
    const result = await parsePredictionCsv(csvFile("quoted.csv", csv));

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.records[0]?.sku).toBe("SKU,1");
    expect(result.series).toEqual([15, 20, 7]);
  });

  it("rejects files over 10000 data rows", async () => {
    const result = await parsePredictionCsv(csvFile("large.csv", buildCsv(10001)));

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.invalidRows[0]?.fieldPath).toBe("rows");
    expect(result.invalidRows[0]?.constraint).toContain("10000");
  });

  it("decodes GB18030 when the browser runtime supports it", async () => {
    const ascii = (text: string): number[] => [...new TextEncoder().encode(text)];
    const bytes = new Uint8Array([
      ...ascii("sku,date,sales\n"),
      0xb2,
      0xe2,
      0xca,
      0xd4,
      ...ascii(",2026-01,10\n"),
      0xb2,
      0xe2,
      0xca,
      0xd4,
      ...ascii(",2026-02,20\n"),
      0xb2,
      0xe2,
      0xca,
      0xd4,
      ...ascii(",2026-03,30\n"),
    ]);
    const file = new File([bytes], "gb18030.csv", { type: "text/csv" });
    const result = await parsePredictionCsv(file);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.summary.encoding).toBe("gb18030");
    expect(result.records[0]?.sku).toBe("测试");
  });
});

describe("replaceInvalidPredictionRows", () => {
  it("replaces only the invalid row and revalidates the full dataset", async () => {
    const invalid = await parsePredictionCsv(csvFile("lina.csv", buildCsv(1000, 847)));
    expect(invalid.ok).toBe(false);
    if (invalid.ok) return;

    const repaired = replaceInvalidPredictionRows(
      invalid,
      "SKU-08,2026-08,8470",
    );

    expect(repaired.ok).toBe(true);
    if (!repaired.ok) return;
    expect(repaired.records).toHaveLength(1000);
    expect(repaired.records.find((row) => row.dataRowNumber === 847)?.value).toBe(8470);

    const body = buildPredictionRequest(repaired, { family: "chronos", horizon: 6 });
    expect(body.family).toBe("chronos");
    expect(body.horizon).toBe(6);
    expect(body.data.length).toBe(12);
  });

  it("fails closed when replacement key does not match the invalid row", async () => {
    const invalid = await parsePredictionCsv(csvFile("lina.csv", buildCsv(1000, 847)));
    expect(invalid.ok).toBe(false);
    if (invalid.ok) return;

    const repaired = replaceInvalidPredictionRows(invalid, "OTHER,2026-08,8470");

    expect(repaired.ok).toBe(false);
    if (repaired.ok) return;
    expect(repaired.invalidRows[0]?.constraint).toContain("replacement row must match");
  });
});
