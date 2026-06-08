import Link from "next/link";
import type { ReactNode } from "react";

export type PublicSection =
  | "home"
  | "algorithms"
  | "academic"
  | "docs"
  | "pricing"
  | "status"
  | "security";

const PUBLIC_NAV: Array<{
  href: string;
  label: string;
  section: PublicSection;
}> = [
  { href: "/algorithms", label: "算法", section: "algorithms" },
  { href: "/docs", label: "文档", section: "docs" },
  { href: "/academic", label: "学术合作", section: "academic" },
  { href: "/pricing", label: "定价", section: "pricing" },
  { href: "/status", label: "状态", section: "status" },
  { href: "/security", label: "安全", section: "security" },
];

function navLinkClass(active: boolean): string {
  return (
    "rounded-md px-2.5 py-2 text-sm font-medium transition " +
    (active
      ? "bg-primary/10 text-primary"
      : "text-muted-foreground hover:bg-muted hover:text-foreground")
  );
}

export function PublicShell({
  active,
  children,
}: {
  active: PublicSection;
  children: ReactNode;
}): JSX.Element {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
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
              aria-label="Public navigation"
              className="flex min-w-0 flex-wrap items-center justify-end gap-1"
            >
              {PUBLIC_NAV.map((item) => (
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
            <Link
              href="/auth/signup"
              className="inline-flex min-h-touch shrink-0 items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              立即注册
            </Link>
          </div>
        </div>
      </header>

      <div className="min-w-0 flex-1">{children}</div>

      <footer className="border-t border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6 text-sm text-muted-foreground sm:px-6 md:flex-row md:items-center md:justify-between">
          <p>OptiCloud · 通用优化与预测云</p>
          <nav aria-label="Public footer navigation" className="flex flex-wrap gap-x-4 gap-y-2">
            {PUBLIC_NAV.map((item) => (
              <Link key={item.href} href={item.href} className="hover:text-foreground">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </main>
  );
}

export function PublicPageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
  meta?: ReactNode;
}): JSX.Element {
  return (
    <section className="border-b border-border bg-muted/40">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-sm font-semibold uppercase text-muted-foreground">{eyebrow}</p>
          )}
          <h1 className="mt-2 text-balance text-3xl font-bold leading-tight md:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
            {description}
          </p>
          {meta && <div className="mt-4 flex min-w-0 flex-wrap gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex min-w-0 flex-wrap gap-3 lg:justify-end">{actions}</div>}
      </div>
    </section>
  );
}
