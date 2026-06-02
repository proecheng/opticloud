import { describe, expect, it } from "vitest";

import {
  buildSecurityTxt,
  SECURITY_DISCLOSURE_POLICY,
  securityTxtExpiresWithinOneYear,
} from "./security-disclosure";

describe("security disclosure policy", () => {
  it("builds RFC 9116 security.txt from the shared policy model", () => {
    const txt = buildSecurityTxt(SECURITY_DISCLOSURE_POLICY);

    expect(txt).toContain("Contact: mailto:security@opticloud.cn");
    expect(txt).toContain("Policy: https://opticloud.cn/security");
    expect(txt).toContain("Canonical: https://opticloud.cn/.well-known/security.txt");
    expect(txt).toContain("Preferred-Languages: zh, en");
    expect(txt).toContain("Expires: 2026-12-03T00:00:00Z");
    expect(txt).not.toContain("Encryption:");
  });

  it("keeps the public SLA and report requirements explicit", () => {
    expect(SECURITY_DISCLOSURE_POLICY.sla.acknowledgement_hours).toBe(48);
    expect(SECURITY_DISCLOSURE_POLICY.sla.cvss_high_patch_days).toBe(7);
    expect(SECURITY_DISCLOSURE_POLICY.sla.internal_critical_hotfix_hours).toBe(24);
    expect(securityTxtExpiresWithinOneYear(SECURITY_DISCLOSURE_POLICY)).toBe(true);

    expect(SECURITY_DISCLOSURE_POLICY.required_fields.map((field) => field.id)).toEqual([
      "affected-surface",
      "impact",
      "reproduction-or-poc",
      "cvss-estimate",
      "reporter-contact",
    ]);
  });

  it("defines safe-harbor boundaries and future-policy exclusions", () => {
    const safeHarborIds = SECURITY_DISCLOSURE_POLICY.safe_harbor.map((item) => item.id);
    expect(safeHarborIds).toEqual([
      "minimal-proof",
      "no-data-exfiltration",
      "no-destructive-testing",
      "no-persistence",
      "no-social-engineering",
      "no-ddos",
      "synthetic-data",
    ]);

    const futureIds = SECURITY_DISCLOSURE_POLICY.future_policy_items.map((item) => item.id);
    expect(futureIds).toEqual([
      "duplicate-disclosure",
      "reward-eligibility",
      "public-acknowledgement",
      "pgp-fallback",
      "cve-tracking",
    ]);
  });
});
