import Link from "next/link";

import {
  buildPostmortemMermaidTimeline,
  componentLabelsForIncident,
  getOrderedPostmortemTimeline,
  INCIDENT_STATUS_LABELS,
  isPostmortemPublishedWithinSla,
  type PublicIncident,
  type PublicStatusComponent,
} from "@/lib/status-page";

const FOLLOW_UP_STATUS_LABELS = {
  todo: "Todo",
  in_progress: "In progress",
  done: "Done",
} as const;

function formatDate(value: string | null): string {
  if (!value) return "Ongoing";
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

function metadataItem(label: string, value: string): JSX.Element {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  );
}

export function PostmortemPageView({
  incident,
  components,
}: {
  incident: PublicIncident;
  components: readonly PublicStatusComponent[];
}): JSX.Element {
  const postmortem = incident.postmortem;
  if (!postmortem) {
    throw new Error("PostmortemPageView requires a published postmortem incident");
  }

  const timeline = getOrderedPostmortemTimeline(incident);
  const mermaid = buildPostmortemMermaidTimeline(incident);
  const mermaidLines = mermaid.split("\n");
  const withinSla = isPostmortemPublishedWithinSla(incident);

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/status" className="font-medium text-foreground hover:text-primary">
              Status
            </Link>
            <Link href="/status/rss.xml" className="text-muted-foreground hover:text-foreground">
              RSS
            </Link>
            <Link
              href="/auth/account#notification-preferences"
              className="text-muted-foreground hover:text-foreground"
            >
              Subscriptions
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <Link href="/status" className="text-sm font-medium text-primary hover:underline">
            Back to status
          </Link>
          <p className="mt-5 text-sm font-semibold text-primary">Public P0 postmortem</p>
          <h1 className="mt-2 max-w-4xl text-3xl font-bold">{incident.title}</h1>
          <p className="mt-3 max-w-4xl text-sm text-muted-foreground">{incident.summary}</p>
          <dl className="mt-6 grid gap-4 rounded-md border border-border bg-background p-4 text-sm md:grid-cols-4">
            {metadataItem("Incident ID", incident.id)}
            {metadataItem("Severity", "P0 / critical")}
            {metadataItem("Status", INCIDENT_STATUS_LABELS[incident.status])}
            {metadataItem("Affected", componentLabelsForIncident(incident, components))}
          </dl>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <section className="rounded-md border border-border bg-background p-5">
            <h2 className="text-xl font-semibold">What happened</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              {postmortem.sections.what_happened}
            </p>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <div className="rounded-md border border-border bg-background p-5">
              <h2 className="text-xl font-semibold">Impact</h2>
              <p className="mt-3 text-sm text-muted-foreground">{postmortem.sections.impact}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-5">
              <h2 className="text-xl font-semibold">Detection</h2>
              <p className="mt-3 text-sm text-muted-foreground">
                {postmortem.sections.detection}
              </p>
            </div>
            <div className="rounded-md border border-border bg-background p-5">
              <h2 className="text-xl font-semibold">Mitigation</h2>
              <p className="mt-3 text-sm text-muted-foreground">
                {postmortem.sections.mitigation}
              </p>
            </div>
            <div className="rounded-md border border-border bg-background p-5">
              <h2 className="text-xl font-semibold">Root cause</h2>
              <p className="mt-3 text-sm text-muted-foreground">
                {postmortem.sections.root_cause}
              </p>
            </div>
          </section>

          <section className="rounded-md border border-border bg-background p-5">
            <h2 className="text-xl font-semibold">Mermaid timeline</h2>
            <pre className="mt-4 overflow-x-auto rounded-md bg-muted p-4 text-sm">
              <code>
                {mermaidLines.map((line) => (
                  <span key={line} className="block">
                    {line}
                  </span>
                ))}
              </code>
            </pre>
            <ol aria-label="Postmortem timeline" className="mt-5 space-y-3">
              {timeline.map((event) => (
                <li key={event.id} className="rounded-md border border-border p-3 text-sm">
                  <div className="font-medium">{event.label}</div>
                  <div className="mt-1 text-muted-foreground">
                    {formatDate(event.occurred_at)} UTC
                  </div>
                  <div className="mt-1 text-muted-foreground">{event.description}</div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-md border border-border bg-background p-5">
            <h2 className="text-lg font-semibold">Publication SLA</h2>
            <dl className="mt-4 space-y-3 text-sm">
              {metadataItem("P0 declared", `${formatDate(postmortem.p0_declared_at)} UTC`)}
              {metadataItem("Due", `${formatDate(postmortem.publish_due_at)} UTC`)}
              {metadataItem("Published", `${formatDate(postmortem.published_at)} UTC`)}
            </dl>
            <p className="mt-4 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm font-medium text-success">
              {withinSla ? "Published within 24h SLA" : "Published after 24h SLA"}
            </p>
          </section>

          <section className="rounded-md border border-border bg-background p-5">
            <h2 className="text-lg font-semibold">Follow-up actions</h2>
            <ul aria-label="Postmortem follow-up actions" className="mt-4 space-y-3">
              {postmortem.follow_ups.map((item) => (
                <li key={item.id} className="rounded-md border border-border p-3 text-sm">
                  <div className="font-medium">{item.title}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-md bg-muted px-2 py-1">{item.owner}</span>
                    <span className="rounded-md bg-muted px-2 py-1">
                      {FOLLOW_UP_STATUS_LABELS[item.status]}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </section>
    </main>
  );
}
