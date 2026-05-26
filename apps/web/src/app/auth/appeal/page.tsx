"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ConfirmationModal, RFC7807Panel, StatusCard } from "@opticloud/ui";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePreferredLocale } from "@/components/LocaleProvider";
import {
  OptiCloudClientError,
  acceptRiskAppealMergeOffer,
  getRiskAppealStatus,
  submitRiskAppeal,
  type RiskAppealStatusResponse,
} from "@/lib/api";
import { translateWithLocale } from "@/lib/messages";

interface FormState {
  phone: string;
  email: string;
  reason: string;
  team_size: string;
  evidence_note: string;
}

function formatDate(value: string | null, locale: string): string {
  if (!value) return "";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusVariant(status: RiskAppealStatusResponse["status"]) {
  if (status === "approved" || status === "merge_accepted") return "ok";
  if (status === "merge_offered") return "warning";
  if (status === "rejected") return "error";
  return "info";
}

function AppealPageContent(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialToken = searchParams.get("token") ?? "";
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);
  const [form, setForm] = useState<FormState>({
    phone: "",
    email: "",
    reason: "",
    team_size: "1",
    evidence_note: "",
  });
  const [token, setToken] = useState(initialToken);
  const [status, setStatus] = useState<RiskAppealStatusResponse | null>(null);
  const [trackingUrl, setTrackingUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);
  const [mergeConfirmOpen, setMergeConfirmOpen] = useState(false);
  const showForm = !initialToken || (!loading && !status && error !== null);

  const loadStatus = async (nextToken: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRiskAppealStatus(nextToken);
      setStatus(result);
      setToken(nextToken);
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: t("appeal.networkError"),
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!initialToken) return;
    void loadStatus(initialToken);
  }, [initialToken]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setStatus(null);
    setTrackingUrl(null);
    try {
      const result = await submitRiskAppeal({
        phone: form.phone,
        email: form.email,
        reason: form.reason,
        team_size: Number(form.team_size),
        evidence: form.evidence_note
          ? { contact_note: form.evidence_note }
          : {},
      });
      setTrackingUrl(result.tracking_url);
      const nextToken = result.tracking_url.split("token=")[1] ?? "";
      if (nextToken) {
        await loadStatus(nextToken);
      }
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: t("appeal.networkError"),
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptMerge = async (): Promise<void> => {
    if (!status || !token) return;
    setLoading(true);
    setError(null);
    try {
      await acceptRiskAppealMergeOffer(status.appeal_id, token);
      setMergeConfirmOpen(false);
      await loadStatus(token);
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: t("appeal.networkError"),
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-muted p-4">
      <div className="mx-auto w-full max-w-3xl py-8">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <section className="rounded-lg border border-border bg-background p-6 shadow">
          <header>
            <h1 className="text-2xl font-bold">{t("appeal.title")}</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("appeal.subtitle")}
            </p>
          </header>

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
                  ariaLabel={`appeal.error.${error.status}`}
                />
              )}
            </div>
          )}

          {loading && (
            <div className="mt-4">
              <StatusCard
                variant="info"
                title={t("appeal.loading")}
                ariaLabel="appeal.loading"
              />
            </div>
          )}

          {status && (
            <div className="mt-4 space-y-4">
              <StatusCard
                variant={statusVariant(status.status)}
                title={t(`appeal.status.${status.status}`)}
                description={
                  status.sla_due_at
                    ? `${t("appeal.slaDue")} ${formatDate(status.sla_due_at, locale)}`
                    : status.decision_reason ?? undefined
                }
                ariaLabel={`appeal.status.${status.status}`}
              />
              {status.evidence_summary.length > 0 && (
                <div className="rounded-md border border-border bg-muted/40 p-4">
                  <h2 className="text-sm font-semibold">
                    {t("appeal.evidenceTitle")}
                  </h2>
                  <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                    {status.evidence_summary.map((item) => (
                      <li key={`${item.rule_code}-${item.created_at}`}>
                        <span className="font-medium text-foreground">
                          {item.label_zh}
                        </span>{" "}
                        · {item.source}
                        {item.summary ? ` · ${item.summary}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {status.merge_offer && (
                <div className="rounded-md border border-warning bg-warning/5 p-4">
                  <h2 className="font-semibold">{status.merge_offer.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {status.merge_offer.description}
                  </p>
                  <button
                    type="button"
                    onClick={() => setMergeConfirmOpen(true)}
                    className="mt-3 min-h-touch rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground hover:bg-primary-600"
                  >
                    {t("appeal.acceptMerge")}
                  </button>
                </div>
              )}
              {status.next_action_url && (
                <button
                  type="button"
                  onClick={() => router.push(status.next_action_url ?? "/auth/login")}
                  className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground hover:bg-primary-600"
                >
                  {t("appeal.returnLogin")}
                </button>
              )}
            </div>
          )}

          {showForm && (
            <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
              <fieldset disabled={loading}>
                <label htmlFor="phone" className="mb-1 block text-sm font-medium">
                  {t("appeal.phone")}
                </label>
                <input
                  id="phone"
                  type="tel"
                  required
                  value={form.phone}
                  onChange={(event) =>
                    setForm({ ...form, phone: event.target.value })
                  }
                  placeholder="+8613800138000"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </fieldset>
              <fieldset disabled={loading}>
                <label htmlFor="email" className="mb-1 block text-sm font-medium">
                  {t("appeal.email")}
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(event) =>
                    setForm({ ...form, email: event.target.value })
                  }
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </fieldset>
              <fieldset disabled={loading}>
                <label
                  htmlFor="team-size"
                  className="mb-1 block text-sm font-medium"
                >
                  {t("appeal.teamSize")}
                </label>
                <input
                  id="team-size"
                  type="number"
                  min={1}
                  max={500}
                  required
                  value={form.team_size}
                  onChange={(event) =>
                    setForm({ ...form, team_size: event.target.value })
                  }
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </fieldset>
              <fieldset disabled={loading}>
                <label htmlFor="reason" className="mb-1 block text-sm font-medium">
                  {t("appeal.reason")}
                </label>
                <textarea
                  id="reason"
                  required
                  minLength={10}
                  value={form.reason}
                  onChange={(event) =>
                    setForm({ ...form, reason: event.target.value })
                  }
                  className="min-h-28 w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </fieldset>
              <fieldset disabled={loading}>
                <label
                  htmlFor="evidence-note"
                  className="mb-1 block text-sm font-medium"
                >
                  {t("appeal.evidenceNote")}
                </label>
                <textarea
                  id="evidence-note"
                  value={form.evidence_note}
                  onChange={(event) =>
                    setForm({ ...form, evidence_note: event.target.value })
                  }
                  className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </fieldset>
              <button
                type="submit"
                disabled={
                  loading ||
                  !form.phone ||
                  !form.email ||
                  form.reason.trim().length < 10
                }
                className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
              >
                {t("appeal.submit")}
              </button>
            </form>
          )}

          {trackingUrl && (
            <div className="mt-4 rounded-md border border-border bg-muted/40 p-3 text-sm">
              <span className="font-medium">{t("appeal.trackingReady")}</span>{" "}
              <a href={trackingUrl} className="text-primary hover:underline">
                {trackingUrl}
              </a>
            </div>
          )}
        </section>
      </div>
      <ConfirmationModal
        open={mergeConfirmOpen}
        onClose={() => setMergeConfirmOpen(false)}
        onConfirm={() => {
          void handleAcceptMerge();
        }}
        variant="p5_alert"
        ariaLabel="appeal.merge.confirm"
        title={t("appeal.mergeConfirmTitle")}
        description={t("appeal.mergeConfirmDescription")}
        confirmLabel={t("appeal.acceptMerge")}
        cancelLabel={t("common.later")}
      />
    </main>
  );
}

export default function AppealPage(): JSX.Element {
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);

  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-muted p-4">
          <div className="w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
            <StatusCard
              variant="info"
              title={t("appeal.loading")}
              ariaLabel="appeal.suspense"
            />
          </div>
        </main>
      }
    >
      <AppealPageContent />
    </Suspense>
  );
}
