/** 404 page — UX Spec Step 9 Error Pages Direction "Recovery-Forward". */
import Link from "next/link";
import { useTranslations } from "next-intl";

import { EmptyState } from "@opticloud/ui";

export default function NotFound(): JSX.Element {
  const t = useTranslations("notFound");

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <EmptyState
        ariaLabel="page.not_found"
        icon=""
        title={t("title")}
        description={t("description")}
        action={
          <Link
            href="/"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
          >
            {t("action")}
          </Link>
        }
      />
    </main>
  );
}
