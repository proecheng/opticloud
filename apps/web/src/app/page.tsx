/** Landing page (UX-DR8 Page Direction Map: Landing → SSR / Direction "Engineer-First / 实证克制"). */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export default function LandingPage(): JSX.Element {
  const common = useTranslations("common");
  const t = useTranslations("landing");

  return (
    <main className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-primary" />
            <span className="font-semibold text-lg">OptiCloud</span>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/algorithms"
              className="text-muted-foreground hover:text-foreground"
            >
              {common("nav.algorithms")}
            </Link>
            <Link
              href="/academic"
              className="text-muted-foreground hover:text-foreground"
            >
              {common("nav.academic")}
            </Link>
            <Link href="/docs" className="text-muted-foreground hover:text-foreground">
              {common("nav.docs")}
            </Link>
            <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
              {common("nav.pricing")}
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              {common("nav.signup")}
            </Link>
            <LanguageSwitcher />
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="bg-background py-20">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h1 className="text-balance text-4xl font-bold leading-tight md:text-5xl">
            {t("hero.title")}
          </h1>
          <p className="mt-3 text-balance text-xl text-muted-foreground md:text-2xl">
            {t("hero.subtitle")}
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-muted-foreground">
            {t("hero.body")}{" "}
            <strong className="text-foreground">{t("hero.cost")}</strong>
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 md:flex-row">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600"
            >
              {common("actions.signupArrow")}
            </Link>
            <Link
              href="/algorithms"
              className="min-h-touch rounded-md border border-border px-6 py-3 font-medium hover:bg-muted"
            >
              {common("actions.browseAlgorithms")}
            </Link>
          </div>
        </div>
      </section>

      {/* Hello World preview */}
      <section className="border-t border-border bg-muted py-16">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-balance text-2xl font-semibold">{t("hello.title")}</h2>
          <pre className="mt-4 overflow-x-auto rounded-lg bg-background p-4 font-mono text-xs leading-relaxed shadow-sm">
            <code>{t("hello.snippet")}</code>
          </pre>
        </div>
      </section>

      <footer className="mt-auto border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>{t("footer")}</p>
      </footer>
    </main>
  );
}
