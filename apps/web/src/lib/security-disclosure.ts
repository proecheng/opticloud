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

export function securityTxtExpiresWithinOneYear(policy: SecurityDisclosurePolicy): boolean {
  const updated = Date.parse(policy.updated_at);
  const expires = Date.parse(policy.expires_at);
  if (Number.isNaN(updated) || Number.isNaN(expires)) return false;
  const oneYearMs = 365 * 24 * 60 * 60 * 1000;
  return expires > updated && expires - updated < oneYearMs;
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
