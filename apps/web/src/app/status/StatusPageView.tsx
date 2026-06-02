import Link from "next/link";

import { EmptyState, StatusCard } from "@opticloud/ui";

import {
  componentLabelsForIncident,
  deriveOverallStatus,
  getPublishedP0Postmortem,
  getOrderedIncidents,
  INCIDENT_STATUS_LABELS,
  STATUS_LABELS,
  type PublicComponentStatus,
  type PublicStatusModel,
} from "@/lib/status-page";

const STATUS_VARIANT: Record<PublicComponentStatus, "ok" | "warning" | "error" | "info"> = {
  operational: "ok",
  degraded_performance: "warning",
  partial_outage: "warning",
  major_outage: "error",
};

function formatDate(value: string | null): string {
  if (!value) return "Ongoing";
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

function statusPill(status: PublicComponentStatus): JSX.Element {
  const tone = {
    operational: "border-success/30 bg-success/10 text-success",
    degraded_performance: "border-warning/30 bg-warning/10 text-warning",
    partial_outage: "border-warning/30 bg-warning/10 text-warning",
    major_outage: "border-danger/30 bg-danger/10 text-danger",
  }[status];
  return (
    <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export function StatusPageView({ model }: { model: PublicStatusModel }): JSX.Element {
  const overall = deriveOverallStatus(model.components);
  const incidents = getOrderedIncidents(model.incidents);
  const activeIncidents = incidents.filter((incident) => incident.status !== "resolved");

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
            <Link href="/status" className="font-medium text-foreground hover:text-primary">
              Status
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
            <p className="text-sm font-semibold text-primary">Public operations surface</p>
            <h1 className="mt-2 text-3xl font-bold">OptiCloud Status</h1>
            <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
              Public status, component health, and incident history for OptiCloud services.
              This page is unauthenticated and does not require a Console session.
            </p>
          </div>
          <StatusCard
            variant={STATUS_VARIANT[overall]}
            title={STATUS_LABELS[overall]}
            description={`Last updated ${formatDate(model.generated_at)} UTC. Public read model; automated status tooling is handled separately.`}
            ariaLabel="status.overall"
          />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <section className="space-y-3">
            <div>
              <h2 className="text-xl font-semibold">Components</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Status is derived from component severities, not maintained separately.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {model.components.map((component) => (
                <article
                  key={component.id}
                  className="rounded-md border border-border bg-background p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h3 className="font-semibold">{component.label}</h3>
                    {statusPill(component.status)}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{component.description}</p>
                  <p className="mt-3 text-xs text-muted-foreground">
                    Updated {formatDate(component.updated_at)} UTC
                  </p>
                </article>
              ))}
            </div>
          </section>

          <section className="space-y-3" aria-labelledby="incident-history-heading">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="incident-history-heading" className="text-xl font-semibold">
                  Incident History
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Ordered newest first and shared with the public RSS feed.
                </p>
              </div>
              <Link
                href="/status/rss.xml"
                className="min-h-touch rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-muted"
              >
                RSS feed
              </Link>
            </div>

            {incidents.length === 0 ? (
              <EmptyState
                ariaLabel="status.incidents.empty"
                title="No incidents reported"
                description="There is no public incident history in the current status model."
              />
            ) : (
              <div className="space-y-3">
                {incidents.map((incident) => (
                  <article
                    key={incident.id}
                    id={incident.id}
                    className="rounded-md border border-border bg-background p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold">{incident.title}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">{incident.summary}</p>
                      </div>
                      <span className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold">
                        {INCIDENT_STATUS_LABELS[incident.status]}
                      </span>
                    </div>
                    <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
                      <div>
                        <dt className="text-xs text-muted-foreground">Severity</dt>
                        <dd className="mt-1 font-medium">{incident.severity}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Started</dt>
                        <dd className="mt-1 font-medium">{formatDate(incident.started_at)} UTC</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Resolved</dt>
                        <dd className="mt-1 font-medium">{formatDate(incident.resolved_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Affected</dt>
                        <dd className="mt-1 font-medium">
                          {componentLabelsForIncident(incident, model.components)}
                        </dd>
                      </div>
                    </dl>
                    {getPublishedP0Postmortem(model, incident.id) ? (
                      <Link
                        href={`/status/incidents/${incident.id}`}
                        className="mt-4 inline-block rounded-md border border-border px-3 py-2 text-sm font-medium text-primary hover:bg-muted"
                      >
                        Read postmortem
                      </Link>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Current incidents</h2>
            {activeIncidents.length > 0 ? (
              <ul className="mt-3 space-y-2 text-sm">
                {activeIncidents.map((incident) => (
                  <li key={incident.id} className="rounded-md bg-muted p-3">
                    <div className="font-medium">{incident.title}</div>
                    <div className="mt-1 text-muted-foreground">
                      {INCIDENT_STATUS_LABELS[incident.status]}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No active incident in the public model.
              </p>
            )}
          </section>

          <section className="rounded-md border border-border bg-background p-4">
            <h2 className="text-lg font-semibold">Subscriptions</h2>
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <div className="font-medium">RSS feed</div>
                <p className="mt-1 text-muted-foreground">
                  Subscribe to incident updates from the public RSS endpoint.
                </p>
                <Link
                  href="/status/rss.xml"
                  className="mt-2 inline-block text-primary hover:underline"
                >
                  RSS feed
                </Link>
              </div>
              <div>
                <div className="font-medium">Email notifications</div>
                <p className="mt-1 text-muted-foreground">
                  Authenticated users can opt in to incident email notifications from account
                  settings.
                </p>
                <Link
                  href="/auth/account#notification-preferences"
                  className="mt-2 inline-block text-primary hover:underline"
                >
                  Manage incident subscriptions
                </Link>
              </div>
              <div>
                <div className="font-medium">Webhook callbacks</div>
                <p className="mt-1 text-muted-foreground">
                  Signed callback delivery, retry, and secret rotation are not active in this
                  v1 subscription contract.
                </p>
              </div>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
