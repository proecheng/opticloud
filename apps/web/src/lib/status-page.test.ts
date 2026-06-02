import { describe, expect, it } from "vitest";

import {
  buildRssXml,
  deriveOverallStatus,
  getOrderedIncidents,
  PUBLIC_STATUS_MODEL,
  type PublicIncident,
} from "./status-page";

describe("public status model", () => {
  it("derives overall status from the highest component severity", () => {
    expect(
      deriveOverallStatus([
        { ...PUBLIC_STATUS_MODEL.components[0], status: "operational" },
        { ...PUBLIC_STATUS_MODEL.components[1], status: "partial_outage" },
        { ...PUBLIC_STATUS_MODEL.components[2], status: "degraded_performance" },
      ]),
    ).toBe("partial_outage");

    expect(
      deriveOverallStatus(
        PUBLIC_STATUS_MODEL.components.map((component) => ({
          ...component,
          status: "operational",
        })),
      ),
    ).toBe("operational");
  });

  it("orders incidents in reverse chronological order", () => {
    const incidents = getOrderedIncidents([
      { ...PUBLIC_STATUS_MODEL.incidents[0], id: "older", started_at: "2026-05-01T00:00:00Z" },
      { ...PUBLIC_STATUS_MODEL.incidents[0], id: "newer", started_at: "2026-06-01T00:00:00Z" },
      { ...PUBLIC_STATUS_MODEL.incidents[0], id: "middle", started_at: "2026-05-20T00:00:00Z" },
    ]);

    expect(incidents.map((incident) => incident.id)).toEqual(["newer", "middle", "older"]);
  });

  it("builds RSS from the same ordered incident data and escapes XML fields", () => {
    const incidents: PublicIncident[] = [
      {
        ...PUBLIC_STATUS_MODEL.incidents[0],
        id: "inc-xml",
        title: "API & Solver <degraded> \"quoted\"",
        summary: "Auth's queue used <unsafe> & chars",
        started_at: "2026-06-01T00:00:00Z",
      },
      {
        ...PUBLIC_STATUS_MODEL.incidents[0],
        id: "inc-old",
        title: "Older incident",
        started_at: "2026-05-01T00:00:00Z",
      },
    ];

    const xml = buildRssXml({
      ...PUBLIC_STATUS_MODEL,
      incidents,
    });

    expect(xml).toContain("<rss version=\"2.0\">");
    expect(xml.indexOf("inc-xml")).toBeLessThan(xml.indexOf("inc-old"));
    expect(xml).toContain("API &amp; Solver &lt;degraded&gt; &quot;quoted&quot;");
    expect(xml).toContain("Auth&apos;s queue used &lt;unsafe&gt; &amp; chars");
    expect(xml).not.toContain("<degraded>");
    expect(xml).not.toContain("<unsafe>");
  });
});
