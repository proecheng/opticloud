import Link from "next/link";
import type { ReactNode } from "react";

export type ConsoleSection =
  | "excel"
  | "predictions"
  | "repro"
  | "providers"
  | "routing-history"
  | "classroom"
  | "data-exports"
  | "billing"
  | "audit-logs";

const CONSOLE_NAV: Array<{
  href: string;
  label: string;
  section: ConsoleSection;
}> = [
  { href: "/console/excel", label: "Excel", section: "excel" },
  { href: "/console/predictions", label: "预测", section: "predictions" },
  { href: "/console/repro", label: "复现", section: "repro" },
  { href: "/console/providers", label: "Providers", section: "providers" },
  { href: "/console/routing-history", label: "路由历史", section: "routing-history" },
  { href: "/console/classroom", label: "Classroom", section: "classroom" },
  { href: "/console/data-exports", label: "数据导出", section: "data-exports" },
  { href: "/console/billing/invoices", label: "账单", section: "billing" },
  { href: "/console/audit-logs", label: "审计日志", section: "audit-logs" },
];

function navLinkClass(active: boolean): string {
  return (
    "rounded-md px-2.5 py-2 text-sm font-medium transition " +
    (active
      ? "bg-primary/10 text-primary"
      : "text-muted-foreground hover:bg-muted hover:text-foreground")
  );
}

export function ConsoleShell({
  active,
  children,
}: {
  active: ConsoleSection;
  children: ReactNode;
}): JSX.Element {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <Link
            href="/"
            className="flex min-w-0 items-center gap-2 rounded-md focus:outline-none focus:ring-2 focus:ring-primary/40"
            aria-label="OptiCloud 首页"
          >
            <div className="h-8 w-8 shrink-0 rounded bg-primary" />
            <span className="truncate text-lg font-semibold">OptiCloud</span>
          </Link>

          <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2">
            <nav
              aria-label="Console navigation"
              className="flex min-w-0 flex-wrap items-center justify-end gap-1"
            >
              {CONSOLE_NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active === item.section ? "page" : undefined}
                  className={navLinkClass(active === item.section)}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <nav
              aria-label="Console support navigation"
              className="flex shrink-0 flex-wrap items-center justify-end gap-1 border-l border-border pl-2"
            >
              <Link href="/docs" className={navLinkClass(false)}>
                文档
              </Link>
              <Link href="/algorithms" className={navLinkClass(false)}>
                算法
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <div className="min-w-0 flex-1">{children}</div>
    </main>
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
    <section className="border-b border-border bg-muted/40">
      <div className="mx-auto grid max-w-7xl gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-sm font-semibold uppercase text-muted-foreground">{eyebrow}</p>
          )}
          <h1 className="mt-1 text-balance text-3xl font-bold leading-tight">{title}</h1>
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
