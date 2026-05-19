/** Excel workbook parser — Story 3.E.2 (browser-side, privacy-preserving).
 *
 * Uses `read-excel-file` (~50 KB gzipped) to extract sheet names + first-row
 * headers + row counts from a user-dropped .xlsx. Returns a small structured
 * summary that `task-type-detect.ts` consumes; never sends bytes to a backend.
 *
 * If we ever need WRITE (download path 3.E.6) we'll add `xlsx` (SheetJS) on
 * the download route only — keeps this landing-page bundle small.
 */

import readXlsxFile from "read-excel-file/browser";

export interface ExcelSheetSummary {
  name: string;
  /** First non-empty row, stringified (cells may be number / date / null). */
  headers: string[];
  /** Total rows in this sheet, including the header row. */
  rowCount: number;
  /** Story 3.E.3 — full rows (including header row at index 0), only present
   * when `parseExcel(file, {includeRows: true})` was called. */
  rows?: unknown[][];
}

export interface ExcelWorkbookSummary {
  sheets: ExcelSheetSummary[];
  /** Sum across sheets, EXCLUDING header rows (FR E11 50K-row cap is "data rows"). */
  totalRows: number;
}

export interface ParseExcelOptions {
  /** Story 3.E.3 — when true, ExcelSheetSummary.rows is populated. Default false. */
  includeRows?: boolean;
}

function firstNonEmptyRow(rows: unknown[][]): string[] {
  for (const row of rows) {
    if (!row || row.length === 0) continue;
    const stringified = row.map((cell) =>
      cell === null || cell === undefined ? "" : String(cell).trim(),
    );
    if (stringified.some((s) => s !== "")) {
      return stringified;
    }
  }
  return [];
}

interface RawSheet {
  sheet?: string;
  data?: unknown[][];
}

export async function parseExcel(
  file: File,
  options: ParseExcelOptions = {},
): Promise<ExcelWorkbookSummary> {
  // `read-excel-file` returns Sheet[] = [{sheet: name, data: Row[]}] when called
  // without a `sheet` option. One round-trip; no second pass needed.
  const rawSheets = (await (readXlsxFile as unknown as (
    f: File,
  ) => Promise<RawSheet[]>)(file)) as RawSheet[];

  if (!Array.isArray(rawSheets) || rawSheets.length === 0) {
    throw new Error("workbook empty");
  }

  const sheets: ExcelSheetSummary[] = [];
  let totalRows = 0;
  for (const raw of rawSheets) {
    const data = raw.data ?? [];
    const headers = firstNonEmptyRow(data);
    const summary: ExcelSheetSummary = {
      name: raw.sheet ?? "",
      headers,
      rowCount: data.length,
    };
    if (options.includeRows) {
      summary.rows = data;
    }
    sheets.push(summary);
    totalRows += Math.max(0, data.length - 1);
  }

  return { sheets, totalRows };
}
