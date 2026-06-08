import Link from "next/link";

import {
  buildJ9WhitehatMermaid,
  J9_WHITEHAT_FLOW,
  J9_WHITEHAT_HARDENINGS,
  J9_WHITEHAT_SOP_STEPS,
  SECURITY_DISCLOSURE_POLICY,
  type SecurityDisclosurePolicy,
} from "@/lib/security-disclosure";

function formatDate(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

export function SecurityDisclosurePageView({
  policy = SECURITY_DISCLOSURE_POLICY,
}: {
  policy?: SecurityDisclosurePolicy;
}): JSX.Element {
  const j9MermaidSource = buildJ9WhitehatMermaid(J9_WHITEHAT_FLOW);

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              Algorithms
            </Link>
            <Link href="/academic" className="text-muted-foreground hover:text-foreground">
              Academic
            </Link>
            <Link href="/status" className="text-muted-foreground hover:text-foreground">
              Status
            </Link>
            <Link href="/security" className="font-medium text-foreground hover:text-primary">
              Security
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              Sign up
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto grid max-w-6xl gap-5 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
          <div>
            <p className="text-sm font-semibold text-primary">Responsible disclosure</p>
            <h1 className="mt-2 text-3xl font-bold">Security Disclosure</h1>
            <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
              Report security vulnerabilities affecting OptiCloud public APIs, product pages, or
              account flows. This public page is unauthenticated and does not require a Console
              session.
            </p>
          </div>
          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Disclosure mailbox</h2>
            <a
              href={`mailto:${policy.contact_email}`}
              className="mt-2 inline-block text-primary hover:underline"
            >
              {policy.contact_email}
            </a>
            <p className="mt-3 text-xs text-muted-foreground">
              security.txt updated {formatDate(policy.updated_at)} UTC; expires{" "}
              {formatDate(policy.expires_at)} UTC.
            </p>
          </section>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-xl font-semibold">What to include</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {policy.required_fields.map((field) => (
                <article key={field.id} className="rounded-md border border-border bg-muted p-4">
                  <h3 className="font-semibold">{field.label}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{field.description}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-xl font-semibold">Safe harbor boundaries</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              We welcome responsible security disclosure when testing stays within these limits.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {policy.safe_harbor.map((item) => (
                <article key={item.id} className="rounded-md border border-border bg-muted p-4">
                  <h3 className="font-semibold">{item.label}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{item.description}</p>
                </article>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Response targets</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="rounded-md bg-muted p-3">
                <dt className="font-medium">Initial acknowledgement target</dt>
                <dd className="mt-1 text-muted-foreground">
                  Within {policy.sla.acknowledgement_hours} hours for reports sent to{" "}
                  {policy.contact_email}.
                </dd>
              </div>
              <div className="rounded-md bg-muted p-3">
                <dt className="font-medium">CVSS &gt;= 7 remediation target</dt>
                <dd className="mt-1 text-muted-foreground">
                  Patch or mitigation target within {policy.sla.cvss_high_patch_days} days. Actively
                  exploited or critical platform-path risk may enter an internal{" "}
                  {policy.sla.internal_critical_hotfix_hours}h hotfix path.
                </dd>
              </div>
            </dl>
          </section>

          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Channel boundaries</h2>
            <div className="mt-3 space-y-3 text-sm text-muted-foreground">
              <p>
                This mailbox is for responsible security disclosure. Ordinary product bugs and
                support requests should use normal support or product feedback channels.
              </p>
              <p>
                SMTP auto-reply, ticket automation, CVE tracking, bounty payment, and PGP encrypted
                intake are not active in this static submission surface.
              </p>
            </div>
          </section>

          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Follow-up policy items</h2>
            <ul className="mt-3 space-y-3 text-sm">
              {policy.future_policy_items.map((item) => (
                <li key={item.id} className="rounded-md bg-muted p-3">
                  <div className="font-medium">{item.label}</div>
                  <p className="mt-1 text-muted-foreground">{item.description}</p>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </section>

      <section className="border-t border-border bg-background">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-primary">J9 responsible disclosure</p>
            <h2 className="mt-2 text-2xl font-bold">J9 Whitehat Vertical Slice</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              This vertical slice is a deterministic public model and dry-run contract for the
              whitehat path. Manual, planned, and blocked items are labeled as boundaries instead of
              active automation.
            </p>
          </div>

          <div className="mt-6 grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
            <section className="min-w-0 rounded-md border border-border bg-background p-4">
              <h3 className="text-xl font-semibold">Flow stages</h3>
              <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-2">
                {J9_WHITEHAT_FLOW.nodes.map((node) => (
                  <article
                    key={node.id}
                    className="min-w-0 rounded-md border border-border bg-muted p-3"
                  >
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <h4 className="min-w-0 break-words font-semibold">{node.label}</h4>
                      <span className="shrink-0 rounded-sm border border-border bg-background px-2 py-0.5 text-xs uppercase text-muted-foreground">
                        {node.status}
                      </span>
                    </div>
                    {node.description ? (
                      <p className="mt-2 break-words text-sm text-muted-foreground">
                        {node.description}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>

            <section className="min-w-0 rounded-md border border-border bg-background p-4">
              <h3 className="text-xl font-semibold">Mermaid flow source</h3>
              <pre className="mt-4 max-h-[560px] max-w-full overflow-auto rounded-md border border-border bg-muted p-4 text-xs leading-5 text-foreground">
                <code>
                  {j9MermaidSource.split("\n").map((line, index) => (
                    <span key={`${index}-${line}`} className="block whitespace-pre">
                      {line}
                    </span>
                  ))}
                </code>
              </pre>
            </section>
          </div>

          <div className="mt-6 grid min-w-0 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
            <section className="min-w-0 rounded-md border border-border bg-background p-4">
              <h3 className="text-xl font-semibold">SOP steps</h3>
              <ol aria-label="J9 SOP steps" className="mt-4 space-y-3 text-sm">
                {J9_WHITEHAT_SOP_STEPS.map((step, index) => (
                  <li
                    key={step.id}
                    className="min-w-0 rounded-md border border-border bg-muted p-3"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-primary text-xs font-semibold text-primary-foreground">
                        {index + 1}
                      </span>
                      <h4 className="min-w-0 break-words font-semibold">{step.title}</h4>
                    </div>
                    <p className="mt-2 break-words text-muted-foreground">{step.description}</p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">
                      Owner: {step.owner}. Evidence: {step.evidence}
                    </p>
                  </li>
                ))}
              </ol>
            </section>

            <section className="min-w-0 rounded-md border border-border bg-background p-4">
              <h3 className="text-xl font-semibold">Hardening checklist</h3>
              <ul
                aria-label="J9 hardening checklist"
                className="mt-4 grid min-w-0 gap-3 text-sm md:grid-cols-2"
              >
                {J9_WHITEHAT_HARDENINGS.map((item) => (
                  <li
                    key={item.id}
                    className="min-w-0 rounded-md border border-border bg-muted p-3"
                  >
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <h4 className="min-w-0 break-words font-semibold">{item.title}</h4>
                      <span className="shrink-0 rounded-sm border border-border bg-background px-2 py-0.5 text-xs uppercase text-muted-foreground">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 break-words text-xs text-muted-foreground">
                      {item.id} · {item.stage} · {item.owner}
                    </p>
                    <p className="mt-2 break-words text-muted-foreground">{item.description}</p>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      </section>
    </main>
  );
}
