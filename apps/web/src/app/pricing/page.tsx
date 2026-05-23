/** /pricing — v1 bilingual key-page shell for Story 1.10. */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export default function PricingPage(): JSX.Element {
  const common = useTranslations("common");
  const t = useTranslations("pricing");

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold">
            OptiCloud
          </Link>
          <div className="flex items-center gap-3">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600"
            >
              {common("nav.signup")}
            </Link>
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">{t("description")}</p>

        <div className="mt-8 rounded-lg border border-border bg-muted/40 p-6">
          <h2 className="font-semibold">{t("plansTitle")}</h2>
          <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
            <li>{t("plans.starter")}</li>
            <li>{t("plans.academic")}</li>
            <li>{t("plans.api")}</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
