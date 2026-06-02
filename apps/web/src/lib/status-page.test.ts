import { describe, expect, it } from "vitest";

import {
  buildPostmortemMermaidTimeline,
  buildRssXml,
  deriveOverallStatus,
  getPublishedP0Postmortem,
  getOrderedIncidents,
  isPostmortemDueExactly24h,
  isPostmortemPublishedWithinSla,
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

  it("finds only published P0 postmortems by incident id", () => {
    const incident = getPublishedP0Postmortem(
      PUBLIC_STATUS_MODEL,
      "inc-2026-05-28-deepseek-provider-fallback",
    );

    expect(incident?.postmortem).toBeDefined();
    expect(incident?.severity).toBe("critical");
    expect(incident?.postmortem?.public_url_path).toBe(
      "/status/incidents/inc-2026-05-28-deepseek-provider-fallback",
    );
    expect(getPublishedP0Postmortem(PUBLIC_STATUS_MODEL, "inc-2026-06-02-solver-latency")).toBe(
      null,
    );
    expect(
      getPublishedP0Postmortem(
        {
          ...PUBLIC_STATUS_MODEL,
          incidents: [
            {
              ...PUBLIC_STATUS_MODEL.incidents[0],
              severity: "critical",
            },
          ],
        },
        "inc-2026-06-02-solver-latency",
      ),
    ).toBe(null);
    expect(getPublishedP0Postmortem(PUBLIC_STATUS_MODEL, "missing")).toBe(null);
  });

  it("checks postmortem publication against the 24h due timestamp", () => {
    const incident = getPublishedP0Postmortem(
      PUBLIC_STATUS_MODEL,
      "inc-2026-05-28-deepseek-provider-fallback",
    );

    expect(incident).not.toBeNull();
    const publishedIncident = incident!;
    expect(isPostmortemDueExactly24h(publishedIncident)).toBe(true);
    expect(isPostmortemPublishedWithinSla(publishedIncident)).toBe(true);
    expect(
      isPostmortemPublishedWithinSla({
        ...publishedIncident,
        postmortem: {
          ...publishedIncident.postmortem!,
          published_at: "2026-05-29T19:14:01Z",
        },
      }),
    ).toBe(false);
    expect(
      isPostmortemDueExactly24h({
        ...publishedIncident,
        postmortem: {
          ...publishedIncident.postmortem!,
          publish_due_at: "2026-05-30T19:14:00Z",
        },
      }),
    ).toBe(false);
    expect(
      isPostmortemPublishedWithinSla({
        ...publishedIncident,
        postmortem: {
          ...publishedIncident.postmortem!,
          publish_due_at: "2026-05-30T19:14:00Z",
          published_at: "2026-05-29T19:14:01Z",
        },
      }),
    ).toBe(false);
  });

  it("builds a Mermaid timeline from ordered canonical events and sanitizes labels", () => {
    const incident = getPublishedP0Postmortem(
      {
        ...PUBLIC_STATUS_MODEL,
        incidents: [
          {
            ...PUBLIC_STATUS_MODEL.incidents[0],
            id: "inc-2026-06-02-solver-latency",
            severity: "critical",
            postmortem: {
              public_url_path: "/status/incidents/inc-2026-06-02-solver-latency",
              p0_declared_at: "2026-05-28T19:14:00Z",
              publish_due_at: "2026-05-29T19:14:00Z",
              published_at: "2026-05-29T18:00:00Z",
              sections: {
                what_happened: "Public summary",
                impact: "Public impact",
                detection: "Public detection",
                mitigation: "Public mitigation",
                root_cause: "Public root cause",
              },
              timeline: [
                {
                  id: "later",
                  occurred_at: "2026-05-28T19:20:00Z",
                  label: "Mitigation \"confirmed\"",
                  description: "Fallback <active> | monitoring",
                },
                {
                  id: "earlier",
                  occurred_at: "2026-05-28T19:10:00Z",
                  label: "Alert [started]",
                  description: "Provider\nhealth failed",
                },
              ],
              follow_ups: [],
            },
          },
        ],
      },
      "inc-2026-06-02-solver-latency",
    );

    const mermaid = buildPostmortemMermaidTimeline(incident!);

    expect(mermaid.startsWith("timeline")).toBe(true);
    expect(mermaid.indexOf("Alert started")).toBeLessThan(
      mermaid.indexOf("Mitigation confirmed"),
    );
    expect(mermaid).not.toContain("\"");
    expect(mermaid).not.toContain("<active>");
    expect(mermaid).not.toContain("|");
    expect(mermaid).not.toContain("[started]");
    expect(mermaid).not.toContain("\nhealth");
  });
});
