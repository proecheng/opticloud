import { describe, expect, it } from "vitest";

import {
  CHAT_PARTIAL_UPLOAD_RECOVERY_ACTIONS,
  cancelChatCsvRecovery,
  parseChatCsvWithRecovery,
  replaceFailedChatCsvRows,
  retryAllChatCsvRecovery,
} from "./chat-file-context-recovery";

function buildCsv(rows = 1000, invalidDataRow?: number): string {
  const lines = ["sku,month,demand"];
  for (let index = 1; index <= rows; index += 1) {
    const sku = `SKU-${String((index % 30) + 1).padStart(2, "0")}`;
    const month = `2026-${String((index % 12) + 1).padStart(2, "0")}`;
    const demand = String(100 + index);
    lines.push(
      invalidDataRow === index ? `${sku},${month}` : `${sku},${month},${demand}`,
    );
  }
  return lines.join("\n");
}

function csvFile(name: string, content: string): File {
  return new File([content], name, { type: "text/csv" });
}

describe("parseChatCsvWithRecovery", () => {
  it("returns Chat file context metadata for structurally valid CSV without raw rows", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("demand.csv", buildCsv(3)),
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.context).toEqual({
      source: "parsed_browser_file_context_v1",
      kind: "csv",
      filename: "demand.csv",
      size_bytes: expect.any(Number),
      mime_type: "text/csv",
      row_count: 3,
      sheet_count: 0,
      sheets: [],
      top_level_keys: [],
      detected_fields: ["sku", "month", "demand"],
      summary: "csv rows=3 headers=sku, month, demand",
    });
    expect(JSON.stringify(result)).not.toContain("SKU-02");
    expect(JSON.stringify(result)).not.toContain("2026-02");
  });

  it("opens a bounded recovery state for the 847th data row with modal-ready actions", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("lina.csv", buildCsv(1000, 847)),
    );

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.reason).toBe("partial_invalid");
    expect(result.invalid_row_count).toBe(1);
    expect(result.invalid_rows).toHaveLength(1);
    expect(result.invalid_rows[0]).toMatchObject({
      row_number: 848,
      data_row_number: 847,
      field_path: "rows[847]",
      constraint: "row cell count must match header cell count",
      remediation_hint_key: "chat.csv.replace_failed_row",
    });
    expect(result.actions).toEqual(CHAT_PARTIAL_UPLOAD_RECOVERY_ACTIONS);
    expect(result.actions.map((action) => action.label)).toEqual([
      "仅替换失败行",
      "全部重试",
      "取消",
    ]);
    expect(JSON.stringify(result)).not.toContain("SKU-08,2026-08");
  });

  it("returns fresh recovery actions so caller mutation cannot pollute later results", async () => {
    const first = await parseChatCsvWithRecovery(csvFile("first.csv", buildCsv(5, 2)));
    expect(first.ok).toBe(false);
    if (first.ok) return;
    first.actions[0] = { action: "cancel", label: "mutated" };

    const second = await parseChatCsvWithRecovery(csvFile("second.csv", buildCsv(5, 2)));

    expect(second.ok).toBe(false);
    if (second.ok) return;
    expect(second.actions).toEqual(CHAT_PARTIAL_UPLOAD_RECOVERY_ACTIONS);
  });

  it("replaces only the failed row, revalidates the full dataset, and returns context", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("lina.csv", buildCsv(1000, 847)),
    );
    expect(result.ok).toBe(false);
    if (result.ok) return;

    const repaired = replaceFailedChatCsvRows(result.session, "SKU-08,2026-08,8470");

    expect(repaired.ok).toBe(true);
    if (!repaired.ok) return;
    expect(repaired.context.row_count).toBe(1000);
    expect(repaired.context.summary).toBe("csv rows=1000 headers=sku, month, demand");
    const serialized = JSON.stringify(repaired);
    expect(serialized).not.toContain("8470");
    expect(serialized).not.toContain("SKU-08");
  });

  it("fails closed when replacement row number does not match a failed source row", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("lina.csv", buildCsv(1000, 847)),
    );
    expect(result.ok).toBe(false);
    if (result.ok) return;

    const repaired = replaceFailedChatCsvRows(
      result.session,
      "row_number,sku,month,demand\n999,SKU-08,2026-08,8470",
    );

    expect(repaired.ok).toBe(false);
    if (repaired.ok) return;
    expect(repaired.reason).toBe("partial_invalid");
    expect(repaired.invalid_rows[0]?.field_path).toBe("replacement");
    expect(repaired.invalid_rows[0]?.constraint).toContain("source row");
    expect(JSON.stringify(repaired)).not.toContain("8470");
  });

  it("requires source row numbers when replacing multiple failed rows", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile(
        "multi.csv",
        [
          "sku,month,demand",
          "SKU-01,2026-01",
          "SKU-02,2026-02,20",
          "SKU-03,2026-03",
        ].join("\n"),
      ),
    );
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.invalid_row_count).toBe(2);

    const unordered = replaceFailedChatCsvRows(
      result.session,
      [
        "row_number,sku,month,demand",
        "4,SKU-03,2026-03,30",
        "2,SKU-01,2026-01,10",
      ].join("\n"),
    );

    expect(unordered.ok).toBe(true);
    if (!unordered.ok) return;
    expect(unordered.context.row_count).toBe(3);

    const withoutRowNumbers = replaceFailedChatCsvRows(
      result.session,
      ["SKU-01,2026-01,10", "SKU-03,2026-03,30"].join("\n"),
    );

    expect(withoutRowNumbers.ok).toBe(false);
    if (withoutRowNumbers.ok) return;
    expect(withoutRowNumbers.invalid_rows[0]?.constraint).toContain("source row number");
  });

  it("resets or cancels recovery without producing file context", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("lina.csv", buildCsv(1000, 847)),
    );
    expect(result.ok).toBe(false);
    if (result.ok) return;

    expect(retryAllChatCsvRecovery(result.session)).toEqual({
      ok: false,
      reason: "retry_all",
      context: null,
    });
    expect(cancelChatCsvRecovery(result.session)).toEqual({
      ok: false,
      reason: "canceled",
      context: null,
    });
  });

  it("caps public invalid-row details while preserving the total count", async () => {
    const lines = ["sku,month,demand"];
    for (let index = 1; index <= 25; index += 1) {
      lines.push(`SKU-${index},2026-01`);
    }

    const result = await parseChatCsvWithRecovery(
      csvFile("many.csv", lines.join("\n")),
    );

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.invalid_row_count).toBe(25);
    expect(result.invalid_rows).toHaveLength(20);
    expect(JSON.stringify(result)).not.toContain("SKU-25");
  });

  it("does not leak raw rows, cell values, or secret-like content through JSON serialization", async () => {
    const result = await parseChatCsvWithRecovery(
      csvFile("secret.csv", "sku,month,demand\nA,2026-01,10\nB,2026-02,sk-test-secret,extra"),
    );

    expect(result.ok).toBe(false);
    if (result.ok) return;
    const serialized = JSON.stringify(result).toLowerCase();
    expect(serialized).not.toContain("sk-test-secret");
    expect(serialized).not.toContain("2026-02");
    expect(serialized).not.toContain("b,");
    expect(serialized).not.toContain("extra");
  });
});
