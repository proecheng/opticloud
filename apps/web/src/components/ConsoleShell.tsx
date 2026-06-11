import Link from "next/link";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

export type ConsoleSection =
  | "excel"
  | "predictions"
  | "repro"
  | "providers"
  | "routing-history"
  | "legal-inquiry"
  | "classroom"
  | "data-exports"
  | "billing"
  | "audit-logs";

const CONSOLE_NAV: Array<{
  href: string;
  labelKey:
    | "console.excel"
    | "console.predictions"
    | "console.repro"
    | "console.providers"
    | "console.routingHistory"
    | "console.legalInquiry"
    | "console.classroom"
    | "console.dataExports"
    | "console.billing"
    | "console.auditLogs";
  section: ConsoleSection;
  group: "workflow" | "governance";
}> = [
  { href: "/console/excel", labelKey: "console.excel", section: "excel", group: "workflow" },
  {
    href: "/console/predictions",
    labelKey: "console.predictions",
    section: "predictions",
    group: "workflow",
  },
  { href: "/console/repro", labelKey: "console.repro", section: "repro", group: "workflow" },
  {
    href: "/console/classroom",
    labelKey: "console.classroom",
    section: "classroom",
    group: "workflow",
  },
  {
    href: "/console/data-exports",
    labelKey: "console.dataExports",
    section: "data-exports",
    group: "workflow",
  },
  {
    href: "/console/providers",
    labelKey: "console.providers",
    section: "providers",
    group: "governance",
  },
  {
    href: "/console/routing-history",
    labelKey: "console.routingHistory",
    section: "routing-history",
    group: "governance",
  },
  {
    href: "/console/legal-inquiry",
    labelKey: "console.legalInquiry",
    section: "legal-inquiry",
    group: "governance",
  },
  {
    href: "/console/billing/invoices",
    labelKey: "console.billing",
    section: "billing",
    group: "governance",
  },
  {
    href: "/console/audit-logs",
    labelKey: "console.auditLogs",
    section: "audit-logs",
    group: "governance",
  },
];

function navLinkClass(active: boolean): string {
  return (
    "inline-flex min-h-touch shrink-0 items-center rounded-md px-3 py-2 text-sm font-medium transition " +
    (active
      ? "bg-primary text-primary-foreground shadow-sm"
      : "text-muted-foreground hover:bg-muted hover:text-foreground")
  );
}

function ConsoleBrand(): JSX.Element {
  return (
    <Link
      href="/"
      className="flex min-w-0 items-center gap-3 rounded-md focus:outline-none focus:ring-2 focus:ring-primary/40"
      aria-label="OptiCloud 首页"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground shadow-sm">
        OC
      </span>
      <span className="min-w-0">
        <span className="block truncate text-base font-semibold leading-5">OptiCloud</span>
        <span className="hidden truncate text-xs text-muted-foreground sm:block">
          Console
        </span>
      </span>
    </Link>
  );
}

const SUPPORT_NAV = [
  { href: "/docs", labelKey: "nav.docs" },
  { href: "/algorithms", labelKey: "nav.algorithms" },
];

export function ConsoleShell({
  active,
  children,
}: {
  active: ConsoleSection;
  children: ReactNode;
}): JSX.Element {
  const t = useTranslations("common");
  const workflowNav = CONSOLE_NAV.filter((item) => item.group === "workflow");
  const governanceNav = CONSOLE_NAV.filter((item) => item.group === "governance");

  return (
    <div className="flex min-h-screen flex-col bg-muted/25 text-foreground">
      <a
        href="#console-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary focus:shadow-lg focus:ring-2 focus:ring-primary/40"
      >
        {t("a11y.skipConsole")}
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <ConsoleBrand />

          <nav
            aria-label="Console support navigation"
            className="flex shrink-0 items-center justify-end gap-1"
          >
            {SUPPORT_NAV.map((item) => (
              <Link key={item.href} href={item.href} className={navLinkClass(false)}>
                {t(item.labelKey)}
              </Link>
            ))}
          </nav>
        </div>

        <div className="border-t border-border/70">
          <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-2 sm:px-6 lg:flex-row lg:items-center lg:gap-3">
            <nav
              aria-label="Console navigation"
              className="flex w-full min-w-0 items-center gap-1 overflow-x-auto pb-1 lg:flex-1"
            >
              {workflowNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active === item.section ? "page" : undefined}
                  className={navLinkClass(active === item.section)}
                >
                  {t(item.labelKey)}
                </Link>
              ))}
            </nav>

            <nav
              aria-label="Console governance navigation"
              className="hidden shrink-0 items-center gap-1 border-l border-border pl-3 lg:flex"
            >
              {governanceNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active === item.section ? "page" : undefined}
                  className={navLinkClass(active === item.section)}
                >
                  {t(item.labelKey)}
                </Link>
              ))}
            </nav>

            <nav
              aria-label="Console governance navigation mobile"
              className="flex w-full min-w-0 items-center gap-1 overflow-x-auto border-t border-border pt-2 lg:hidden"
            >
              {governanceNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active === item.section ? "page" : undefined}
                  className={navLinkClass(active === item.section)}
                >
                  {t(item.labelKey)}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main id="console-content" className="min-w-0 flex-1">
        {children}
      </main>
    </div>
  );
}

export function ConsolePageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  meta?: ReactNode;
  actions?: ReactNode;
}): JSX.Element {
  return (
    <section className="border-b border-border bg-background">
      <div className="mx-auto grid max-w-7xl gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-normal text-primary">
              {eyebrow}
            </p>
          )}
          <h1 className="mt-1 text-balance text-2xl font-bold leading-tight md:text-3xl">
            {title}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
          {meta && <div className="mt-4 flex min-w-0 flex-wrap gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex min-w-0 flex-wrap gap-3 lg:justify-end">{actions}</div>}
      </div>
    </section>
  );
}
