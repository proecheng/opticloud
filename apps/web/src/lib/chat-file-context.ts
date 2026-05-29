import { parseExcel } from "./excel";

export type ChatFileContextKind = "csv" | "excel" | "json";
export type ChatFileContextRejectCode =
  | "too_large"
  | "unsupported_type"
  | "invalid_filename"
  | "parse_failed";

export interface ChatFileSheetContextPayload {
  name: string;
  headers: string[];
  row_count: number;
}

export interface ChatFileContextPayload {
  source: "parsed_browser_file_context_v1";
  kind: ChatFileContextKind;
  filename: string;
  size_bytes: number;
  mime_type: string;
  row_count: number;
  sheet_count: number;
  sheets: ChatFileSheetContextPayload[];
  top_level_keys: string[];
  detected_fields: string[];
  summary: string;
}

export interface ChatCsvParsedRow {
  cells: string[];
  row_number: number;
}

export class ChatFileContextRejectError extends Error {
  code: ChatFileContextRejectCode;
  max_mb?: string;

  constructor(code: ChatFileContextRejectCode, message: string, maxMb?: string) {
    super(message);
    this.name = "ChatFileContextRejectError";
    this.code = code;
    this.max_mb = maxMb;
  }
}

const SOURCE = "parsed_browser_file_context_v1" as const;
const MAX_SIZE_BYTES = 5 * 1024 * 1024;
const MAX_HEADERS = 20;
const MAX_FIELDS = 30;
const MAX_SHEETS = 12;
const FILENAME_PATTERN = /^[^/\\:\u0000-\u001f]{1,120}$/;
const CSV_MIME_TYPES = new Set(["", "text/csv", "application/csv", "application/vnd.ms-excel"]);
const EXCEL_MIME_TYPES = new Set([
  "",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]);
const JSON_MIME_TYPES = new Set(["", "application/json", "text/json"]);
const NO_LEAK_PATTERN =
  /(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|authorization|cookie|password|token|raw[_ -]?(response|request|row|value)|provider[_ -]?(request|response|payload)?|prompt|traceback|generated[_ -]?code|sandbox[_ -]?output|charge_id|optimization_id|prediction_id|callback[_ -]?url|[A-Za-z]:\\|\/tmp\/|\/var\/|queue[_ -]?payload)/i;

export async function parseChatFileContext(file: File): Promise<ChatFileContextPayload> {
  const { filename, kind } = prepareChatFile(file);
  if (kind === "csv") return parseCsvContext(file, filename);
  if (kind === "excel") return parseExcelContext(file, filename);
  if (kind === "json") return parseJsonContext(file, filename);
  throw new ChatFileContextRejectError("unsupported_type", "仅支持 CSV、Excel 或 JSON 文件。");
}

export function prepareChatFile(file: File): {
  filename: string;
  kind: ChatFileContextKind;
} {
  const filename = safeFilename(file.name);
  if (file.size > MAX_SIZE_BYTES) {
    throw new ChatFileContextRejectError(
      "too_large",
      "文件超过 5MB 上限。",
      "5",
    );
  }
  return { filename, kind: classifyKind(filename, file.type) };
}

async function parseCsvContext(file: File, filename: string): Promise<ChatFileContextPayload> {
  try {
    const text = await file.text();
    return buildChatCsvContextFromRows(parseChatCsvRows(text), {
      filename,
      sizeBytes: file.size,
      mimeType: file.type || "text/csv",
    });
  } catch (error) {
    if (error instanceof ChatFileContextRejectError) throw error;
    throw new ChatFileContextRejectError("parse_failed", "无法解析 CSV 文件。");
  }
}

export function buildChatCsvContextFromRows(
  rows: string[][],
  source: { filename: string; sizeBytes: number; mimeType: string },
): ChatFileContextPayload {
  const headerRow = rows.find((row) => row.some((cell) => cell.trim()));
  const headers = safeTerms(headerRow ?? [], MAX_HEADERS);
  const rowCount = Math.max(0, rows.length - 1);
  return {
    source: SOURCE,
    kind: "csv",
    filename: source.filename,
    size_bytes: source.sizeBytes,
    mime_type: safeMime(source.mimeType || "text/csv"),
    row_count: rowCount,
    sheet_count: 0,
    sheets: [],
    top_level_keys: [],
    detected_fields: safeTerms(headers, MAX_FIELDS),
    summary: `csv rows=${rowCount} headers=${headers.join(", ")}`,
  };
}

async function parseExcelContext(file: File, filename: string): Promise<ChatFileContextPayload> {
  try {
    const workbook = await parseExcel(file);
    const sheets = workbook.sheets.slice(0, MAX_SHEETS).map((sheet) => ({
      name: safeTerm(sheet.name),
      headers: safeTerms(sheet.headers, MAX_HEADERS),
      row_count: sheet.rowCount,
    }));
    const detectedFields = safeTerms(
      sheets.flatMap((sheet) => sheet.headers),
      MAX_FIELDS,
    );
    return {
      source: SOURCE,
      kind: "excel",
      filename,
      size_bytes: file.size,
      mime_type: safeMime(
        file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ),
      row_count: workbook.totalRows,
      sheet_count: sheets.length,
      sheets,
      top_level_keys: [],
      detected_fields: detectedFields,
      summary: `excel rows=${workbook.totalRows} sheets=${sheets
        .map((sheet) => sheet.name)
        .join(", ")}`,
    };
  } catch (error) {
    if (error instanceof ChatFileContextRejectError) throw error;
    throw new ChatFileContextRejectError("parse_failed", "无法解析 Excel 文件。");
  }
}

async function parseJsonContext(file: File, filename: string): Promise<ChatFileContextPayload> {
  try {
    const parsed = JSON.parse(await file.text()) as unknown;
    const { keys, rowCount, summary } = summarizeJson(parsed);
    const topLevelKeys = safeTerms(keys, MAX_FIELDS);
    return {
      source: SOURCE,
      kind: "json",
      filename,
      size_bytes: file.size,
      mime_type: safeMime(file.type || "application/json"),
      row_count: rowCount,
      sheet_count: 0,
      sheets: [],
      top_level_keys: topLevelKeys,
      detected_fields: topLevelKeys,
      summary,
    };
  } catch (error) {
    if (error instanceof ChatFileContextRejectError) throw error;
    throw new ChatFileContextRejectError("parse_failed", "无法解析 JSON 文件。");
  }
}

function safeFilename(value: string): string {
  const clean = value.trim();
  if (!FILENAME_PATTERN.test(clean) || clean.includes("..")) {
    throw new ChatFileContextRejectError("invalid_filename", "文件名必须是不含路径的安全名称。");
  }
  if (NO_LEAK_PATTERN.test(clean)) {
    throw new ChatFileContextRejectError("invalid_filename", "文件名包含不安全内容。");
  }
  return clean;
}

function classifyKind(filename: string, mimeType: string): ChatFileContextKind {
  const lowerName = filename.toLowerCase();
  const lowerMime = mimeType.trim().toLowerCase();
  if (lowerName.endsWith(".csv")) return requireSupportedMime("csv", lowerMime, CSV_MIME_TYPES);
  if (lowerName.endsWith(".xlsx")) {
    return requireSupportedMime("excel", lowerMime, EXCEL_MIME_TYPES);
  }
  if (lowerName.endsWith(".json")) return requireSupportedMime("json", lowerMime, JSON_MIME_TYPES);
  throw new ChatFileContextRejectError("unsupported_type", "仅支持 CSV、Excel 或 JSON 文件。");
}

function requireSupportedMime(
  kind: ChatFileContextKind,
  mimeType: string,
  allowed: Set<string>,
): ChatFileContextKind {
  if (!allowed.has(mimeType)) {
    throw new ChatFileContextRejectError("unsupported_type", "仅支持 CSV、Excel 或 JSON 文件。");
  }
  return kind;
}

export function parseChatCsvRows(text: string): string[][] {
  return parseChatCsvRowsWithLineNumbers(text).map((row) => row.cells);
}

export function parseChatCsvRowsWithLineNumbers(text: string): ChatCsvParsedRow[] {
  const rows: ChatCsvParsedRow[] = [];
  let current = "";
  let row: string[] = [];
  let inQuotes = false;
  let physicalRowNumber = 1;
  const pushRow = (): void => {
    row.push(current);
    if (row.some((cell) => cell.trim())) {
      rows.push({ cells: row, row_number: physicalRowNumber });
    }
    row = [];
    current = "";
  };

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      row.push(current);
      current = "";
    } else if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      pushRow();
      physicalRowNumber += 1;
    } else {
      current += char;
    }
  }
  pushRow();
  return rows;
}

function summarizeJson(value: unknown): { keys: string[]; rowCount: number; summary: string } {
  if (Array.isArray(value)) {
    const first = value.find((item) => item && typeof item === "object" && !Array.isArray(item));
    const keys = first ? Object.keys(first as Record<string, unknown>) : [];
    return {
      keys,
      rowCount: value.length,
      summary: `json array length=${value.length} keys=${safeTerms(keys, 10).join(", ")}`,
    };
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return {
      keys,
      rowCount: Array.isArray(value) ? value.length : 0,
      summary: `json object keys=${safeTerms(keys, 10).join(", ")}`,
    };
  }
  return { keys: ["value"], rowCount: 1, summary: "json scalar value" };
}

function safeMime(value: string): string {
  const clean = value.trim().toLowerCase();
  if (!clean || NO_LEAK_PATTERN.test(clean) || /[\r\n\t]/.test(clean)) {
    return "application/octet-stream";
  }
  return clean.slice(0, 100);
}

function safeTerms(values: string[], maxItems: number): string[] {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const clean = safeTerm(value);
    if (!clean || seen.has(clean)) continue;
    output.push(clean);
    seen.add(clean);
    if (output.length >= maxItems) break;
  }
  return output;
}

function safeTerm(value: string): string {
  const clean = String(value).trim().slice(0, 64);
  if (
    !clean ||
    NO_LEAK_PATTERN.test(clean) ||
    /[\r\n\t]/.test(clean) ||
    clean.includes("/") ||
    clean.includes("\\") ||
    clean.includes(":") ||
    clean.includes("..")
  ) {
    return "";
  }
  return clean;
}
