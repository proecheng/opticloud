/** Shared helpers for per-template mappers — Story 3.E.5.
 *
 * Extracted from vrptw-template.ts + schedule-template.ts when the inventory
 * mapper became the third occurrence (rule-of-three). Pure functions, no IO.
 */

import type { ExcelSheetSummary, ExcelWorkbookSummary } from "./excel";

/** Case-insensitive substring match against sheet names. Returns first match, or null. */
export function findSheet(
  summary: ExcelWorkbookSummary,
  tokens: string[],
): ExcelSheetSummary | null {
  const lowered = tokens.map((t) => t.toLowerCase());
  return (
    summary.sheets.find((s) =>
      lowered.some((t) => s.name.toLowerCase().includes(t)),
    ) ?? null
  );
}

/** Case-insensitive substring match against header strings. Returns first matching column index, or -1. */
export function findColumn(headers: string[], tokens: string[]): number {
  const loweredHeaders = headers.map((h) => h.toLowerCase());
  for (const t of tokens) {
    const tLower = t.toLowerCase();
    const idx = loweredHeaders.findIndex((h) => h.includes(tLower));
    if (idx !== -1) return idx;
  }
  return -1;
}

/** Parse a cell into a finite number, or null when blank/non-numeric. */
export function toNumber(cell: unknown): number | null {
  if (cell === null || cell === undefined || cell === "") return null;
  const n = typeof cell === "number" ? cell : Number(String(cell).trim());
  return Number.isFinite(n) ? n : null;
}

/** Parse a cell into a trimmed non-empty string, or null. */
export function toCellString(cell: unknown): string | null {
  if (cell === null || cell === undefined) return null;
  const s = String(cell).trim();
  return s === "" ? null : s;
}
