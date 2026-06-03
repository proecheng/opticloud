export interface SecurityDisclosureField {
  id: string;
  label: string;
  description: string;
}

export interface SecurityDisclosureSafeHarborItem {
  id: string;
  label: string;
  description: string;
}

export interface SecurityDisclosureFuturePolicyItem {
  id: string;
  label: string;
  description: string;
}

export interface SecurityDisclosurePolicy {
  updated_at: string;
  expires_at: string;
  contact_email: string;
  policy_url: string;
  canonical_url: string;
  preferred_languages: string[];
  sla: {
    acknowledgement_hours: number;
    cvss_high_patch_days: number;
    internal_critical_hotfix_hours: number;
  };
  required_fields: SecurityDisclosureField[];
  safe_harbor: SecurityDisclosureSafeHarborItem[];
  future_policy_items: SecurityDisclosureFuturePolicyItem[];
}

export type J9WhitehatStatus = "active" | "manual" | "planned" | "blocked";

export interface J9WhitehatFlowNode {
  id: string;
  label: string;
  status: J9WhitehatStatus;
  description?: string;
}

export interface J9WhitehatFlowEdge {
  from: string;
  to: string;
  label: string;
}

export interface J9WhitehatFlow {
  nodes: J9WhitehatFlowNode[];
  edges: J9WhitehatFlowEdge[];
}

export interface J9WhitehatSopStep {
  id: string;
  title: string;
  owner: string;
  description: string;
  evidence: string;
}

export interface J9WhitehatHardening {
  id: string;
  owner: string;
  stage: string;
  status: J9WhitehatStatus;
  title: string;
  description: string;
}

export const SECURITY_DISCLOSURE_POLICY: SecurityDisclosurePolicy = {
  updated_at: "2026-06-03T00:00:00Z",
  expires_at: "2026-12-03T00:00:00Z",
  contact_email: "security@opticloud.cn",
  policy_url: "https://opticloud.cn/security",
  canonical_url: "https://opticloud.cn/.well-known/security.txt",
  preferred_languages: ["zh", "en"],
  sla: {
    acknowledgement_hours: 48,
    cvss_high_patch_days: 7,
    internal_critical_hotfix_hours: 24,
  },
  required_fields: [
    {
      id: "affected-surface",
      label: "Affected endpoint or service",
      description: "Include the API path, page URL, account flow, or public service you tested.",
    },
    {
      id: "impact",
      label: "Vulnerability class and impact",
      description: "Describe the weakness, likely impact, and affected data or capability.",
    },
    {
      id: "reproduction-or-poc",
      label: "Reproduction steps or PoC",
      description: "Provide minimal steps, request samples, screenshots, or a safe proof of concept.",
    },
    {
      id: "cvss-estimate",
      label: "CVSS estimate",
      description: "Share your CVSS estimate and reasoning if you can classify severity.",
    },
    {
      id: "reporter-contact",
      label: "Reporter contact",
      description: "Tell us how to reach you for acknowledgement, clarification, and coordination.",
    },
  ],
  safe_harbor: [
    {
      id: "minimal-proof",
      label: "Stop after minimal proof",
      description: "Validate only enough to prove the issue, then stop and report.",
    },
    {
      id: "no-data-exfiltration",
      label: "Do not exfiltrate customer or platform data",
      description: "Do not access, copy, modify, or disclose data that is not yours.",
    },
    {
      id: "no-destructive-testing",
      label: "Do not perform destructive testing",
      description: "Avoid actions that delete data, change balances, alter jobs, or disrupt accounts.",
    },
    {
      id: "no-persistence",
      label: "Do not create persistence or backdoors",
      description: "Do not install shells, hidden users, scheduled jobs, or persistent access paths.",
    },
    {
      id: "no-social-engineering",
      label: "No social engineering",
      description: "Do not phish, pretext, bribe, or contact OptiCloud staff, customers, or providers.",
    },
    {
      id: "no-ddos",
      label: "Do not perform DDoS or load testing",
      description: "Avoid volume testing, resource exhaustion, spam, or automated traffic bursts.",
    },
    {
      id: "synthetic-data",
      label: "Use synthetic or researcher-owned test data",
      description: "Privacy-impacting findings should use synthetic or researcher-owned test data where possible.",
    },
  ],
  future_policy_items: [
    {
      id: "duplicate-disclosure",
      label: "Duplicate disclosure handling",
      description: "Duplicate reports and first-disclosure precedence are handled by the follow-up J9 policy.",
    },
    {
      id: "reward-eligibility",
      label: "Reward eligibility",
      description: "Reward amount, eligibility, anti-fraud checks, and payout are handled by the follow-up J9 policy.",
    },
    {
      id: "public-acknowledgement",
      label: "Public acknowledgement",
      description: "Public thanks-page entries are handled by the follow-up J9 policy.",
    },
    {
      id: "pgp-fallback",
      label: "PGP fallback",
      description: "Encrypted intake will be published only after a real public PGP key URL exists.",
    },
    {
      id: "cve-tracking",
      label: "CVE tracking",
      description: "CVE tracking and coordination automation are handled by the follow-up J9 policy.",
    },
  ],
};

export const J9_WHITEHAT_FLOW: J9WhitehatFlow = {
  nodes: [
    {
      id: "discover-api",
      label: "Researcher scans API v1 surface",
      status: "active",
      description: "Researcher finds the public API surface and starts from published discovery.",
    },
    {
      id: "read-security-txt",
      label: "Read security.txt",
      status: "active",
      description: "Researcher reads the RFC 9116 discovery file.",
    },
    {
      id: "find-security-mailbox",
      label: "Find security@opticloud.cn",
      status: "active",
      description: "Researcher finds the responsible disclosure mailbox.",
    },
    {
      id: "discover-vulnerability",
      label: "Discover endpoint vulnerability",
      status: "manual",
      description: "Researcher validates only the minimal safe proof.",
    },
    {
      id: "disclosure-type",
      label: "Disclosure type decision",
      status: "manual",
      description: "Report is routed by disclosure class.",
    },
    {
      id: "responsible-disclosure",
      label: "Send email plus PoC and CVSS",
      status: "active",
      description: "Responsible disclosure uses the required report fields.",
    },
    {
      id: "ordinary-bug-report",
      label: "Ordinary bug report handoff",
      status: "manual",
      description: "Non-security product bugs are routed outside security intake.",
    },
    {
      id: "academic-disclosure",
      label: "Academic/student channel handoff",
      status: "planned",
      description: "Academic/student handling is a future channel handoff.",
    },
    {
      id: "national-apt-escalation",
      label: "National/APT escalation handoff",
      status: "blocked",
      description: "National-security or APT-class reports require legal/regulatory SOP handoff.",
    },
    {
      id: "future-platform",
      label: "Future platform integration",
      status: "planned",
      description: "HackerOne-like platform integration is v2+ only.",
    },
    {
      id: "acknowledgement-ticket",
      label: "48h acknowledgement and ticket contract",
      status: "manual",
      description: "48h acknowledgement is tracked as a contract; ticket automation is not active.",
    },
    {
      id: "email-received",
      label: "Email received decision",
      status: "manual",
      description: "Operator verifies whether the disclosure reached the security mailbox.",
    },
    {
      id: "email-fallback",
      label: "PGP/key and internal alert fallback",
      status: "planned",
      description: "Fallback remains planned until a real PGP key and alert integration exist.",
    },
    {
      id: "security-team-confirm",
      label: "Security team confirms report",
      status: "manual",
      description: "Security team confirms receipt and requests clarifications if needed.",
    },
    {
      id: "triage",
      label: "Vulnerability triage",
      status: "manual",
      description: "Report is classified by CVSS and exploitability.",
    },
    {
      id: "cvss-high-patch",
      label: "CVSS >= 7 hotfix path",
      status: "manual",
      description: "High severity enters hotfix planning and remediation evidence collection.",
    },
    {
      id: "cvss-medium-patch",
      label: "CVSS 4-6.9 seven day patch",
      status: "manual",
      description: "Medium severity enters the seven-day patch target.",
    },
    {
      id: "public-acknowledgement",
      label: "Public acknowledgement handoff",
      status: "planned",
      description: "Public thanks-page entry is a planned/manual handoff, not an active database.",
    },
    {
      id: "duplicate-disclosure",
      label: "Duplicate disclosure decision",
      status: "manual",
      description: "Duplicate handling decides first-disclosure credit.",
    },
    {
      id: "first-disclosure-reward",
      label: "First disclosure reward handoff",
      status: "planned",
      description: "Reward decision is a legal/finance handoff, not active payout automation.",
    },
    {
      id: "duplicate-thanks",
      label: "Duplicate report thanks",
      status: "manual",
      description: "Duplicate reports receive acknowledgement without reward implication.",
    },
  ],
  edges: [
    { from: "discover-api", to: "read-security-txt", label: "finds" },
    { from: "read-security-txt", to: "find-security-mailbox", label: "contact" },
    { from: "find-security-mailbox", to: "discover-vulnerability", label: "reports" },
    { from: "discover-vulnerability", to: "disclosure-type", label: "classify" },
    {
      from: "disclosure-type",
      to: "responsible-disclosure",
      label: "responsible security disclosure",
    },
    { from: "disclosure-type", to: "ordinary-bug-report", label: "ordinary product bug" },
    { from: "disclosure-type", to: "academic-disclosure", label: "academic/student" },
    { from: "disclosure-type", to: "national-apt-escalation", label: "national/APT" },
    { from: "disclosure-type", to: "future-platform", label: "v2+ platform" },
    { from: "responsible-disclosure", to: "acknowledgement-ticket", label: "email + PoC + CVSS" },
    { from: "acknowledgement-ticket", to: "email-received", label: "48h SLA" },
    { from: "email-received", to: "email-fallback", label: "no" },
    { from: "email-received", to: "security-team-confirm", label: "yes" },
    { from: "email-fallback", to: "security-team-confirm", label: "manual recovery" },
    { from: "security-team-confirm", to: "triage", label: "confirm" },
    { from: "triage", to: "cvss-high-patch", label: "CVSS >= 7.0" },
    { from: "triage", to: "cvss-medium-patch", label: "CVSS 4-6.9" },
    { from: "cvss-high-patch", to: "public-acknowledgement", label: "fixed" },
    { from: "cvss-medium-patch", to: "public-acknowledgement", label: "fixed" },
    { from: "public-acknowledgement", to: "duplicate-disclosure", label: "dedupe" },
    { from: "duplicate-disclosure", to: "first-disclosure-reward", label: "first disclosure" },
    { from: "duplicate-disclosure", to: "duplicate-thanks", label: "duplicate" },
  ],
};

export const J9_WHITEHAT_SOP_STEPS: J9WhitehatSopStep[] = [
  {
    id: "discover",
    title: "Discover",
    owner: "Security",
    description: "Keep security.txt and the public /security page discoverable from public trust surfaces.",
    evidence: "security.txt route, /security page, and public navigation checks.",
  },
  {
    id: "intake",
    title: "Intake",
    owner: "Security",
    description: "Receive responsible disclosure through security@opticloud.cn with PoC and CVSS context.",
    evidence: "Report completeness checklist and safe-harbor boundary review.",
  },
  {
    id: "acknowledge",
    title: "Acknowledge",
    owner: "Security",
    description: "Send a human acknowledgement within the 48h target and record the tracking reference.",
    evidence: "Timestamped acknowledgement note; no active SMTP auto-reply claim.",
  },
  {
    id: "triage",
    title: "Triage",
    owner: "Security",
    description: "Classify by CVSS, exploitability, data exposure, and active abuse signals.",
    evidence: "Triage note with severity, affected surface, and redacted reproduction context.",
  },
  {
    id: "remediate",
    title: "Remediate",
    owner: "Engineering",
    description: "Patch, mitigate, or document compensating controls according to severity target.",
    evidence: "Patch PR, deploy reference, rollback note, and public-safe remediation summary.",
  },
  {
    id: "coordinate-disclosure",
    title: "Coordinate disclosure",
    owner: "Security",
    description: "Coordinate disclosure timing, duplicate handling, and public wording with the researcher.",
    evidence: "Researcher communication log and redaction review.",
  },
  {
    id: "acknowledge-reward",
    title: "Acknowledge or reward",
    owner: "Legal/Finance",
    description: "Route public acknowledgement and reward eligibility through manual legal/finance review.",
    evidence: "Manual approval record; no active bounty payment automation claim.",
  },
  {
    id: "retrospective-evidence",
    title: "Retrospective evidence",
    owner: "Security",
    description: "Archive public-safe evidence and lessons without raw exploit payloads or customer data.",
    evidence: "Redacted evidence bundle and hardening checklist update.",
  },
];

export const J9_WHITEHAT_HARDENINGS: J9WhitehatHardening[] = [
  {
    id: "j9-h01-security-txt-discovery",
    owner: "Web",
    stage: "discovery",
    status: "active",
    title: "security.txt discovery",
    description: "RFC 9116 discovery route points researchers to the disclosure policy.",
  },
  {
    id: "j9-h02-mailbox-contact",
    owner: "Security",
    stage: "discovery",
    status: "active",
    title: "Mailbox contact",
    description: "Responsible disclosure mailbox is visible and linked as mailto.",
  },
  {
    id: "j9-h03-report-required-fields",
    owner: "Security",
    stage: "intake",
    status: "active",
    title: "Report required fields",
    description: "Policy lists affected surface, impact, PoC, CVSS estimate, and reporter contact.",
  },
  {
    id: "j9-h04-safe-harbor-boundary",
    owner: "Security",
    stage: "intake",
    status: "active",
    title: "Safe-harbor boundary",
    description: "Policy constrains testing to minimal proof and non-destructive behavior.",
  },
  {
    id: "j9-h05-ordinary-bug-separation",
    owner: "Support",
    stage: "routing",
    status: "manual",
    title: "Ordinary bug separation",
    description: "Ordinary product bugs are routed away from security vulnerability intake.",
  },
  {
    id: "j9-h06-academic-channel-handoff",
    owner: "Academic",
    stage: "routing",
    status: "planned",
    title: "Academic channel handoff",
    description: "Academic/student disclosure receives a future specialized handoff path.",
  },
  {
    id: "j9-h07-national-apt-escalation",
    owner: "Legal",
    stage: "routing",
    status: "blocked",
    title: "National/APT escalation",
    description: "National-security or APT-class reports require legal/regulatory SOP activation.",
  },
  {
    id: "j9-h08-future-platform-boundary",
    owner: "Security",
    stage: "routing",
    status: "planned",
    title: "Future platform boundary",
    description: "HackerOne-like integration remains v2+ and is not represented as active.",
  },
  {
    id: "j9-h09-acknowledgement-sla-clock",
    owner: "Security",
    stage: "acknowledgement",
    status: "manual",
    title: "Acknowledgement SLA clock",
    description: "48h acknowledgement target is tracked manually until ticket automation exists.",
  },
  {
    id: "j9-h10-email-receipt-failure-fallback",
    owner: "Security",
    stage: "acknowledgement",
    status: "planned",
    title: "Email receipt failure fallback",
    description: "Fallback alerting remains a planned hardening until real monitoring exists.",
  },
  {
    id: "j9-h11-pgp-fallback-boundary",
    owner: "Security",
    stage: "acknowledgement",
    status: "blocked",
    title: "PGP fallback boundary",
    description: "Encrypted intake remains blocked until a real public PGP key URL is published.",
  },
  {
    id: "j9-h12-cvss-triage",
    owner: "Security",
    stage: "triage",
    status: "manual",
    title: "CVSS triage",
    description: "Reports are classified by CVSS and exploitability before remediation routing.",
  },
  {
    id: "j9-h13-critical-hotfix-path",
    owner: "Engineering",
    stage: "remediation",
    status: "manual",
    title: "Critical hotfix path",
    description: "CVSS >= 7 issues can enter an internal 24h hotfix path.",
  },
  {
    id: "j9-h14-medium-patch-path",
    owner: "Engineering",
    stage: "remediation",
    status: "manual",
    title: "Medium patch path",
    description: "CVSS 4-6.9 issues stay aligned to the seven-day patch target.",
  },
  {
    id: "j9-h15-patch-evidence",
    owner: "Engineering",
    stage: "remediation",
    status: "manual",
    title: "Patch evidence",
    description: "Patch references, deploy notes, and rollback notes are captured without secrets.",
  },
  {
    id: "j9-h16-privacy-redaction",
    owner: "Security",
    stage: "evidence",
    status: "active",
    title: "Privacy redaction",
    description: "Evidence excludes customer data, raw exploit payloads, credentials, and internal hosts.",
  },
  {
    id: "j9-h17-duplicate-disclosure",
    owner: "Security",
    stage: "coordination",
    status: "manual",
    title: "Duplicate disclosure",
    description: "Duplicate reports are acknowledged while first-disclosure credit is reviewed.",
  },
  {
    id: "j9-h18-reward-antifraud",
    owner: "Legal/Finance",
    stage: "coordination",
    status: "planned",
    title: "Reward anti-fraud handoff",
    description: "Reward eligibility and anti-fraud checks are manual legal/finance handoffs.",
  },
  {
    id: "j9-h19-public-acknowledgement",
    owner: "Security",
    stage: "coordination",
    status: "planned",
    title: "Public acknowledgement",
    description: "Public thanks-page publication remains a planned/manual handoff.",
  },
  {
    id: "j9-h20-cve-coordination-boundary",
    owner: "Security",
    stage: "coordination",
    status: "planned",
    title: "CVE coordination boundary",
    description: "CVE tracking is documented as future coordination, not active automation.",
  },
  {
    id: "j9-h21-automation-overclaim-guard",
    owner: "Web",
    stage: "governance",
    status: "active",
    title: "Automation overclaim guard",
    description: "Tests and copy prevent false claims about SMTP, ticket, PGP, CVE, or payout automation.",
  },
  {
    id: "j9-h22-retrospective-evidence",
    owner: "Security",
    stage: "evidence",
    status: "manual",
    title: "Retrospective evidence",
    description: "Dry-run records and lessons are archived after each significant disclosure.",
  },
];

export function securityTxtExpiresWithinOneYear(policy: SecurityDisclosurePolicy): boolean {
  const updated = Date.parse(policy.updated_at);
  const expires = Date.parse(policy.expires_at);
  if (Number.isNaN(updated) || Number.isNaN(expires)) return false;
  const oneYearMs = 365 * 24 * 60 * 60 * 1000;
  return expires > updated && expires - updated < oneYearMs;
}

function sanitizeMermaidValue(value: string): string {
  return value
    .replace(/[\r\n]+/g, " ")
    .replace(/[<"'[\]{}()|:;`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function buildJ9WhitehatMermaid(flow: J9WhitehatFlow = J9_WHITEHAT_FLOW): string {
  const nodeLines = flow.nodes.map((node) => `${node.id}[${sanitizeMermaidValue(node.label)}]`);
  const edgeLines = flow.edges.map((edge) => {
    return `${edge.from} -->|${sanitizeMermaidValue(edge.label)}| ${edge.to}`;
  });
  return ["graph TD", ...nodeLines, ...edgeLines].join("\n");
}

export function buildSecurityTxt(
  policy: SecurityDisclosurePolicy = SECURITY_DISCLOSURE_POLICY,
): string {
  return [
    `Contact: mailto:${policy.contact_email}`,
    `Policy: ${policy.policy_url}`,
    `Canonical: ${policy.canonical_url}`,
    `Preferred-Languages: ${policy.preferred_languages.join(", ")}`,
    `Expires: ${policy.expires_at}`,
    "",
  ].join("\n");
}
