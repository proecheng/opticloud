export type PublicComponentStatus =
  | "operational"
  | "degraded_performance"
  | "partial_outage"
  | "major_outage";

export type PublicIncidentStatus = "investigating" | "identified" | "monitoring" | "resolved";

export type PublicIncidentSeverity = "minor" | "major" | "critical";

export interface PublicStatusComponent {
  id: string;
  label: string;
  status: PublicComponentStatus;
  description: string;
  updated_at: string;
}

export interface PublicIncident {
  id: string;
  title: string;
  severity: PublicIncidentSeverity;
  status: PublicIncidentStatus;
  summary: string;
  started_at: string;
  resolved_at: string | null;
  affected_component_ids: string[];
}

export interface PublicStatusModel {
  generated_at: string;
  components: PublicStatusComponent[];
  incidents: PublicIncident[];
}

const STATUS_RANK: Record<PublicComponentStatus, number> = {
  operational: 0,
  degraded_performance: 1,
  partial_outage: 2,
  major_outage: 3,
};

export const STATUS_LABELS: Record<PublicComponentStatus, string> = {
  operational: "Operational",
  degraded_performance: "Degraded performance",
  partial_outage: "Partial outage",
  major_outage: "Major outage",
};

export const INCIDENT_STATUS_LABELS: Record<PublicIncidentStatus, string> = {
  investigating: "Investigating",
  identified: "Identified",
  monitoring: "Monitoring",
  resolved: "Resolved",
};

export const PUBLIC_STATUS_MODEL: PublicStatusModel = {
  generated_at: "2026-06-02T12:00:00Z",
  components: [
    {
      id: "api-gateway",
      label: "API Gateway",
      status: "operational",
      description: "Public API ingress, rate-limit envelope, and request routing.",
      updated_at: "2026-06-02T12:00:00Z",
    },
    {
      id: "auth",
      label: "Auth",
      status: "operational",
      description: "Signup, login, OTP, API key issuance, and account controls.",
      updated_at: "2026-06-02T12:00:00Z",
    },
    {
      id: "solver-orchestrator",
      label: "Solver Orchestrator",
      status: "degraded_performance",
      description: "Optimization and forecasting job admission, queueing, and execution.",
      updated_at: "2026-06-02T11:45:00Z",
    },
    {
      id: "billing",
      label: "Billing",
      status: "operational",
      description: "Credits reservation, finalization, refunds, invoices, and budgets.",
      updated_at: "2026-06-02T12:00:00Z",
    },
    {
      id: "chat",
      label: "Chat",
      status: "operational",
      description: "Natural-language analysis, file context, and streaming assistant flows.",
      updated_at: "2026-06-02T12:00:00Z",
    },
    {
      id: "capability-registry",
      label: "Capability Registry",
      status: "operational",
      description: "Algorithm catalog, provider capability metadata, and provider dashboards.",
      updated_at: "2026-06-02T12:00:00Z",
    },
  ],
  incidents: [
    {
      id: "inc-2026-06-02-solver-latency",
      title: "Solver queue latency above target",
      severity: "minor",
      status: "monitoring",
      summary:
        "LP and prediction jobs are completing, but queue admission latency is above the public target for a subset of requests.",
      started_at: "2026-06-02T09:20:00Z",
      resolved_at: null,
      affected_component_ids: ["solver-orchestrator"],
    },
    {
      id: "inc-2026-05-29-capability-maintenance",
      title: "Capability registry maintenance window",
      severity: "minor",
      status: "resolved",
      summary:
        "Provider dashboard read models were temporarily unavailable during planned maintenance.",
      started_at: "2026-05-29T02:00:00Z",
      resolved_at: "2026-05-29T02:30:00Z",
      affected_component_ids: ["capability-registry"],
    },
  ],
};

export function deriveOverallStatus(
  components: readonly PublicStatusComponent[],
): PublicComponentStatus {
  return components.reduce<PublicComponentStatus>((current, component) => {
    return STATUS_RANK[component.status] > STATUS_RANK[current] ? component.status : current;
  }, "operational");
}

export function getOrderedIncidents(
  incidents: readonly PublicIncident[] = PUBLIC_STATUS_MODEL.incidents,
): PublicIncident[] {
  return [...incidents].sort((left, right) => {
    return Date.parse(right.started_at) - Date.parse(left.started_at);
  });
}

export function componentLabelsForIncident(
  incident: PublicIncident,
  components: readonly PublicStatusComponent[] = PUBLIC_STATUS_MODEL.components,
): string {
  const labels = incident.affected_component_ids.map((id) => {
    return components.find((component) => component.id === id)?.label ?? id;
  });
  return labels.join(", ");
}

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function rssItem(incident: PublicIncident, model: PublicStatusModel): string {
  const affected = componentLabelsForIncident(incident, model.components);
  const description = `${incident.summary} Affected components: ${affected}. Status: ${
    INCIDENT_STATUS_LABELS[incident.status]
  }.`;
  return [
    "    <item>",
    `      <guid isPermaLink="false">${escapeXml(incident.id)}</guid>`,
    `      <title>${escapeXml(incident.title)}</title>`,
    `      <link>https://status.opticloud.cn/status#${escapeXml(incident.id)}</link>`,
    `      <description>${escapeXml(description)}</description>`,
    `      <pubDate>${new Date(incident.started_at).toUTCString()}</pubDate>`,
    "    </item>",
  ].join("\n");
}

export function buildRssXml(model: PublicStatusModel = PUBLIC_STATUS_MODEL): string {
  const incidents = getOrderedIncidents(model.incidents);
  const overall = deriveOverallStatus(model.components);
  const items = incidents.map((incident) => rssItem(incident, model)).join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0">',
    "  <channel>",
    "    <title>OptiCloud Status</title>",
    "    <link>https://status.opticloud.cn/status</link>",
    `    <description>${escapeXml(
      `Public OptiCloud status and incident history. Current status: ${STATUS_LABELS[overall]}.`,
    )}</description>`,
    `    <lastBuildDate>${new Date(model.generated_at).toUTCString()}</lastBuildDate>`,
    items,
    "  </channel>",
    "</rss>",
  ].join("\n");
}
