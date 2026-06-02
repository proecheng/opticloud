import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("security.txt route", () => {
  it("returns public RFC 9116 text without overclaiming unsupported intake automation", async () => {
    const response = await GET();
    const body = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/plain; charset=utf-8");
    expect(body).toContain("Contact: mailto:security@opticloud.cn");
    expect(body).toContain("Policy: https://opticloud.cn/security");
    expect(body).toContain("Canonical: https://opticloud.cn/.well-known/security.txt");
    expect(body).toContain("Preferred-Languages: zh, en");
    expect(body).toContain("Expires: 2026-12-03T00:00:00Z");
    expect(body).not.toContain("Encryption:");
    expect(body).not.toContain("Ticket");
    expect(body).not.toContain("Bounty");
    expect(body).not.toContain("CVE");
  });
});
