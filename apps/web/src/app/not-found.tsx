/** 404 page — UX Spec Step 9 Error Pages Direction "Recovery-Forward". */
"use client";

import Link from "next/link";

import { EmptyState } from "@opticloud/ui";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePreferredLocale } from "@/components/LocaleProvider";
import { translateWithLocale } from "@/lib/messages";

export default function NotFound(): JSX.Element {
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4">
      <div className="mb-4">
        <LanguageSwitcher />
      </div>
      <EmptyState
        ariaLabel="page.not_found"
        icon="🔍"
        title={t("notFound.title")}
        description={t("notFound.description")}
        action={
          <Link
            href="/"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
          >
            {t("notFound.action")}
          </Link>
        }
      />
    </main>
  );
}
