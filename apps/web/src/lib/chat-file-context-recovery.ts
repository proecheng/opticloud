import {
  ChatFileContextRejectError,
  buildChatCsvContextFromRows,
  parseChatCsvRowsWithLineNumbers,
  prepareChatFile,
  type ChatCsvParsedRow,
  type ChatFileContextPayload,
} from "./chat-file-context";

export type ChatCsvRecoveryActionId = "replace_failed_rows" | "retry_all" | "cancel";

export interface ChatCsvRecoveryAction {
  action: ChatCsvRecoveryActionId;
  label: string;
}

export interface ChatCsvRecoveryInvalidRow {
  row_number: number;
  data_row_number: number;
  field_path: string;
  constraint: string;
  remediation_hint_key: string;
}

export interface ChatCsvRecoverySuccess {
  ok: true;
  context: ChatFileContextPayload;
}

export interface ChatCsvRecoveryInvalid {
  ok: false;
  reason: "partial_invalid";
  invalid_row_count: number;
  invalid_rows: ChatCsvRecoveryInvalidRow[];
  actions: ChatCsvRecoveryAction[];
  session: ChatCsvRecoverySession;
}

export interface ChatCsvRecoveryTerminal {
  ok: false;
  reason: "retry_all" | "canceled";
  context: null;
}

export type ChatCsvRecoveryResult = ChatCsvRecoverySuccess | ChatCsvRecoveryInvalid;

type ParsedCsvRow = ChatCsvParsedRow;

type DraftCsvRow = {
  cells: string[];
  rowNumber: number;
  dataRowNumber: number;
};

type ChatCsvRecoverySource = {
  filename: string;
  sizeBytes: number;
  mimeType: string;
};

export const CHAT_PARTIAL_UPLOAD_RECOVERY_ACTIONS: ChatCsvRecoveryAction[] = [
  { action: "replace_failed_rows", label: "仅替换失败行" },
  { action: "retry_all", label: "全部重试" },
  { action: "cancel", label: "取消" },
] as const satisfies ChatCsvRecoveryAction[];

const MAX_PUBLIC_INVALID_ROWS = 20;
const ROW_NUMBER_ALIASES = ["row_number", "rownumber", "source_row", "源行号"];

export class ChatCsvRecoverySession {
  readonly filename: string;
  readonly invalid_row_count: number;

  #source: ChatCsvRecoverySource;
  #header: ParsedCsvRow;
  #dataRows: DraftCsvRow[];
  #invalidRows: ChatCsvRecoveryInvalidRow[];

  constructor(options: {
    source: ChatCsvRecoverySource;
    header: ParsedCsvRow;
    dataRows: DraftCsvRow[];
    invalidRows: ChatCsvRecoveryInvalidRow[];
  }) {
    this.filename = options.source.filename;
    this.invalid_row_count = options.invalidRows.length;
    this.#source = options.source;
    this.#header = cloneParsedRow(options.header);
    this.#dataRows = options.dataRows.map(cloneDraftRow);
    this.#invalidRows = options.invalidRows.map((row) => ({ ...row }));
  }

  get source(): ChatCsvRecoverySource {
    return { ...this.#source };
  }

  get invalidRows(): ChatCsvRecoveryInvalidRow[] {
    return this.#invalidRows.map((row) => ({ ...row }));
  }

  snapshot(): { filename: string; invalid_row_count: number } {
    return {
      filename: this.filename,
      invalid_row_count: this.invalid_row_count,
    };
  }

  applyReplacementCsv(replacementCsv: string): ChatCsvRecoveryResult {
    const parsed = parseReplacementRows(
      replacementCsv,
      this.#header.cells,
      this.#invalidRows.length,
    );
    if (!parsed.ok) return this.invalidReplacement(parsed.constraint);

    const invalidRows = this.#invalidRows.map((row) => ({ ...row }));
    const replacementsByRowNumber = new Map<number, string[]>();
    const requiresRowNumber = invalidRows.length > 1;

    for (let index = 0; index < parsed.rows.length; index += 1) {
      const replacement = parsed.rows[index];
      const fallbackInvalid = invalidRows[index];
      if (!replacement) {
        return this.invalidReplacement("replacement row count must match invalid row count");
      }
      const targetRowNumber = replacement.rowNumber ?? fallbackInvalid?.row_number;
      if (requiresRowNumber && replacement.rowNumber === undefined) {
        return this.invalidReplacement(
          "replacement source row number is required for multiple failed rows",
        );
      }
      if (!targetRowNumber || !invalidRows.some((row) => row.row_number === targetRowNumber)) {
        return this.invalidReplacement(
          "replacement source row must match a failed source row",
        );
      }
      if (replacementsByRowNumber.has(targetRowNumber)) {
        return this.invalidReplacement("replacement source row must be unique");
      }
      replacementsByRowNumber.set(targetRowNumber, replacement.cells);
    }

    const nextRows = this.#dataRows.map(cloneDraftRow);
    for (const invalid of invalidRows) {
      const replacement = replacementsByRowNumber.get(invalid.row_number);
      if (!replacement) {
        return this.invalidReplacement("replacement source row must match a failed source row");
      }
      const index = invalid.data_row_number - 1;
      const existing = nextRows[index];
      if (!existing || existing.rowNumber !== invalid.row_number) {
        return this.invalidReplacement("replacement source row must match a failed source row");
      }
      nextRows[index] = { ...existing, cells: [...replacement] };
    }

    return buildResult([cloneParsedRow(this.#header), ...nextRows.map(toParsedRow)], {
      ...this.#source,
    });
  }

  private invalidReplacement(constraint: string): ChatCsvRecoveryInvalid {
    return invalidResult(
      new ChatCsvRecoverySession({
        source: { ...this.#source },
        header: cloneParsedRow(this.#header),
        dataRows: this.#dataRows.map(cloneDraftRow),
        invalidRows: [
          {
            row_number: this.#invalidRows[0]?.row_number ?? 1,
            data_row_number: this.#invalidRows[0]?.data_row_number ?? 0,
            field_path: "replacement",
            constraint,
            remediation_hint_key: "chat.csv.replace_failed_row",
          },
        ],
      }),
    );
  }

  toJSON(): object {
    return { kind: "chat_csv_recovery_session", ...this.snapshot() };
  }
}

export async function parseChatCsvWithRecovery(file: File): Promise<ChatCsvRecoveryResult> {
  const { filename, kind } = prepareChatFile(file);
  if (kind !== "csv") {
    throw new ChatFileContextRejectError("unsupported_type", "仅支持 CSV 文件恢复。");
  }

  const source = {
    filename,
    sizeBytes: file.size,
    mimeType: file.type || "text/csv",
  };
  return buildResult(parseChatCsvRowsWithLineNumbers(await file.text()), source);
}

export function replaceFailedChatCsvRows(
  session: ChatCsvRecoverySession,
  replacementCsv: string,
): ChatCsvRecoveryResult {
  return session.applyReplacementCsv(replacementCsv);
}

export function retryAllChatCsvRecovery(
  _session: ChatCsvRecoverySession,
): ChatCsvRecoveryTerminal {
  return { ok: false, reason: "retry_all", context: null };
}

export function cancelChatCsvRecovery(
  _session: ChatCsvRecoverySession,
): ChatCsvRecoveryTerminal {
  return { ok: false, reason: "canceled", context: null };
}

function buildResult(
  rows: ParsedCsvRow[],
  source: ChatCsvRecoverySource,
): ChatCsvRecoveryResult {
  const evaluated = evaluateRows(rows);
  if (evaluated.invalidRows.length > 0) {
    return invalidResult(
      new ChatCsvRecoverySession({
        source,
        header: evaluated.header,
        dataRows: evaluated.dataRows,
        invalidRows: evaluated.invalidRows,
      }),
    );
  }

  return {
    ok: true,
    context: buildChatCsvContextFromRows(evaluated.rowsForContext, source),
  };
}

function evaluateRows(rows: ParsedCsvRow[]): {
  header: ParsedCsvRow;
  dataRows: DraftCsvRow[];
  invalidRows: ChatCsvRecoveryInvalidRow[];
  rowsForContext: string[][];
} {
  const header = rows[0] ?? { cells: [], row_number: 1 };
  const dataRows = rows.slice(1).map((row, index) => ({
    cells: [...row.cells],
    rowNumber: row.row_number,
    dataRowNumber: index + 1,
  }));
  const invalidRows: ChatCsvRecoveryInvalidRow[] = [];
  if (!header.cells.some((cell) => cell.trim() !== "")) {
    invalidRows.push({
      row_number: 1,
      data_row_number: 0,
      field_path: "header",
      constraint: "header row must be present",
      remediation_hint_key: "chat.csv.add_header",
    });
  }

  const expectedCellCount = header.cells.length;
  dataRows.forEach((row) => {
    if (row.cells.length !== expectedCellCount) {
      invalidRows.push({
        row_number: row.rowNumber,
        data_row_number: row.dataRowNumber,
        field_path: `rows[${row.dataRowNumber}]`,
        constraint: "row cell count must match header cell count",
        remediation_hint_key: "chat.csv.replace_failed_row",
      });
    }
  });

  return {
    header,
    dataRows,
    invalidRows,
    rowsForContext: [header.cells, ...dataRows.map((row) => row.cells)],
  };
}

function invalidResult(session: ChatCsvRecoverySession): ChatCsvRecoveryInvalid {
  return {
    ok: false,
    reason: "partial_invalid",
    invalid_row_count: session.invalid_row_count,
    invalid_rows: session.invalidRows.slice(0, MAX_PUBLIC_INVALID_ROWS),
    actions: CHAT_PARTIAL_UPLOAD_RECOVERY_ACTIONS.map((action) => ({ ...action })),
    session,
  };
}

type ReplacementParseResult =
  | {
      ok: true;
      rows: Array<{ cells: string[]; rowNumber?: number }>;
    }
  | { ok: false; constraint: string };

function parseReplacementRows(
  replacementCsv: string,
  headerCells: string[],
  invalidRowCount: number,
): ReplacementParseResult {
  const rows = parseChatCsvRowsWithLineNumbers(replacementCsv);
  if (rows.length === 0 || rows.length > invalidRowCount + 1) {
    return { ok: false, constraint: "replacement row count must match invalid row count" };
  }

  const first = rows[0] ?? { cells: [], row_number: 1 };
  const headerInfo = replacementHeaderInfo(first.cells, headerCells);
  const dataRows = headerInfo.hasHeader ? rows.slice(1) : rows;
  if (dataRows.length !== invalidRowCount) {
    return { ok: false, constraint: "replacement row count must match invalid row count" };
  }

  const replacements: Array<{ cells: string[]; rowNumber?: number }> = [];
  for (const row of dataRows) {
    const rowNumber =
      headerInfo.rowNumberIndex === -1
        ? undefined
        : parseSourceRowNumber(row.cells[headerInfo.rowNumberIndex] ?? "");
    if (headerInfo.rowNumberIndex !== -1 && rowNumber === undefined) {
      return { ok: false, constraint: "replacement source row must match a failed source row" };
    }
    const cells =
      headerInfo.rowNumberIndex === -1
        ? row.cells
        : row.cells.filter((_cell, index) => index !== headerInfo.rowNumberIndex);
    replacements.push({ cells: cells.map((cell) => cell.trim()), rowNumber });
  }

  if (replacements.some((row) => row.cells.length !== headerCells.length)) {
    return { ok: false, constraint: "replacement row cell count must match original header" };
  }

  return { ok: true, rows: replacements };
}

function replacementHeaderInfo(
  candidate: string[],
  originalHeader: string[],
): { hasHeader: boolean; rowNumberIndex: number } {
  const rowNumberIndex = candidate.findIndex((cell) =>
    ROW_NUMBER_ALIASES.includes(cell.trim().toLowerCase()),
  );
  const businessCells =
    rowNumberIndex === -1
      ? candidate
      : candidate.filter((_cell, index) => index !== rowNumberIndex);
  const hasHeader = normalizedCells(businessCells).join("\u0000") ===
    normalizedCells(originalHeader).join("\u0000");
  return { hasHeader, rowNumberIndex: hasHeader ? rowNumberIndex : -1 };
}

function parseSourceRowNumber(value: string): number | undefined {
  const parsed = Number(value.trim());
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function normalizedCells(values: string[]): string[] {
  return values.map((value) => value.trim().toLowerCase());
}

function cloneParsedRow(row: ParsedCsvRow): ParsedCsvRow {
  return { cells: [...row.cells], row_number: row.row_number };
}

function cloneDraftRow(row: DraftCsvRow): DraftCsvRow {
  return {
    cells: [...row.cells],
    rowNumber: row.rowNumber,
    dataRowNumber: row.dataRowNumber,
  };
}

function toParsedRow(row: DraftCsvRow): ParsedCsvRow {
  return { cells: [...row.cells], row_number: row.rowNumber };
}
