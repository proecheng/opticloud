export type PredictionFamily = "arima" | "chronos";

export interface PredictionCsvRecord {
  sku: string;
  period: string;
  value: number;
  rowNumber: number;
  dataRowNumber: number;
}

export interface PredictionCsvInvalidRow {
  rowNumber: number;
  dataRowNumber: number;
  fieldPath: string;
  value: unknown;
  constraint: string;
}

export interface PredictionCsvSummary {
  filename: string;
  encoding: "utf-8" | "gb18030";
  rowCount: number;
  skuCount: number;
  periodCount: number;
  minPeriod: string | null;
  maxPeriod: string | null;
}

export interface PredictionCsvDraftRow {
  sku: string;
  period: string;
  rawValue: string;
  rowNumber: number;
  dataRowNumber: number;
}

export interface PredictionCsvValidResult {
  ok: true;
  records: PredictionCsvRecord[];
  series: number[];
  periods: string[];
  summary: PredictionCsvSummary;
  defaultFamily: PredictionFamily;
  defaultHorizon: number;
}

export interface PredictionCsvInvalidResult {
  ok: false;
  records: PredictionCsvRecord[];
  invalidRows: PredictionCsvInvalidRow[];
  summary: PredictionCsvSummary;
  draftRows: PredictionCsvDraftRow[];
}

export type PredictionCsvParseResult =
  | PredictionCsvValidResult
  | PredictionCsvInvalidResult;

export interface PredictionRequestBody {
  family: PredictionFamily;
  data: number[];
  horizon: number;
}

const MAX_DATA_ROWS = 10_000;
const DEFAULT_FAMILY: PredictionFamily = "chronos";
const DEFAULT_HORIZON = 3;

const HEADER_ALIASES = {
  sku: ["sku", "商品", "商品编号"],
  period: ["month", "date", "月份", "日期"],
  value: ["value", "sales", "销量", "销售额", "需求"],
};
const ROW_NUMBER_ALIASES = ["row_number", "rowNumber", "source_row", "源行号"];

export async function parsePredictionCsv(file: File): Promise<PredictionCsvParseResult> {
  const decoded = await decodeCsvFile(file);
  return parsePredictionCsvText(decoded.text, {
    filename: file.name,
    encoding: decoded.encoding,
  });
}

export function replaceInvalidPredictionRows(
  result: PredictionCsvInvalidResult,
  replacementCsv: string,
): PredictionCsvParseResult {
  const replacementRows = parseReplacementRows(replacementCsv, result.invalidRows.length);
  if (!replacementRows.ok) {
    return invalidReplacement(result, replacementRows.constraint);
  }
  if (replacementRows.length !== result.invalidRows.length) {
    return invalidReplacement(result, "replacement row count must match invalid row count");
  }

  const nextRows = result.draftRows.map((row) => ({ ...row }));
  for (let i = 0; i < result.invalidRows.length; i++) {
    const invalid = result.invalidRows[i];
    const replacement = replacementRows[i];
    const existing = nextRows.find((row) => row.rowNumber === invalid.rowNumber);
    if (!replacement || !existing) {
      return invalidReplacement(result, "replacement row must match an invalid source row");
    }
    const replacementMatchesKey =
      rowKey(existing) === `${replacement.sku}\u0000${replacement.period}`;
    const replacementMatchesRow =
      replacement.rowNumber !== undefined && replacement.rowNumber === invalid.rowNumber;
    if (!replacementMatchesKey && !replacementMatchesRow) {
      return invalidReplacement(
        result,
        "replacement row must match the invalid row sku and period or source row number",
      );
    }
    nextRows[existing.dataRowNumber - 1] = {
      ...existing,
      sku: replacement.sku,
      period: replacement.period,
      rawValue: replacement.rawValue,
    };
  }

  return buildResultFromDraftRows(nextRows, {
    filename: result.summary.filename,
    encoding: result.summary.encoding,
  });
}

export function buildPredictionRequest(
  result: PredictionCsvValidResult,
  options: { family: PredictionFamily; horizon: number },
): PredictionRequestBody {
  return {
    family: options.family,
    data: result.series,
    horizon: options.horizon,
  };
}

async function decodeCsvFile(
  file: File,
): Promise<{ text: string; encoding: "utf-8" | "gb18030" }> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const utf8 = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  if (!utf8.includes("\uFFFD")) {
    return { text: stripBom(utf8), encoding: "utf-8" };
  }
  try {
    const gb = new TextDecoder("gb18030", { fatal: true }).decode(bytes);
    return { text: stripBom(gb), encoding: "gb18030" };
  } catch {
    throw new Error("无法识别 CSV 编码。请另存为 UTF-8 CSV 后重试。");
  }
}

function stripBom(value: string): string {
  return value.charCodeAt(0) === 0xfeff ? value.slice(1) : value;
}

function parsePredictionCsvText(
  text: string,
  source: { filename: string; encoding: "utf-8" | "gb18030" },
): PredictionCsvParseResult {
  const rows = parseCsvRows(text).filter((row) => row.some((cell) => cell.trim() !== ""));
  return buildResultFromRows(rows, source);
}

function buildResultFromRows(
  rows: string[][],
  source: { filename: string; encoding: "utf-8" | "gb18030" },
): PredictionCsvParseResult {
  const header = rows[0] ?? [];
  const dataRows = rows.slice(1);
  const invalidRows: PredictionCsvInvalidRow[] = [];
  const columns = resolveColumns(header);
  const hasRequiredColumns = Object.values(columns).every((idx) => idx !== -1);

  if (dataRows.length > MAX_DATA_ROWS) {
    invalidRows.push({
      rowNumber: dataRows.length + 1,
      dataRowNumber: dataRows.length,
      fieldPath: "rows",
      value: dataRows.length,
      constraint: "CSV data rows must be <= 10000",
    });
  }

  for (const [field, idx] of Object.entries(columns)) {
    if (idx === -1) {
      invalidRows.push({
        rowNumber: 1,
        dataRowNumber: 0,
        fieldPath: `header.${field}`,
        value: "[omitted]",
        constraint: `missing required ${field} column`,
      });
    }
  }

  const draftRows =
    hasRequiredColumns && dataRows.length <= MAX_DATA_ROWS
      ? dataRows.map((row, rowIndex) => ({
          sku: cell(row, columns.sku),
          period: normalizePeriod(cell(row, columns.period)),
          rawValue: cell(row, columns.value),
          rowNumber: rowIndex + 2,
          dataRowNumber: rowIndex + 1,
        }))
      : [];

  const validation = validateDraftRows(draftRows, source, dataRows.length);
  invalidRows.push(...validation.invalidRows);
  const { records, series, periods, summary } = validation;

  if (invalidRows.length > 0) {
    return {
      ok: false,
      records,
      invalidRows,
      summary,
      draftRows,
    };
  }

  if (series.length < 3) {
    return {
      ok: false,
      records,
      invalidRows: [
        {
          rowNumber: records.at(-1)?.rowNumber ?? 1,
          dataRowNumber: records.at(-1)?.dataRowNumber ?? 0,
          fieldPath: "data",
          value: series.length,
          constraint: "data length must be at least 3 after aggregation",
        },
      ],
      summary,
      draftRows,
    };
  }

  return {
    ok: true,
    records,
    series,
    periods,
    summary,
    defaultFamily: DEFAULT_FAMILY,
    defaultHorizon: DEFAULT_HORIZON,
  };
}

function buildResultFromDraftRows(
  draftRows: PredictionCsvDraftRow[],
  source: { filename: string; encoding: "utf-8" | "gb18030" },
): PredictionCsvParseResult {
  const validation = validateDraftRows(draftRows, source, draftRows.length);
  if (validation.invalidRows.length > 0) {
    return {
      ok: false,
      records: validation.records,
      invalidRows: validation.invalidRows,
      summary: validation.summary,
      draftRows,
    };
  }
  if (validation.series.length < 3) {
    return {
      ok: false,
      records: validation.records,
      invalidRows: [
        {
          rowNumber: draftRows.at(-1)?.rowNumber ?? 1,
          dataRowNumber: draftRows.at(-1)?.dataRowNumber ?? 0,
          fieldPath: "data",
          value: validation.series.length,
          constraint: "data length must be at least 3 after aggregation",
        },
      ],
      summary: validation.summary,
      draftRows,
    };
  }
  return {
    ok: true,
    records: validation.records,
    series: validation.series,
    periods: validation.periods,
    summary: validation.summary,
    defaultFamily: DEFAULT_FAMILY,
    defaultHorizon: DEFAULT_HORIZON,
  };
}

function validateDraftRows(
  draftRows: PredictionCsvDraftRow[],
  source: { filename: string; encoding: "utf-8" | "gb18030" },
  rowCount: number,
): {
  records: PredictionCsvRecord[];
  invalidRows: PredictionCsvInvalidRow[];
  series: number[];
  periods: string[];
  summary: PredictionCsvSummary;
} {
  const records: PredictionCsvRecord[] = [];
  const invalidRows: PredictionCsvInvalidRow[] = [];

  for (const row of draftRows) {
    const numericValue = Number(row.rawValue);
    if (!row.sku) {
      invalidRows.push({
        rowNumber: row.rowNumber,
        dataRowNumber: row.dataRowNumber,
        fieldPath: `rows[${row.dataRowNumber}].sku`,
        value: row.rawValue,
        constraint: "sku must be non-empty",
      });
      continue;
    }
    if (!row.period) {
      invalidRows.push({
        rowNumber: row.rowNumber,
        dataRowNumber: row.dataRowNumber,
        fieldPath: `rows[${row.dataRowNumber}].period`,
        value: row.period,
        constraint: "period must be non-empty",
      });
      continue;
    }
    if (!Number.isFinite(numericValue)) {
      invalidRows.push({
        rowNumber: row.rowNumber,
        dataRowNumber: row.dataRowNumber,
        fieldPath: `rows[${row.dataRowNumber}].value`,
        value: compactValue(row.rawValue),
        constraint: "value must be a finite number",
      });
      continue;
    }
    records.push({
      sku: row.sku,
      period: row.period,
      value: numericValue,
      rowNumber: row.rowNumber,
      dataRowNumber: row.dataRowNumber,
    });
  }

  const { series, periods } = aggregateSeries(records);
  return {
    records,
    invalidRows,
    series,
    periods,
    summary: summarize(source, records, rowCount, periods),
  };
}

function resolveColumns(header: string[]): { sku: number; period: number; value: number } {
  return {
    sku: findHeader(header, HEADER_ALIASES.sku),
    period: findHeader(header, HEADER_ALIASES.period),
    value: findHeader(header, HEADER_ALIASES.value),
  };
}

function findHeader(header: string[], aliases: string[]): number {
  const normalized = header.map((value) => value.trim().toLowerCase());
  for (const alias of aliases) {
    const idx = normalized.findIndex((value) => value === alias.toLowerCase());
    if (idx !== -1) return idx;
  }
  return -1;
}

function cell(row: string[], idx: number): string {
  return idx >= 0 ? (row[idx] ?? "").trim() : "";
}

function normalizePeriod(value: string): string {
  return value.trim();
}

function aggregateSeries(records: PredictionCsvRecord[]): {
  series: number[];
  periods: string[];
} {
  const buckets = new Map<string, number>();
  for (const record of records) {
    buckets.set(record.period, (buckets.get(record.period) ?? 0) + record.value);
  }
  const periods = [...buckets.keys()].sort();
  return {
    periods,
    series: periods.map((period) => stableNumber(buckets.get(period) ?? 0)),
  };
}

function summarize(
  source: { filename: string; encoding: "utf-8" | "gb18030" },
  records: PredictionCsvRecord[],
  rowCount: number,
  periods: string[],
): PredictionCsvSummary {
  return {
    filename: source.filename,
    encoding: source.encoding,
    rowCount,
    skuCount: new Set(records.map((row) => row.sku)).size,
    periodCount: periods.length,
    minPeriod: periods[0] ?? null,
    maxPeriod: periods.at(-1) ?? null,
  };
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cellValue = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cellValue += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cellValue += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(cellValue);
      cellValue = "";
    } else if (ch === "\n") {
      row.push(cellValue);
      rows.push(row);
      row = [];
      cellValue = "";
    } else if (ch !== "\r") {
      cellValue += ch;
    }
  }
  row.push(cellValue);
  rows.push(row);
  return rows;
}

function rowKey(row: PredictionCsvDraftRow): string {
  return `${row.sku}\u0000${row.period}`;
}

type ReplacementRows =
  | (Array<{
      sku: string;
      period: string;
      rawValue: string;
      rowNumber?: number;
    }> & { ok: true })
  | { ok: false; constraint: string };

function parseReplacementRows(
  replacementCsv: string,
  invalidRowCount: number,
): ReplacementRows {
  const rows = parseCsvRows(replacementCsv).filter((row) =>
    row.some((cellValue) => cellValue.trim() !== ""),
  );
  if (rows.length === 0) {
    return { ok: false, constraint: "replacement row count must match invalid row count" };
  }

  const firstRow = rows[0] ?? [];
  const headerColumns = resolveColumns(firstRow);
  const hasHeader = Object.values(headerColumns).every((idx) => idx !== -1);
  const rowNumberColumn = hasHeader ? findHeader(firstRow, ROW_NUMBER_ALIASES) : -1;

  const dataRows = hasHeader ? rows.slice(1) : rows;
  if (dataRows.length !== invalidRowCount) {
    return { ok: false, constraint: "replacement row count must match invalid row count" };
  }

  const replacements = dataRows.map((row) => {
    if (hasHeader) {
      const rawRowNumber = cell(row, rowNumberColumn);
      const parsedRowNumber = Number(rawRowNumber);
      return {
        sku: cell(row, headerColumns.sku),
        period: normalizePeriod(cell(row, headerColumns.period)),
        rawValue: cell(row, headerColumns.value),
        rowNumber:
          rawRowNumber !== "" && Number.isInteger(parsedRowNumber) && parsedRowNumber > 0
            ? parsedRowNumber
            : undefined,
      };
    }
    return {
      sku: cell(row, 0),
      period: normalizePeriod(cell(row, 1)),
      rawValue: cell(row, 2),
    };
  });

  return Object.assign(replacements, { ok: true as const });
}

function invalidReplacement(
  result: PredictionCsvInvalidResult,
  constraint: string,
): PredictionCsvInvalidResult {
  return {
    ...result,
    invalidRows: [
      {
        rowNumber: result.invalidRows[0]?.rowNumber ?? 1,
        dataRowNumber: result.invalidRows[0]?.dataRowNumber ?? 0,
        fieldPath: "replacement",
        value: "[omitted]",
        constraint,
      },
    ],
  };
}

function compactValue(value: string): string {
  return value.length > 80 ? "[omitted]" : value;
}

function stableNumber(value: number): number {
  return Number(value.toFixed(6));
}
