import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  buildSecurityTxt,
  buildJ9WhitehatMermaid,
  J9_WHITEHAT_FLOW,
  J9_WHITEHAT_HARDENINGS,
  J9_WHITEHAT_SOP_STEPS,
  SECURITY_DISCLOSURE_POLICY,
  securityTxtExpiresWithinOneYear,
  type J9WhitehatFlow,
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

  it("models the UX-DR7 J9 whitehat flow with stable nodes and branches", () => {
    expect(J9_WHITEHAT_FLOW.nodes.map((node) => node.id)).toEqual([
      "discover-api",
      "read-security-txt",
      "find-security-mailbox",
      "discover-vulnerability",
      "disclosure-type",
      "responsible-disclosure",
      "ordinary-bug-report",
      "academic-disclosure",
      "national-apt-escalation",
      "future-platform",
      "acknowledgement-ticket",
      "email-received",
      "email-fallback",
      "security-team-confirm",
      "triage",
      "cvss-high-patch",
      "cvss-medium-patch",
      "public-acknowledgement",
      "duplicate-disclosure",
      "first-disclosure-reward",
      "duplicate-thanks",
    ]);
    expect(J9_WHITEHAT_FLOW.edges).toContainEqual({
      from: "disclosure-type",
      to: "responsible-disclosure",
      label: "responsible security disclosure",
    });
    expect(J9_WHITEHAT_FLOW.edges).toContainEqual({
      from: "disclosure-type",
      to: "ordinary-bug-report",
      label: "ordinary product bug",
    });
    expect(J9_WHITEHAT_FLOW.edges).toContainEqual({
      from: "email-received",
      to: "email-fallback",
      label: "no",
    });
    expect(J9_WHITEHAT_FLOW.edges).toContainEqual({
      from: "triage",
      to: "cvss-high-patch",
      label: "CVSS >= 7.0",
    });

    const nodeIds = new Set(J9_WHITEHAT_FLOW.nodes.map((node) => node.id));
    for (const edge of J9_WHITEHAT_FLOW.edges) {
      expect(nodeIds.has(edge.from)).toBe(true);
      expect(nodeIds.has(edge.to)).toBe(true);
      expect(edge.label.trim()).toBe(edge.label);
      expect(edge.label).not.toHaveLength(0);
    }
  });

  it("builds deterministic sanitized Mermaid source from the typed J9 flow", () => {
    const mermaid = buildJ9WhitehatMermaid(J9_WHITEHAT_FLOW);

    expect(mermaid.startsWith("graph TD")).toBe(true);
    expect(mermaid).toContain("discover-api[Researcher scans API v1 surface]");
    expect(mermaid).toContain(
      "disclosure-type -->|responsible security disclosure| responsible-disclosure",
    );
    expect(mermaid).toContain("triage -->|CVSS >= 7.0| cvss-high-patch");

    const unsafeFlow: J9WhitehatFlow = {
      nodes: [
        { id: "a", label: "A [bad] <node> | quoted", status: "active" },
        { id: "b", label: "B\nnext", status: "planned" },
      ],
      edges: [{ from: "a", to: "b", label: "go | <now>" }],
    };
    const unsafeMermaid = buildJ9WhitehatMermaid(unsafeFlow);
    expect(unsafeMermaid).not.toContain("[bad]");
    expect(unsafeMermaid).not.toContain("<node>");
    expect(unsafeMermaid).not.toContain("| <now>");
    expect(unsafeMermaid).not.toContain("\nnext");
  });

  it("defines ordered SOP steps and exactly 22 hardenings", () => {
    expect(J9_WHITEHAT_SOP_STEPS.map((step) => step.id)).toEqual([
      "discover",
      "intake",
      "acknowledge",
      "triage",
      "remediate",
      "coordinate-disclosure",
      "acknowledge-reward",
      "retrospective-evidence",
    ]);

    expect(J9_WHITEHAT_HARDENINGS).toHaveLength(22);
    expect(new Set(J9_WHITEHAT_HARDENINGS.map((item) => item.id)).size).toBe(22);
    expect(J9_WHITEHAT_HARDENINGS.map((item) => item.id)).toEqual([
      "j9-h01-security-txt-discovery",
      "j9-h02-mailbox-contact",
      "j9-h03-report-required-fields",
      "j9-h04-safe-harbor-boundary",
      "j9-h05-ordinary-bug-separation",
      "j9-h06-academic-channel-handoff",
      "j9-h07-national-apt-escalation",
      "j9-h08-future-platform-boundary",
      "j9-h09-acknowledgement-sla-clock",
      "j9-h10-email-receipt-failure-fallback",
      "j9-h11-pgp-fallback-boundary",
      "j9-h12-cvss-triage",
      "j9-h13-critical-hotfix-path",
      "j9-h14-medium-patch-path",
      "j9-h15-patch-evidence",
      "j9-h16-privacy-redaction",
      "j9-h17-duplicate-disclosure",
      "j9-h18-reward-antifraud",
      "j9-h19-public-acknowledgement",
      "j9-h20-cve-coordination-boundary",
      "j9-h21-automation-overclaim-guard",
      "j9-h22-retrospective-evidence",
    ]);
    expect(new Set(J9_WHITEHAT_HARDENINGS.map((item) => item.status))).toEqual(
      new Set(["active", "manual", "planned", "blocked"]),
    );
    for (const item of J9_WHITEHAT_HARDENINGS) {
      expect(item.owner.trim()).not.toHaveLength(0);
      expect(item.stage.trim()).not.toHaveLength(0);
      expect(item.title.trim()).not.toHaveLength(0);
      expect(item.description.trim()).not.toHaveLength(0);
    }
  });

  it("keeps the J9 runbook aligned with model stages and inactive automation boundaries", () => {
    const runbook = readFileSync(
      new URL("../../../../docs/runbooks/j9-whitehat-disclosure.md", import.meta.url),
      "utf8",
    );

    for (const step of J9_WHITEHAT_SOP_STEPS) {
      expect(runbook).toContain(`## Stage ${J9_WHITEHAT_SOP_STEPS.indexOf(step) + 1}: ${step.title}`);
    }

    expect(runbook).toContain("Dry-run evidence");
    expect(runbook).toContain("Redaction Rules");
    expect(runbook).toContain("Inactive Automation Boundaries");
    expect(runbook).toContain("SMTP auto-reply");
    expect(runbook).toContain("ticket automation");
    expect(runbook).toContain("PGP encrypted intake");
    expect(runbook).toContain("CVE tracking automation");
    expect(runbook).toContain("bounty payment");
    expect(runbook).toContain("HackerOne-like platform integration");
  });
});
