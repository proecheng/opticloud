/** Landing page (UX-DR8 Page Direction Map: Landing → SSR / Direction "Engineer-First / 实证克制"). */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { PublicShell } from "@/components/PublicShell";

export default function LandingPage(): JSX.Element {
  const common = useTranslations("common");
  const t = useTranslations("landing");
  const metrics = [
    { label: t("metrics.api.label"), value: t("metrics.api.value"), detail: t("metrics.api.detail") },
    { label: t("metrics.excel.label"), value: t("metrics.excel.value"), detail: t("metrics.excel.detail") },
    { label: t("metrics.trust.label"), value: t("metrics.trust.value"), detail: t("metrics.trust.detail") },
  ];
  const workflows = [
    {
      title: t("workflows.api.title"),
      body: t("workflows.api.body"),
      href: "/docs/quickstart",
      action: t("workflows.api.action"),
    },
    {
      title: t("workflows.excel.title"),
      body: t("workflows.excel.body"),
      href: "/console/excel",
      action: t("workflows.excel.action"),
    },
    {
      title: t("workflows.provider.title"),
      body: t("workflows.provider.body"),
      href: "/algorithms",
      action: t("workflows.provider.action"),
    },
  ];

  return (
    <PublicShell active="home">
      <section className="border-b border-border bg-background">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:py-14">
          <div className="max-w-4xl">
            <p className="text-xs font-semibold uppercase tracking-normal text-primary">
              {t("eyebrow")}
            </p>
            <h1 className="mt-3 text-balance text-4xl font-bold leading-tight md:text-5xl">
              {t("hero.title")}
            </h1>
            <p className="mt-4 max-w-3xl text-balance text-xl leading-8 text-muted-foreground md:text-2xl">
              {t("hero.subtitle")}
            </p>
            <p className="mt-5 max-w-3xl text-base leading-7 text-muted-foreground">
              {t("hero.body")}{" "}
              <strong className="font-semibold text-foreground">{t("hero.cost")}</strong>
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/auth/signup"
                className="inline-flex min-h-touch items-center justify-center rounded-md bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary-600"
              >
                {common("actions.signupArrow")}
              </Link>
              <Link
                href="/algorithms"
                className="inline-flex min-h-touch items-center justify-center rounded-md border border-border bg-background px-5 py-3 text-sm font-semibold transition hover:bg-muted"
              >
                {common("actions.browseAlgorithms")}
              </Link>
            </div>
          </div>

          <div className="mt-10 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <section
              aria-label={t("preview.aria")}
              className="min-w-0 overflow-hidden rounded-md border border-border bg-background shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold">{t("preview.title")}</h2>
                  <p className="mt-1 text-xs text-muted-foreground">{t("preview.subtitle")}</p>
                </div>
                <span className="rounded-md border border-success/30 bg-success/5 px-2.5 py-1 text-xs font-medium text-success">
                  {t("preview.status")}
                </span>
              </div>

              <dl className="grid border-b border-border sm:grid-cols-3">
                {metrics.map((metric) => (
                  <div key={metric.label} className="min-w-0 border-b border-border p-4 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
                    <dt className="text-xs font-medium text-muted-foreground">{metric.label}</dt>
                    <dd className="mt-2 text-2xl font-bold">{metric.value}</dd>
                    <dd className="mt-1 text-xs leading-5 text-muted-foreground">{metric.detail}</dd>
                  </div>
                ))}
              </dl>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="bg-muted/60 text-xs text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium">{t("preview.table.task")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("preview.table.input")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("preview.table.provider")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("preview.table.state")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">highs-lp</td>
                      <td className="px-4 py-3">{t("preview.rows.lp.input")}</td>
                      <td className="px-4 py-3">HiGHS v1.7</td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-success/10 px-2 py-1 text-xs font-medium text-success">
                          {t("preview.rows.lp.state")}
                        </span>
                      </td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">inventory-baseline</td>
                      <td className="px-4 py-3">{t("preview.rows.inventory.input")}</td>
                      <td className="px-4 py-3">Forecast baseline</td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                          {t("preview.rows.inventory.state")}
                        </span>
                      </td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">vrptw-routing</td>
                      <td className="px-4 py-3">{t("preview.rows.routing.input")}</td>
                      <td className="px-4 py-3">OR-Tools / T4</td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-warning/10 px-2 py-1 text-xs font-medium text-warning">
                          {t("preview.rows.routing.state")}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <aside className="grid min-w-0 gap-3">
              <section className="rounded-md border border-border bg-muted/30 p-4">
                <h2 className="text-sm font-semibold">{t("summary.title")}</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("summary.body")}</p>
              </section>
              <section className="rounded-md border border-border bg-background p-4">
                <h2 className="text-sm font-semibold">{t("summary.trustTitle")}</h2>
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <li>{t("summary.trustOne")}</li>
                  <li>{t("summary.trustTwo")}</li>
                  <li>{t("summary.trustThree")}</li>
                </ul>
              </section>
            </aside>
          </div>
        </div>
      </section>

      <section className="border-b border-border bg-muted/30">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
          <div className="max-w-3xl">
            <h2 className="text-2xl font-bold">{t("workflows.title")}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {t("workflows.description")}
            </p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {workflows.map((item, index) => (
              <section
                key={item.title}
                className="min-w-0 rounded-md border border-border bg-background p-5"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-sm font-bold text-primary">
                  {index + 1}
                </div>
                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
                <Link
                  href={item.href}
                  className="mt-4 inline-flex min-h-touch items-center rounded-md border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
                >
                  {item.action}
                </Link>
              </section>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-background">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)] lg:items-start">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-normal text-primary">
              Quickstart
            </p>
            <h2 className="mt-2 text-2xl font-bold">{t("hello.title")}</h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {t("hello.description")}
            </p>
            <Link
              href="/docs/quickstart"
              className="mt-5 inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600"
            >
              {common("actions.openQuickstart")}
            </Link>
          </div>
          <pre className="min-w-0 overflow-x-auto rounded-md border border-border bg-muted/40 p-4 font-mono text-xs leading-relaxed">
            <code>{t("hello.snippet")}</code>
          </pre>
        </div>
      </section>
    </PublicShell>
  );
}
