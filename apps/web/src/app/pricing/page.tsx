/** /pricing — M4.5 buyer-safe pricing page. */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const PLAN_KEYS = ["free", "starter", "pro", "team", "enterprise"] as const;

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

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {PLAN_KEYS.map((plan) => (
            <section key={plan} className="rounded-lg border border-border bg-muted/40 p-5">
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                {t(`plans.${plan}.status`)}
              </p>
              <h2 className="mt-2 text-xl font-semibold">{t(`plans.${plan}.name`)}</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {t(`plans.${plan}.summary`)}
              </p>
            </section>
          ))}
        </div>

        <div className="mt-8 rounded-lg border border-border bg-background p-5">
          <h2 className="font-semibold">{t("buyerSafeTitle")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t("buyerSafeCaveat")}</p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-center text-sm font-medium text-primary-foreground hover:bg-primary-600"
            >
              {common("actions.signup")}
            </Link>
            <Link
              href="/docs/quickstart"
              className="min-h-touch rounded-md border border-border px-4 py-2 text-center text-sm font-medium hover:bg-muted"
            >
              {t("docsCta")}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
