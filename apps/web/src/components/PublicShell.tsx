import Link from "next/link";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

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
  labelKey: "nav.algorithms" | "nav.docs" | "nav.academic" | "nav.pricing" | "nav.status" | "nav.security";
  section: PublicSection;
}> = [
  { href: "/algorithms", labelKey: "nav.algorithms", section: "algorithms" },
  { href: "/docs", labelKey: "nav.docs", section: "docs" },
  { href: "/academic", labelKey: "nav.academic", section: "academic" },
  { href: "/pricing", labelKey: "nav.pricing", section: "pricing" },
  { href: "/status", labelKey: "nav.status", section: "status" },
  { href: "/security", labelKey: "nav.security", section: "security" },
];

function navLinkClass(active: boolean): string {
  return (
    "inline-flex min-h-touch shrink-0 items-center rounded-md px-3 py-2 text-sm font-medium transition " +
    (active
      ? "bg-primary/10 text-primary shadow-sm"
      : "text-muted-foreground hover:bg-muted hover:text-foreground")
  );
}

function BrandMark(): JSX.Element {
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
          Optimization & Forecasting
        </span>
      </span>
    </Link>
  );
}

export function PublicShell({
  active,
  children,
}: {
  active: PublicSection;
  children: ReactNode;
}): JSX.Element {
  const t = useTranslations("common");

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary focus:shadow-lg focus:ring-2 focus:ring-primary/40"
      >
        {t("a11y.skipMain")}
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <BrandMark />

          <nav
            aria-label="Account navigation"
            className="flex min-w-0 flex-1 items-center justify-end gap-2"
          >
            <div className="hidden shrink-0 md:block">
              <LanguageSwitcher />
            </div>
            <Link
              href="/auth/signup"
              className="inline-flex min-h-touch shrink-0 items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              {t("nav.signup")}
            </Link>
          </nav>

          <div className="flex w-full min-w-0 items-center gap-2 md:w-auto">
            <nav
              aria-label="Public navigation"
              className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pb-1 md:flex-none md:justify-end md:overflow-visible md:pb-0"
            >
              {PUBLIC_NAV.map((item) => (
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
            <div className="shrink-0 md:hidden">
              <LanguageSwitcher />
            </div>
          </div>
        </div>
      </header>

      <main id="main-content" className="min-w-0 flex-1">
        {children}
      </main>

      <footer className="border-t border-border bg-background">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 text-sm text-muted-foreground sm:px-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
          <div className="min-w-0">
            <p className="font-medium text-foreground">OptiCloud</p>
            <p className="mt-1">{t("footer.summary")}</p>
          </div>
          <nav
            aria-label="Public footer navigation"
            className="flex min-w-0 flex-wrap gap-x-4 gap-y-2 md:justify-end"
          >
            {PUBLIC_NAV.map((item) => (
              <Link key={item.href} href={item.href} className="hover:text-foreground">
                {t(item.labelKey)}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </div>
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
    <section className="border-b border-border bg-muted/30">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-normal text-primary">
              {eyebrow}
            </p>
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
