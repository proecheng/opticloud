"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { RFC7807Panel, StatusCard } from "@opticloud/ui";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePreferredLocale } from "@/components/LocaleProvider";
import { confirmGuardianConfirmation, OptiCloudClientError } from "@/lib/api";
import { translateWithLocale } from "@/lib/messages";

function GuardianConfirmationContent(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);
  const token = searchParams.get("token") ?? "";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!token || confirmed || error) return;
    setLoading(true);
    void (async () => {
      try {
        await confirmGuardianConfirmation({ token });
        setConfirmed(true);
      } catch (err) {
        if (err instanceof OptiCloudClientError) {
          setError(err);
        } else {
          setError(
            new OptiCloudClientError({
              status: 0,
              title: t("guardian.networkError"),
              detail: String((err as Error).message),
            }),
          );
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [token, confirmed, error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <h1 className="text-2xl font-bold">{t("guardian.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("guardian.description")}
        </p>

        {loading && (
          <StatusCard
            variant="info"
            title={t("guardian.loading")}
            ariaLabel="guardian.confirmation.loading"
          />
        )}
        {confirmed && (
          <StatusCard
            variant="ok"
            title={t("guardian.successTitle")}
            description={t("guardian.successDescription")}
            ariaLabel="guardian.confirmation.success"
          />
        )}
        {error && (
          <div className="mt-4">
            {error.errors && error.errors.length > 0 ? (
              <RFC7807Panel
                payload={{
                  title: error.title,
                  status: error.status,
                  detail: error.detail,
                  errors: error.errors,
                  next_action_url: error.next_action_url,
                }}
              />
            ) : (
              <StatusCard
                variant="error"
                title={error.title}
                description={error.detail}
                ariaLabel={`guardian.confirmation.error.${error.status}`}
              />
            )}
          </div>
        )}

        {confirmed && (
          <button
            type="button"
            onClick={() => router.push("/auth/login")}
            className="mt-4 min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground hover:bg-primary-600"
          >
            {t("guardian.returnLogin")}
          </button>
        )}
      </div>
    </main>
  );
}

export default function GuardianConfirmationPage(): JSX.Element {
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);

  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-muted p-4">
          <div className="w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
            <StatusCard
              variant="info"
              title={t("guardian.suspense")}
              ariaLabel="guardian.confirmation.suspense"
            />
          </div>
        </main>
      }
    >
      <GuardianConfirmationContent />
    </Suspense>
  );
}
