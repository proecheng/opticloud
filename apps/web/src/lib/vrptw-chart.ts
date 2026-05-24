import type { EChartsOption } from "echarts";

import type { VRPTWPayload } from "./vrptw-template";

export type VrptwChartMode = "derived_preview" | "solver_route";
export type VrptwChartSource = "vrptw_payload" | "solver_route_data";

export interface VrptwChartContract {
  mode: VrptwChartMode;
  source: VrptwChartSource;
}

export interface VrptwSolverRouteStop {
  customerId: string;
  vehicleId: string;
  sequence: number;
  lat: number;
  lng: number;
  demand?: number | null;
  arrivalMinutes?: number | null;
  departureMinutes?: number | null;
  serviceMinutes?: number | null;
}

export interface VrptwSolverRouteData {
  depot?: { lat: number; lng: number };
  stops: VrptwSolverRouteStop[];
}

export type VrptwChartRequest =
  | { mode?: "derived_preview"; source?: "vrptw_payload" }
  | {
      mode: "solver_route";
      source: "solver_route_data";
      routeData: VrptwSolverRouteData;
    };

export interface VrptwChartImage {
  base64: string;
  extension: "png";
  position: {
    tl: { col: number; row: number };
    ext: { width: number; height: number };
  };
}

export interface VrptwChartArtifact {
  sheetName: string;
  contract: VrptwChartContract;
  sheetRows: unknown[][];
  images: VrptwChartImage[];
}

interface DerivedTimelineRow {
  label: string;
  vehicleLabel: string;
  vehicleIndex: number;
  start: number;
  duration: number;
  end: number;
  customerId: string;
}

interface DerivedPoint {
  customerId: string;
  lat: number;
  lng: number;
  demand: number;
  vehicleLabel: string;
  vehicleIndex: number;
}

interface DerivedModel {
  depot: { lat: number; lng: number };
  customers: DerivedPoint[];
  timelineRows: DerivedTimelineRow[];
  vehicleLabels: string[];
}

interface ChartCallbackParams {
  data?: unknown;
  dataIndex?: number;
}

const CHART_SHEET_NAME = "Chart Preview";
const PNG_EXT = "png" as const;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function parseClockToMinutes(value: string | null | undefined): number | null {
  if (!value) return null;
  const match = /^(\d{1,2}):(\d{2})/.exec(value.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function fallbackDuration(
  customer: VRPTWPayload["customers"][number],
  index: number,
): number {
  const service = customer.service_minutes ?? 0;
  if (service > 0) return service;
  return Math.max(10, Math.round((customer.demand || 1) * 1.5) + index * 2);
}

export function buildVrptwDerivedModel(payload: VRPTWPayload): DerivedModel {
  const vehicleLabels = payload.vehicles.map(
    (vehicle, index) => vehicle.id || `V${index + 1}`,
  );
  const safeVehicleCount = Math.max(1, vehicleLabels.length);

  const customers = payload.customers.map((customer, index) => {
    const vehicleIndex = index % safeVehicleCount;
    return {
      customerId: customer.id,
      lat: customer.lat,
      lng: customer.lng,
      demand: customer.demand,
      vehicleLabel: vehicleLabels[vehicleIndex] ?? `V${vehicleIndex + 1}`,
      vehicleIndex,
    };
  });

  const latValues = customers.map((c) => c.lat);
  const lngValues = customers.map((c) => c.lng);
  const depotLat =
    latValues.length > 0
      ? latValues.reduce((sum, value) => sum + value, 0) / latValues.length
      : 0;
  const depotLng =
    lngValues.length > 0
      ? lngValues.reduce((sum, value) => sum + value, 0) / lngValues.length
      : 0;

  const timelineRows: DerivedTimelineRow[] = payload.customers.map(
    (customer, index) => {
      const vehicleIndex = index % safeVehicleCount;
      const vehicleLabel =
        vehicleLabels[vehicleIndex] ?? `V${vehicleIndex + 1}`;
      const label = `${vehicleLabel} · ${customer.id}`;
      const explicitStart = parseClockToMinutes(customer.time_window_start);
      const explicitEnd = parseClockToMinutes(customer.time_window_end);
      const duration = fallbackDuration(customer, index);
      const start =
        explicitStart ??
        (explicitEnd !== null
          ? Math.max(0, explicitEnd - duration)
          : index * 25 + vehicleIndex * 7);
      const end = start + duration;

      return {
        label,
        vehicleLabel,
        vehicleIndex,
        start,
        duration,
        end,
        customerId: customer.id,
      };
    },
  );

  return {
    depot: { lat: depotLat, lng: depotLng },
    customers,
    timelineRows: timelineRows.sort(
      (a, b) => a.start - b.start || a.vehicleIndex - b.vehicleIndex,
    ),
    vehicleLabels: vehicleLabels.length > 0 ? vehicleLabels : ["V1"],
  };
}

function buildVrptwSolverRouteModel(routeData: VrptwSolverRouteData): DerivedModel {
  if (routeData.stops.length === 0) {
    throw new Error("solver_route chart requires at least one route stop");
  }

  const vehicleLabels = Array.from(
    new Set(routeData.stops.map((stop) => stop.vehicleId)),
  );
  const vehicleIndexById = new Map(
    vehicleLabels.map((vehicleId, index) => [vehicleId, index]),
  );

  const customers = routeData.stops.map((stop) => ({
    customerId: stop.customerId,
    lat: stop.lat,
    lng: stop.lng,
    demand: stop.demand ?? 0,
    vehicleLabel: stop.vehicleId,
    vehicleIndex: vehicleIndexById.get(stop.vehicleId) ?? 0,
  }));

  const depot =
    routeData.depot ??
    (() => {
      const lat =
        customers.reduce((sum, customer) => sum + customer.lat, 0) /
        customers.length;
      const lng =
        customers.reduce((sum, customer) => sum + customer.lng, 0) /
        customers.length;
      return { lat, lng };
    })();

  const timelineRows = routeData.stops
    .map((stop) => {
      const vehicleIndex = vehicleIndexById.get(stop.vehicleId) ?? 0;
      const start =
        stop.arrivalMinutes ?? Math.max(0, (stop.sequence - 1) * 25);
      const duration =
        stop.serviceMinutes ??
        (stop.departureMinutes !== null && stop.departureMinutes !== undefined
          ? Math.max(1, stop.departureMinutes - start)
          : 10);
      return {
        label: `${stop.vehicleId} · ${stop.customerId}`,
        vehicleLabel: stop.vehicleId,
        vehicleIndex,
        start,
        duration,
        end: start + duration,
        customerId: stop.customerId,
      };
    })
    .sort((a, b) => a.start - b.start || a.vehicleIndex - b.vehicleIndex);

  return {
    depot,
    customers,
    timelineRows,
    vehicleLabels,
  };
}

function resolveChartInput(
  payload: VRPTWPayload,
  request?: VrptwChartRequest,
): { contract: VrptwChartContract; model: DerivedModel } {
  if (request?.mode === "solver_route") {
    return {
      contract: { mode: "solver_route", source: "solver_route_data" },
      model: buildVrptwSolverRouteModel(request.routeData),
    };
  }

  return {
    contract: { mode: "derived_preview", source: "vrptw_payload" },
    model: buildVrptwDerivedModel(payload),
  };
}

function buildScatterOption(model: DerivedModel): EChartsOption {
  const palette = [
    "#2D5BA8",
    "#4A77BB",
    "#1F3A68",
    "#5F8DD3",
    "#7CA8E6",
    "#335C99",
  ];

  const vehicleSeries = model.vehicleLabels.map(
    (vehicleLabel, vehicleIndex) => ({
      name: vehicleLabel,
      type: "scatter" as const,
      coordinateSystem: "cartesian2d" as const,
      data: model.customers
        .filter((customer) => customer.vehicleIndex === vehicleIndex)
        .map((customer) => [
          customer.lng,
          customer.lat,
          customer.customerId,
          customer.demand,
        ]),
      symbolSize: (value: unknown) => {
        const demand = Array.isArray(value) ? Number(value[3] ?? 0) : 0;
        return Math.max(10, Math.min(20, 10 + demand / 4));
      },
      itemStyle: {
        color: palette[vehicleIndex % palette.length],
      },
      label: {
        show: true,
        formatter: (params: ChartCallbackParams) => {
          const data = Array.isArray(params.data) ? params.data : [];
          return String(data[2] ?? "");
        },
        position: "top" as const,
        fontSize: 10,
      },
      emphasis: {
        scale: true,
      },
    }),
  );

  return {
    backgroundColor: "#ffffff",
    title: {
      text: "VRPTW 客户散点 / 车辆分组",
      subtext: "Derived preview from payload",
      left: "center",
      textStyle: {
        fontSize: 18,
        fontWeight: 600,
        color: "#1f2937",
      },
      subtextStyle: {
        color: "#6b7280",
      },
    },
    tooltip: {
      trigger: "item",
    },
    legend: {
      top: 32,
      left: "center",
      data: ["Depot", ...model.vehicleLabels],
    },
    grid: {
      left: 56,
      right: 24,
      top: 78,
      bottom: 40,
    },
    xAxis: {
      type: "value",
      name: "Lng",
      nameLocation: "middle",
      nameGap: 28,
      splitLine: {
        lineStyle: { color: "#e5e7eb" },
      },
    },
    yAxis: {
      type: "value",
      name: "Lat",
      nameLocation: "middle",
      nameGap: 38,
      splitLine: {
        lineStyle: { color: "#e5e7eb" },
      },
    },
    series: [
      {
        name: "Depot",
        type: "scatter" as const,
        data: [[model.depot.lng, model.depot.lat, "Depot"]],
        symbolSize: 18,
        itemStyle: {
          color: "#111827",
        },
        label: {
          show: true,
          formatter: "Depot",
          position: "right",
          fontWeight: 600,
        },
      },
      ...vehicleSeries,
    ],
  };
}

function buildTimelineOption(model: DerivedModel): EChartsOption {
  const categories = model.timelineRows.map((row) => row.label);
  const palette = [
    "#2D5BA8",
    "#4A77BB",
    "#1F3A68",
    "#5F8DD3",
    "#7CA8E6",
    "#335C99",
  ];

  return {
    backgroundColor: "#ffffff",
    title: {
      text: "VRPTW 路线时间轴 / 任务顺序",
      subtext: "Derived preview from payload",
      left: "center",
      textStyle: {
        fontSize: 18,
        fontWeight: 600,
        color: "#1f2937",
      },
      subtextStyle: {
        color: "#6b7280",
      },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    legend: {
      top: 32,
      left: "center",
      data: ["Wait", "Service"],
    },
    grid: {
      left: 120,
      right: 24,
      top: 78,
      bottom: 36,
    },
    xAxis: {
      type: "value",
      name: "Minutes",
      nameLocation: "middle",
      nameGap: 26,
      splitLine: {
        lineStyle: { color: "#e5e7eb" },
      },
    },
    yAxis: {
      type: "category",
      data: categories,
      axisLabel: {
        width: 110,
        overflow: "truncate",
      },
    },
    series: [
      {
        name: "Wait",
        type: "bar" as const,
        stack: "total",
        silent: true,
        itemStyle: {
          color: "rgba(0,0,0,0)",
        },
        emphasis: {
          disabled: true,
        },
        data: model.timelineRows.map((row) => row.start),
      },
      {
        name: "Service",
        type: "bar" as const,
        stack: "total",
        data: model.timelineRows.map((row) => row.duration),
        label: {
          show: true,
          position: "insideRight",
          formatter: (params: ChartCallbackParams) => {
            const row = model.timelineRows[Number(params.dataIndex ?? 0)];
            return row?.customerId ?? "";
          },
          color: "#111827",
          fontSize: 10,
        },
        itemStyle: {
          color: (params: ChartCallbackParams) => {
            const row = model.timelineRows[Number(params.dataIndex ?? 0)];
            return palette[(row?.vehicleIndex ?? 0) % palette.length];
          },
        },
      },
    ],
  };
}

async function renderChartPng(
  option: EChartsOption,
  width: number,
  height: number,
): Promise<string> {
  if (typeof document === "undefined") {
    throw new Error("chart embedding requires a browser-like DOM");
  }

  const echarts = await import("echarts");
  const host = document.createElement("div");
  host.style.position = "absolute";
  host.style.left = "-10000px";
  host.style.top = "0";
  host.style.width = `${width}px`;
  host.style.height = `${height}px`;
  host.style.pointerEvents = "none";
  document.body.appendChild(host);

  const chart = echarts.init(host, undefined, {
    renderer: "canvas",
    width,
    height,
    devicePixelRatio: 2,
  });

  try {
    chart.setOption({ ...option, animation: false }, true);
    await new Promise<void>((resolve) => {
      const timeout = window.setTimeout(() => resolve(), 30);
      chart.on("finished", () => {
        window.clearTimeout(timeout);
        resolve();
      });
    });
    return chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: "#ffffff",
    });
  } finally {
    chart.dispose();
    host.remove();
  }
}

export async function buildVrptwChartArtifact(
  payload: VRPTWPayload,
  request?: VrptwChartRequest,
): Promise<VrptwChartArtifact> {
  const { contract, model } = resolveChartInput(payload, request);
  const scatterBase64 = await renderChartPng(
    buildScatterOption(model),
    840,
    320,
  );
  const timelineBase64 = await renderChartPng(
    buildTimelineOption(model),
    840,
    320,
  );

  return {
    sheetName: CHART_SHEET_NAME,
    contract,
    sheetRows: [
      ["VRPTW Chart Preview"],
      ["chart_mode", contract.mode],
      ["chart_source", contract.source],
      [
        "chart_note",
        contract.mode === "derived_preview"
          ? "Derived from VRPTW payload. Preview only; not solver route output."
          : "Solver-backed preview.",
      ],
      ["depot_lat", Number(model.depot.lat.toFixed(4))],
      ["depot_lng", Number(model.depot.lng.toFixed(4))],
      ["vehicle_count", model.vehicleLabels.length],
      ["customer_count", model.customers.length],
      [],
      ["Scatter preview"],
      [
        "Customers are assigned to vehicles in a deterministic round-robin preview.",
      ],
      [],
      ["Timeline preview"],
      [
        "Uses time windows when available; otherwise falls back to deterministic service windows.",
      ],
    ],
    images: [
      {
        base64: scatterBase64,
        extension: PNG_EXT,
        position: {
          tl: { col: 0, row: 9 },
          ext: { width: 840, height: 320 },
        },
      },
      {
        base64: timelineBase64,
        extension: PNG_EXT,
        position: {
          tl: { col: 0, row: 25 },
          ext: { width: 840, height: 320 },
        },
      },
    ],
  };
}
