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
  postmortem?: PublicPostmortem;
}

export type PublicPostmortemFollowUpStatus = "todo" | "in_progress" | "done";

export interface PublicPostmortemTimelineEvent {
  id: string;
  occurred_at: string;
  label: string;
  description: string;
}

export interface PublicPostmortemFollowUp {
  id: string;
  title: string;
  owner: string;
  status: PublicPostmortemFollowUpStatus;
}

export interface PublicPostmortemSections {
  what_happened: string;
  impact: string;
  detection: string;
  mitigation: string;
  root_cause: string;
}

export interface PublicPostmortem {
  public_url_path: string;
  p0_declared_at: string;
  publish_due_at: string;
  published_at: string;
  sections: PublicPostmortemSections;
  timeline: PublicPostmortemTimelineEvent[];
  follow_ups: PublicPostmortemFollowUp[];
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

const POSTMORTEM_SLA_MS = 24 * 60 * 60 * 1000;

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
      id: "inc-2026-05-28-deepseek-provider-fallback",
      title: "DeepSeek provider outage and emergency fallback",
      severity: "critical",
      status: "resolved",
      summary:
        "DeepSeek-backed natural-language flows degraded, and the incident fallback path was activated while the provider recovered.",
      started_at: "2026-05-28T19:12:00Z",
      resolved_at: "2026-05-28T22:45:00Z",
      affected_component_ids: ["chat"],
      postmortem: {
        public_url_path: "/status/incidents/inc-2026-05-28-deepseek-provider-fallback",
        p0_declared_at: "2026-05-28T19:14:00Z",
        publish_due_at: "2026-05-29T19:14:00Z",
        published_at: "2026-05-29T18:02:00Z",
        sections: {
          what_happened:
            "Provider health checks detected sustained DeepSeek degradation. OptiCloud declared a P0 for the affected natural-language path and activated the emergency fallback workflow.",
          impact:
            "A subset of Chat and NL-assisted optimization preparation requests saw elevated latency or failed attempts while the fallback path was being confirmed.",
          detection:
            "The incident was detected through provider health monitoring and confirmed by SRE review of public-safe service indicators.",
          mitigation:
            "SRE shifted affected NL flows to the Qwen-Max incident fallback path, kept the public status record updated, and monitored recovery until DeepSeek health stabilized.",
          root_cause:
            "The proximate cause was upstream provider unavailability. Internal routing and fallback evidence did not show data loss or billing ledger inconsistency.",
        },
        timeline: [
          {
            id: "incident-started",
            occurred_at: "2026-05-28T19:12:00Z",
            label: "Incident started",
            description: "DeepSeek-backed NL requests began showing elevated failures.",
          },
          {
            id: "provider-health-failed",
            occurred_at: "2026-05-28T19:12:20Z",
            label: "Provider health failed",
            description: "Provider health checks marked the DeepSeek path failed.",
          },
          {
            id: "p0-declared",
            occurred_at: "2026-05-28T19:14:00Z",
            label: "P0 declared",
            description: "SRE declared a P0 provider incident.",
          },
          {
            id: "fallback-confirmed",
            occurred_at: "2026-05-28T19:17:30Z",
            label: "Fallback confirmed",
            description: "Qwen-Max incident fallback was confirmed for affected flows.",
          },
          {
            id: "status-monitoring",
            occurred_at: "2026-05-28T22:45:00Z",
            label: "Resolved",
            description: "DeepSeek health stabilized and the incident moved to resolved.",
          },
          {
            id: "postmortem-published",
            occurred_at: "2026-05-29T18:02:00Z",
            label: "Postmortem published",
            description: "Public P0 postmortem published within the 24h SLA.",
          },
        ],
        follow_ups: [
          {
            id: "j3-evidence-archive",
            title: "Attach redacted provider-health and fallback evidence to the incident archive",
            owner: "SRE",
            status: "in_progress",
          },
          {
            id: "compensation-review",
            title: "Review compensation eligibility for confirmed affected accounts",
            owner: "Billing",
            status: "todo",
          },
        ],
      },
    },
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

export function getOrderedPostmortemTimeline(
  incident: PublicIncident,
): PublicPostmortemTimelineEvent[] {
  return [...(incident.postmortem?.timeline ?? [])].sort((left, right) => {
    return Date.parse(left.occurred_at) - Date.parse(right.occurred_at);
  });
}

export function getPublishedP0Postmortem(
  model: PublicStatusModel,
  incidentId: string,
): PublicIncident | null {
  const incident = model.incidents.find((candidate) => candidate.id === incidentId);
  if (!incident || incident.severity !== "critical" || !incident.postmortem) {
    return null;
  }
  if (incident.postmortem.public_url_path !== `/status/incidents/${incident.id}`) {
    return null;
  }
  return incident;
}

export function isPostmortemDueExactly24h(incident: PublicIncident): boolean {
  if (!incident.postmortem) return false;
  const declared = Date.parse(incident.postmortem.p0_declared_at);
  const due = Date.parse(incident.postmortem.publish_due_at);
  if (Number.isNaN(declared) || Number.isNaN(due)) return false;
  return due - declared === POSTMORTEM_SLA_MS;
}

export function isPostmortemPublishedWithinSla(incident: PublicIncident): boolean {
  if (!incident.postmortem) return false;
  if (!isPostmortemDueExactly24h(incident)) return false;
  return (
    Date.parse(incident.postmortem.published_at) <=
    Date.parse(incident.postmortem.publish_due_at)
  );
}

function sanitizeMermaidLabel(value: string): string {
  return value
    .replace(/[\r\n]+/g, " ")
    .replace(/[<>"'[\]{}()|:;`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function buildPostmortemMermaidTimeline(incident: PublicIncident): string {
  const events = getOrderedPostmortemTimeline(incident).map((event) => {
    const timestamp = new Date(event.occurred_at).toISOString().replace(".000Z", "Z");
    const label = sanitizeMermaidLabel(event.label);
    const description = sanitizeMermaidLabel(event.description);
    return `  ${timestamp} : ${label} - ${description}`;
  });
  return ["timeline", ...events].join("\n");
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
