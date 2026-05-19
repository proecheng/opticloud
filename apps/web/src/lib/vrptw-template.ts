/** VRPTW schema mapper — Story 3.E.3 (PMR6).
 *
 * Reads parsed Excel rows for 客户/车辆/时间窗 sheets and builds an OptiCloud
 * VRPTW request payload. Pure function — no IO, no fetch. Called from the
 * Console page after task_type=vrptw is confirmed in 3.E.2.
 *
 * Column-mapping heuristic: case-insensitive substring match against curated
 * Chinese + English alias lists (see SIGNALS below). Required columns missing
 * → returns ok=false with field-level errors.
 */

import type { ExcelWorkbookSummary } from "./excel";
import { findColumn, findSheet, toNumber } from "./excel-helpers";

export interface VRPTWCustomer {
  id: string;
  lat: number;
  lng: number;
  demand: number;
  time_window_start: string | null;
  time_window_end: string | null;
  service_minutes: number | null;
}

export interface VRPTWVehicle {
  id: string;
  capacity: number;
}

export interface VRPTWPayload {
  task_type: "vrptw";
  customers: VRPTWCustomer[];
  vehicles: VRPTWVehicle[];
  options?: { max_solve_seconds?: number };
}

export interface VRPTWErrorDetail {
  sheet: string;
  field?: string;
  message: string;
}

export type VRPTWMappingResult =
  | {
      ok: true;
      payload: VRPTWPayload;
      customer_count: number;
      vehicle_count: number;
      warnings: string[];
    }
  | {
      ok: false;
      errors: VRPTWErrorDetail[];
    };

const SIGNALS = {
  customerSheet: ["客户", "customer"],
  vehicleSheet: ["车辆", "vehicle"],
  timeWindowSheet: ["时间窗", "time_window", "timewindow"],
  customerId: ["客户名", "客户编号", "名称", "id", "customer", "name"],
  lat: ["纬度", "lat", "latitude"],
  lng: ["经度", "lng", "lon", "longitude"],
  demand: ["需求", "demand", "数量", "qty"],
  serviceMinutes: ["服务时间", "service_time", "service_minutes"],
  vehicleId: ["编号", "id", "vehicle", "name"],
  capacity: ["容量", "capacity"],
  twStart: ["开始", "start"],
  twEnd: ["结束", "end"],
};

function toTimeString(cell: unknown): string | null {
  if (cell === null || cell === undefined || cell === "") return null;
  if (cell instanceof Date) {
    const hh = String(cell.getUTCHours()).padStart(2, "0");
    const mm = String(cell.getUTCMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }
  return String(cell).trim();
}

export function buildVrptwPayload(
  summary: ExcelWorkbookSummary,
): VRPTWMappingResult {
  const errors: VRPTWErrorDetail[] = [];
  const warnings: string[] = [];

  const customerSheet = findSheet(summary, SIGNALS.customerSheet);
  const vehicleSheet = findSheet(summary, SIGNALS.vehicleSheet);
  const twSheet = findSheet(summary, SIGNALS.timeWindowSheet);

  if (!customerSheet) {
    errors.push({
      sheet: "客户",
      message: "未找到客户 sheet（期望包含 '客户' 或 'customer' 字样）",
    });
  }
  if (!vehicleSheet) {
    errors.push({
      sheet: "车辆",
      message: "未找到车辆 sheet（期望包含 '车辆' 或 'vehicle' 字样）",
    });
  }

  if (errors.length > 0 || !customerSheet || !vehicleSheet) {
    return { ok: false, errors };
  }

  if (!customerSheet.rows || !vehicleSheet.rows) {
    return {
      ok: false,
      errors: [
        {
          sheet: "(workbook)",
          message: "rows 未填充 — 请用 parseExcel(file, {includeRows: true}) 重新解析",
        },
      ],
    };
  }

  // Customer mapping
  const cHeaders = customerSheet.headers;
  const cIdIdx = findColumn(cHeaders, SIGNALS.customerId);
  const cLatIdx = findColumn(cHeaders, SIGNALS.lat);
  const cLngIdx = findColumn(cHeaders, SIGNALS.lng);
  const cDemandIdx = findColumn(cHeaders, SIGNALS.demand);
  const cServiceIdx = findColumn(cHeaders, SIGNALS.serviceMinutes);

  if (cIdIdx === -1)
    errors.push({ sheet: customerSheet.name, field: "id", message: "缺少客户名 / id 列" });
  if (cLatIdx === -1)
    errors.push({ sheet: customerSheet.name, field: "lat", message: "缺少纬度 / lat 列" });
  if (cLngIdx === -1)
    errors.push({ sheet: customerSheet.name, field: "lng", message: "缺少经度 / lng 列" });
  if (cDemandIdx === -1)
    errors.push({ sheet: customerSheet.name, field: "demand", message: "缺少需求 / demand 列" });

  // Vehicle mapping
  const vHeaders = vehicleSheet.headers;
  const vIdIdx = findColumn(vHeaders, SIGNALS.vehicleId);
  const vCapIdx = findColumn(vHeaders, SIGNALS.capacity);

  if (vIdIdx === -1)
    errors.push({ sheet: vehicleSheet.name, field: "id", message: "缺少编号 / id 列" });
  if (vCapIdx === -1)
    errors.push({
      sheet: vehicleSheet.name,
      field: "capacity",
      message: "缺少容量 / capacity 列",
    });

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  // Build customers (skip header row at index 0)
  const customers: VRPTWCustomer[] = [];
  let skippedRows = 0;
  for (let i = 1; i < customerSheet.rows.length; i++) {
    const row = customerSheet.rows[i];
    if (!row || row.length === 0) {
      skippedRows++;
      continue;
    }
    const rawId = row[cIdIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedRows++;
      continue;
    }
    const id = String(rawId).trim();
    const lat = toNumber(row[cLatIdx]);
    const lng = toNumber(row[cLngIdx]);
    const demand = toNumber(row[cDemandIdx]);
    const serviceMins = cServiceIdx !== -1 ? toNumber(row[cServiceIdx]) : null;

    if (lat === null || lat < -90 || lat > 90) {
      errors.push({
        sheet: customerSheet.name,
        field: "lat",
        message: `第 ${i + 1} 行 "${id}" 纬度无效 (${row[cLatIdx]})`,
      });
      continue;
    }
    if (lng === null || lng < -180 || lng > 180) {
      errors.push({
        sheet: customerSheet.name,
        field: "lng",
        message: `第 ${i + 1} 行 "${id}" 经度无效 (${row[cLngIdx]})`,
      });
      continue;
    }
    if (demand === null || demand < 0) {
      errors.push({
        sheet: customerSheet.name,
        field: "demand",
        message: `第 ${i + 1} 行 "${id}" 需求无效 (${row[cDemandIdx]})`,
      });
      continue;
    }

    customers.push({
      id,
      lat,
      lng,
      demand,
      time_window_start: null,
      time_window_end: null,
      service_minutes: serviceMins,
    });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedRows > 0) {
    warnings.push(`跳过 ${skippedRows} 个空客户行`);
  }
  if (customers.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: customerSheet.name, message: "客户 sheet 没有任何有效数据行" },
      ],
    };
  }

  // Build vehicles
  const vehicles: VRPTWVehicle[] = [];
  let skippedVRows = 0;
  for (let i = 1; i < vehicleSheet.rows.length; i++) {
    const row = vehicleSheet.rows[i];
    if (!row || row.length === 0) {
      skippedVRows++;
      continue;
    }
    const rawId = row[vIdIdx];
    if (rawId === null || rawId === undefined || String(rawId).trim() === "") {
      skippedVRows++;
      continue;
    }
    const id = String(rawId).trim();
    const cap = toNumber(row[vCapIdx]);
    if (cap === null || cap <= 0) {
      errors.push({
        sheet: vehicleSheet.name,
        field: "capacity",
        message: `第 ${i + 1} 行 "${id}" 容量无效 (${row[vCapIdx]})`,
      });
      continue;
    }
    vehicles.push({ id, capacity: cap });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  if (skippedVRows > 0) {
    warnings.push(`跳过 ${skippedVRows} 个空车辆行`);
  }
  if (vehicles.length === 0) {
    return {
      ok: false,
      errors: [
        { sheet: vehicleSheet.name, message: "车辆 sheet 没有任何有效数据行" },
      ],
    };
  }

  // Optional time windows
  if (twSheet && twSheet.rows && twSheet.rows.length > 1) {
    const twHeaders = twSheet.headers;
    const tIdIdx = findColumn(twHeaders, SIGNALS.customerId);
    const tStartIdx = findColumn(twHeaders, SIGNALS.twStart);
    const tEndIdx = findColumn(twHeaders, SIGNALS.twEnd);

    if (tIdIdx === -1 || tStartIdx === -1 || tEndIdx === -1) {
      warnings.push("时间窗 sheet 缺少必要列 (客户名 / 开始 / 结束) — 已忽略");
    } else {
      const byId = new Map(customers.map((c) => [c.id, c]));
      let unmatched = 0;
      for (let i = 1; i < twSheet.rows.length; i++) {
        const row = twSheet.rows[i];
        if (!row || row.length === 0) continue;
        const cid = row[tIdIdx];
        if (cid === null || cid === undefined || String(cid).trim() === "") continue;
        const customer = byId.get(String(cid).trim());
        if (!customer) {
          unmatched++;
          continue;
        }
        customer.time_window_start = toTimeString(row[tStartIdx]);
        customer.time_window_end = toTimeString(row[tEndIdx]);
      }
      if (unmatched > 0) {
        warnings.push(`时间窗 sheet 有 ${unmatched} 行未匹配到任何客户`);
      }
      const withoutTw = customers.filter((c) => c.time_window_start === null);
      if (withoutTw.length > 0) {
        warnings.push(
          `${withoutTw.length} 个客户没有时间窗 — 默认全天`,
        );
      }
    }
  }

  return {
    ok: true,
    payload: {
      task_type: "vrptw",
      customers,
      vehicles,
    },
    customer_count: customers.length,
    vehicle_count: vehicles.length,
    warnings,
  };
}
