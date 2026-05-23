import Link from "next/link";
import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export function LegalShell({
  title,
  body,
}: {
  title: string;
  body: string;
}): JSX.Element {
  const common = useTranslations("common");
  const legal = useTranslations("legal");

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold">
            OptiCloud
          </Link>
          <LanguageSwitcher />
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold">{title}</h1>
        <p className="mt-4 max-w-2xl text-muted-foreground">{body}</p>
        <div className="mt-6 rounded-md border border-warning/50 bg-warning/10 p-4 text-sm text-warning">
          {common("legal.reviewPending")}
        </div>
        <Link
          href="/"
          className="mt-8 inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
        >
          {legal("back")}
        </Link>
      </section>
    </main>
  );
}
