/** /docs/quickstart — Story 1.8 onboarding support entry. */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export default function QuickstartPage(): JSX.Element {
  const t = useTranslations("quickstart");

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-12">
      <div className="flex items-center justify-between gap-3">
        <Link href="/welcome" className="text-sm text-primary hover:underline">
          {t("back")}
        </Link>
        <LanguageSwitcher />
      </div>

      <h1 className="mt-4 text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {t("description")}
      </p>

      <ol className="mt-8 space-y-5">
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">{t("steps.apiKey.title")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("steps.apiKey.body")}
          </p>
        </li>
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">{t("steps.postman.title")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("steps.postman.body")}
          </p>
        </li>
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">{t("steps.lp.title")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("steps.lp.body")}
          </p>
        </li>
      </ol>

      <Link
        href="/welcome"
        className="mt-8 inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
      >
        {t("continue")}
      </Link>
    </main>
  );
}
