/** Heuristic task_type detector — Story 3.E.2 (PMR6).
 *
 * Given an ExcelWorkbookSummary, recommend ONE of:
 *   vrptw / schedule / inventory / lp / unknown
 *
 * Uses sheet-name + header-text signals; sums per-task scores; returns the
 * winner with a confidence in [0.2, 1] and a zh-CN reasoning sentence the
 * ConfirmationModal can display to the user.
 *
 * Manual override (via "其它" dropdown in the Modal) always wins — the user
 * has the wheel; this module is just a suggestion engine.
 */

import type { ExcelWorkbookSummary } from "./excel";

export type DetectedTaskType =
  | "vrptw"
  | "schedule"
  | "inventory"
  | "lp"
  | "unknown";

export interface DetectionResult {
  taskType: DetectedTaskType;
  /** [0.2, 1] for matched cases; 0 for `unknown` */
  confidence: number;
  /** zh-CN, 1-2 sentences for Modal body */
  reasoning: string;
  /** Other detected types, sorted by score desc, excluding winner */
  alternatives: DetectedTaskType[];
}

interface SignalSet {
  sheetTokens: string[];
  headerTokens: string[];
}

const SIGNALS: Record<Exclude<DetectedTaskType, "unknown">, SignalSet> = {
  vrptw: {
    sheetTokens: ["客户", "车辆", "路线", "时间窗", "customer", "vehicle", "route"],
    headerTokens: [
      "客户名",
      "经度",
      "纬度",
      "需求",
      "时间窗",
      "服务时间",
      "lat",
      "lng",
      "lon",
      "demand",
      "time_window",
      "service_time",
    ],
  },
  schedule: {
    sheetTokens: ["任务", "资源", "工序", "排班", "task", "resource", "shift"],
    headerTokens: [
      "任务名",
      "工期",
      "截止",
      "资源",
      "工序",
      "duration",
      "deadline",
      "resource",
      "shift",
      "employee",
    ],
  },
  inventory: {
    sheetTokens: ["出货", "sku", "库存", "季节", "sales", "inventory"],
    headerTokens: [
      "日期",
      "sku",
      "销量",
      "库存",
      "季节性",
      "date",
      "qty",
      "sales",
      "stock",
      "season",
    ],
  },
  lp: {
    sheetTokens: [],
    // Weak signal: matrix-style headers (single-letter / numeric labels)
    headerTokens: ["x1", "x2", "x3", "c1", "c2", "c", "a", "b"],
  },
};

const TASK_LABEL: Record<DetectedTaskType, string> = {
  vrptw: "VRPTW（带时间窗的客户路线规划）",
  schedule: "排班/调度",
  inventory: "库存预测",
  lp: "通用 LP（线性规划）",
  unknown: "未知类型",
};

function lower(s: string): string {
  return s.toLowerCase();
}

function scoreTask(summary: ExcelWorkbookSummary, signals: SignalSet): {
  score: number;
  matched: string[];
} {
  const matched: string[] = [];
  let score = 0;

  const sheetNames = summary.sheets.map((s) => lower(s.name));
  for (const token of signals.sheetTokens) {
    if (sheetNames.some((n) => n.includes(lower(token)))) {
      score += 1.0;
      matched.push(`工作表“${token}”`);
    }
  }

  const allHeaders = summary.sheets.flatMap((s) => s.headers.map(lower));
  for (const token of signals.headerTokens) {
    const t = lower(token);
    // Short tokens (≤3 chars, like LP's "a"/"b"/"c"/"x1") need exact match
    // to avoid matching common English words like "bar"/"baz". Longer tokens
    // (Chinese phrases or domain terms) use substring match.
    const matchedHeader =
      t.length <= 3
        ? allHeaders.some((h) => h === t)
        : allHeaders.some((h) => h.includes(t));
    if (matchedHeader) {
      score += 0.5;
      matched.push(`列“${token}”`);
    }
  }

  return { score, matched };
}

export function detectTaskType(summary: ExcelWorkbookSummary): DetectionResult {
  const tasks: Exclude<DetectedTaskType, "unknown">[] = [
    "vrptw",
    "schedule",
    "inventory",
    "lp",
  ];

  const scored = tasks.map((t) => {
    const { score, matched } = scoreTask(summary, SIGNALS[t]);
    return { task: t, score, matched };
  });

  scored.sort((a, b) => b.score - a.score);
  const winner = scored[0];
  const runnerUp = scored[1];

  if (!winner || winner.score < 1.0) {
    return {
      taskType: "unknown",
      confidence: 0,
      reasoning:
        "未匹配到任何模板的工作表或表头特征 — 请手动选择类型，或参考算法目录。",
      alternatives: scored.filter((s) => s.score > 0).map((s) => s.task),
    };
  }

  const denom = winner.score + Math.max(0.5, runnerUp?.score ?? 0);
  const raw = winner.score / denom;
  const confidence = Math.min(1, Math.max(0.2, raw));

  const matchedDesc =
    winner.matched.length > 3
      ? `${winner.matched.slice(0, 3).join(" / ")}（共 ${winner.matched.length} 处特征）`
      : winner.matched.join(" / ");
  const reasoning = `检测到 ${matchedDesc} — 推荐 ${TASK_LABEL[winner.task]}。`;

  return {
    taskType: winner.task,
    confidence,
    reasoning,
    alternatives: scored
      .filter((s) => s.task !== winner.task && s.score > 0)
      .map((s) => s.task),
  };
}

export { TASK_LABEL };
