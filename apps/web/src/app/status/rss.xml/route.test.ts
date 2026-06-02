import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("status RSS route", () => {
  it("returns public RSS XML with incident items and content type", async () => {
    const response = await GET();
    const body = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/rss+xml");
    expect(body).toContain("<rss version=\"2.0\">");
    expect(body).toContain("<channel>");
    expect(body).toContain("Solver queue latency above target");
    expect(body.indexOf("Solver queue latency above target")).toBeLessThan(
      body.indexOf("Capability registry maintenance window"),
    );
  });
});
