/** Schedule schema mapper — Story 3.E.4 (PMR6).
 *
 * Reads parsed Excel rows for 任务 / 资源 / 工序 sheets and builds an OptiCloud
 * Schedule request payload. Pure function — no IO, no fetch. Called from the
 * Console page after task_type=schedule is confirmed in 3.E.2.
 *
 * Mirrors `vrptw-template.ts` in shape; duplication is intentional at v1 (per
 * the story's rule-of-three deferral — 3.E.5 will trigger the refactor into a
 * shared `lib/excel-helpers.ts`).
 */

import type { ExcelSheetSummary, ExcelWorkbookSummary } from "./excel";

export interface ScheduleTask {
  id: string;
  duration: number;
  deadline: string | null;
  resource: string | null;
  earliest_start: string | null;
}

export interface ScheduleResource {
  id: string;
  capacity: number;
  type: string | null;
}

export interface SchedulePrecedence {
  predecessor: string;
  successor: string;
}

export interface SchedulePayload {
  task_type: "schedule";
  tasks: ScheduleTask[];
  resources: ScheduleResource[];
  precedences: SchedulePrecedence[];
  options?: { max_solve_seconds?: number };
}

export interface ScheduleErrorDetail {
  sheet: string;
  field?: string;
  message: string;
}

export type ScheduleMappingResult =
  | {
      ok: true;
      payload: SchedulePayload;
      task_count: number;
      resource_count: number;
      precedence_count: number;
      warnings: string[];
    }
  | {
      ok: false;
      errors: ScheduleErrorDetail[];
    };

const SIGNALS = {
  taskSheet: ["任务", "task"],
  resourceSheet: ["资源", "resource", "shift", "employee"],
  precedenceSheet: ["工序", "precedence", "dependency"],
  taskId: ["任务名", "任务编号", "名称", "id", "task", "name"],
  duration: ["工期", "duration", "耗时"],
  deadline: ["截止", "deadline", "due"],
  taskResource: ["资源", "resource"],
  earliestStart: ["最早开始", "earliest", "start"],
  resourceId: ["编号", "名称", "id", "resource", "name"],
  capacity: ["容量", "capacity", "数量"],
  resourceType: ["类型", "type", "kind"],
  predecessor: ["前驱", "predecessor", "from"],
  successor: ["后继", "successor", "to"],
};

function lower(s: string): string {
  return s.toLowerCase();
}

function findSheet(
  summary: ExcelWorkbookSummary,
  tokens: string[],
): ExcelSheetSummary | null {
  const lowered = tokens.map(lower);
  return (
    summary.sheets.find((s) =>
      lowered.some((t) => lower(s.name).includes(t)),
    ) ?? null
  );
}

function findColumn(headers: string[], tokens: string[]): number {
  const loweredHeaders = headers.map(lower);
  for (const t of tokens) {
    const tLower = lower(t);
    const idx = loweredHeaders.findIndex((h) => h.includes(tLower));
    if (idx !== -1) return idx;
  }
  return -1;
}

function toNumber(cell: unknown): number | null {
  if (cell === null || cell === undefined || cell === "") return null;
  const n = typeof cell === "number" ? cell : Number(String(cell).trim());
  return Number.isFinite(n) ? n : null;
}

function toCellString(cell: unknown): string | null {
  if (cell === null || cell === undefined) return null;
  const s = String(cell).trim();
  return s === "" ? null : s;
}

export function buildSchedulePayload(
  summary: ExcelWorkbookSummary,
): ScheduleMappingResult {
  const errors: ScheduleErrorDetail[] = [];
  const warnings: string[] = [];

  const taskSheet = findSheet(summary, SIGNALS.taskSheet);
  const resourceSheet = findSheet(summary, SIGNALS.resourceSheet);
  const precedenceSheet = findSheet(summary, SIGNALS.precedenceSheet);

  if (!taskSheet) {
    errors.push({
      sheet: "任务",
      message: "未找到任务 sheet（期望包含 '任务' 或 'task' 字样）",
    });
  }
  if (!resourceSheet) {
    errors.push({
      sheet: "资源",
      message: "未找到资源 sheet（期望包含 '资源' / 'resource' / 'shift' / 'employee' 字样）",
    });
  }

  if (errors.length > 0 || !taskSheet || !resourceSheet) {
    return { ok: false, errors };
  }

  if (!taskSheet.rows || !resourceSheet.rows) {
    return {
      ok: false,
      errors: [
        {
          sheet: "(workbook)",
          message:
            "rows 未填充 — 请用 parseExcel(file, {includeRows: true}) 重新解析",
        },
      ],
    };
  }

  // Task mapping
  const tHeaders = taskSheet.headers;
  const tIdIdx = findColumn(tHeaders, SIGNALS.taskId);
  const tDurIdx = findColumn(tHeaders, SIGNALS.duration);
  const tDeadlineIdx = findColumn(tHeaders, SIGNALS.deadline);
  const tResIdx = findColumn(tHeaders, SIGNALS.taskResource);
  const tEarliestIdx = findColumn(tHeaders, SIGNALS.earliestStart);

  if (tIdIdx === -1)
    errors.push({
      sheet: taskSheet.name,
      field: "id",
      message: "缺少任务名 / id 列",
    });
  if (tDurIdx === -1)
    errors.push({
      sheet: taskSheet.name,
      field: "duration",
      message: "缺少工期 / duration 列",
    });

  // Resource mapping
  const rHeaders = resourceSheet.headers;
  const rIdIdx = findColumn(rHeaders, SIGNALS.resourceId);
  const rCapIdx = findColumn(rHeaders, SIGNALS.capacity);
  const rTypeIdx = findColumn(rHeaders, SIGNALS.resourceType);

  if (rIdIdx === -1)
    errors.push({
      sheet: resourceSheet.name,
      field: "id",
      message: "缺少编号 / id 列",
    });
  if (rCapIdx === -1)
    errors.push({
      sheet: resourceSheet.name,
      field: "capacity",
      message: "缺少容量 / capacity 列",
    });

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  // Build tasks (skip header row at index 0)
  const tasks: ScheduleTask[] = [];
  let skippedTRows = 0;
  for (let i = 1; i < taskSheet.rows.length; i++) {
    const row = taskSheet.rows[i];
    if (!row || row.length === 0) {
      skippedTRows++;
      continue;
    }
    const rawId = row[tIdIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedTRows++;
      continue;
    }
    const id = String(rawId).trim();
    const duration = toNumber(row[tDurIdx]);
    if (duration === null || duration <= 0) {
      errors.push({
        sheet: taskSheet.name,
        field: "duration",
        message: `第 ${i + 1} 行 "${id}" 工期无效 (${row[tDurIdx]})`,
      });
      continue;
    }

    tasks.push({
      id,
      duration,
      deadline: tDeadlineIdx !== -1 ? toCellString(row[tDeadlineIdx]) : null,
      resource: tResIdx !== -1 ? toCellString(row[tResIdx]) : null,
      earliest_start:
        tEarliestIdx !== -1 ? toCellString(row[tEarliestIdx]) : null,
    });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedTRows > 0) {
    warnings.push(`跳过 ${skippedTRows} 个空任务行`);
  }
  if (tasks.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: taskSheet.name, message: "任务 sheet 没有任何有效数据行" },
      ],
    };
  }

  // Build resources
  const resources: ScheduleResource[] = [];
  let skippedRRows = 0;
  for (let i = 1; i < resourceSheet.rows.length; i++) {
    const row = resourceSheet.rows[i];
    if (!row || row.length === 0) {
      skippedRRows++;
      continue;
    }
    const rawId = row[rIdIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedRRows++;
      continue;
    }
    const id = String(rawId).trim();
    const cap = toNumber(row[rCapIdx]);
    if (cap === null || cap <= 0) {
      errors.push({
        sheet: resourceSheet.name,
        field: "capacity",
        message: `第 ${i + 1} 行 "${id}" 容量无效 (${row[rCapIdx]})`,
      });
      continue;
    }
    resources.push({
      id,
      capacity: cap,
      type: rTypeIdx !== -1 ? toCellString(row[rTypeIdx]) : null,
    });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedRRows > 0) {
    warnings.push(`跳过 ${skippedRRows} 个空资源行`);
  }
  if (resources.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: resourceSheet.name, message: "资源 sheet 没有任何有效数据行" },
      ],
    };
  }

  // Optional precedences
  const precedences: SchedulePrecedence[] = [];
  if (!precedenceSheet) {
    warnings.push("工序 sheet 未找到 — 已默认无前驱后继约束");
  } else if (precedenceSheet.rows && precedenceSheet.rows.length > 1) {
    const pHeaders = precedenceSheet.headers;
    const pFromIdx = findColumn(pHeaders, SIGNALS.predecessor);
    const pToIdx = findColumn(pHeaders, SIGNALS.successor);

    if (pFromIdx === -1 || pToIdx === -1) {
      warnings.push("工序 sheet 缺少必要列 (前驱 / 后继) — 已忽略");
    } else {
      const taskIds = new Set(tasks.map((t) => t.id));
      let unmatched = 0;
      for (let i = 1; i < precedenceSheet.rows.length; i++) {
        const row = precedenceSheet.rows[i];
        if (!row || row.length === 0) continue;
        const rawFrom = row[pFromIdx];
        const rawTo = row[pToIdx];
        if (
          rawFrom === null ||
          rawFrom === undefined ||
          rawTo === null ||
          rawTo === undefined
        )
          continue;
        const predecessor = String(rawFrom).trim();
        const successor = String(rawTo).trim();
        if (!predecessor || !successor) continue;
        if (!taskIds.has(predecessor) || !taskIds.has(successor)) {
          unmatched++;
          continue;
        }
        precedences.push({ predecessor, successor });
      }
      if (unmatched > 0) {
        warnings.push(`工序 sheet 有 ${unmatched} 行引用了未知任务 id`);
      }
    }
  }

  // Soft warning for orphan resource references
  const resourceIds = new Set(resources.map((r) => r.id));
  const orphanResource = tasks.filter(
    (t) => t.resource !== null && !resourceIds.has(t.resource),
  );
  if (orphanResource.length > 0) {
    warnings.push(
      `${orphanResource.length} 个任务引用了未在 资源 sheet 中定义的 resource`,
    );
  }

  return {
    ok: true,
    payload: {
      task_type: "schedule",
      tasks,
      resources,
      precedences,
    },
    task_count: tasks.length,
    resource_count: resources.length,
    precedence_count: precedences.length,
    warnings,
  };
}
