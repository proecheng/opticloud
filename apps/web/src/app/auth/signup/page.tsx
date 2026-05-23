/** Signup page — Story 1.1a J1 Vertical Slice 第 1a 段.
 *
 * FR A1: 手机号+邮箱双因素验证（OTP stub — 实际 OTP 在 Story 1.x）
 * FR A9: Onboarding Wizard ≤ 5 步骤（v1 实施 stub: 1 步表单 + 1 步成功页）
 * FR A4: 教育版邮箱白名单自动激活
 */
"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { RFC7807Panel, SignupWizard, StatusCard } from "@opticloud/ui";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import {
  type GuardianConsentPendingResponse,
  OptiCloudClientError,
  type SignupResult,
  signup,
} from "@/lib/api";
import {
  type OnboardingStepId,
  buildOnboardingSteps,
  createInitialOnboardingState,
  dismissOnboarding,
  getOnboardingStorageKey,
  loadOnboardingState,
  markOnboardingStep,
  markSupportPromptShown,
  saveOnboardingState,
  shouldShowOnboardingSupport,
} from "@/lib/onboarding";

const QUICKSTART_URL = "/docs/quickstart";

function isGuardianConsentPending(
  result: SignupResult,
): result is GuardianConsentPendingResponse {
  return "status" in result && result.status === "guardian_consent_required";
}

interface FormState {
  phone: string;
  email: string;
  ageYears: string;
  guardianEmail: string;
  guardianConsentToken: string;
}

export default function SignupPage(): JSX.Element {
  const router = useRouter();
  const common = useTranslations("common");
  const t = useTranslations("signup");
  const onboarding = useTranslations("onboarding");
  const [form, setForm] = useState<FormState>({
    phone: "",
    email: "",
    ageYears: "",
    guardianEmail: "",
    guardianConsentToken: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);
  const [wizardState, setWizardState] = useState(() =>
    createInitialOnboardingState(null),
  );
  const [supportVisible, setSupportVisible] = useState(false);
  const [guardianPending, setGuardianPending] = useState<{
    requestId: string;
    guardianEmail: string;
    devToken: string | null;
  } | null>(null);

  useEffect(() => {
    const loaded = loadOnboardingState(sessionStorage, null);
    setWizardState(loaded);
    saveOnboardingState(sessionStorage, loaded);
  }, []);

  useEffect(() => {
    if (wizardState.completed || wizardState.dismissed) return;
    const timeout = window.setInterval(() => {
      if (shouldShowOnboardingSupport(wizardState)) {
        const shown = markSupportPromptShown(wizardState);
        setWizardState(shown);
        saveOnboardingState(sessionStorage, shown);
        setSupportVisible(true);
      }
    }, 1000);
    return () => window.clearInterval(timeout);
  }, [wizardState]);

  const ageYears = Number.parseInt(form.ageYears, 10);
  const isMinorRequiringGuardian =
    Number.isFinite(ageYears) && ageYears >= 14 && ageYears < 18;
  const stepLabels: Record<OnboardingStepId, string> = {
    signup: onboarding("steps.signup"),
    verify: onboarding("steps.verify"),
    "api-key": onboarding("steps.api-key"),
    postman: onboarding("steps.postman"),
    "hello-world": onboarding("steps.hello-world"),
  };
  const wizardStateLabels = {
    completed: onboarding("states.completed"),
    current: onboarding("states.current"),
    pending: onboarding("states.pending"),
    skipped: onboarding("states.skipped"),
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await signup({
        phone: form.phone,
        email: form.email,
        age_years: ageYears,
        guardian_email: isMinorRequiringGuardian ? form.guardianEmail : undefined,
        guardian_consent_request_id: guardianPending?.requestId,
        guardian_consent_token:
          guardianPending && form.guardianConsentToken
            ? form.guardianConsentToken
            : undefined,
      });
      if (isGuardianConsentPending(result)) {
        setGuardianPending({
          requestId: result.request_id,
          guardianEmail: result.guardian_email,
          devToken: result.dev_guardian_consent_token,
        });
        setForm((current) => ({
          ...current,
          guardianEmail: result.guardian_email,
          guardianConsentToken: result.dev_guardian_consent_token ?? "",
        }));
        return;
      }
      // Store JWT in sessionStorage (production: HttpOnly cookie)
      sessionStorage.setItem("jwt_access", result.jwt_access);
      sessionStorage.setItem("jwt_refresh", result.jwt_refresh);
      sessionStorage.setItem("user_id", result.user_id);
      sessionStorage.setItem("edu_tier", String(result.edu_tier));
      const completedSignup = markOnboardingStep(wizardState, "signup", "complete");
      const verified = markOnboardingStep(
        { ...completedSignup, userKey: result.user_id },
        "verify",
        "complete",
      );
      saveOnboardingState(sessionStorage, verified);
      sessionStorage.removeItem(getOnboardingStorageKey(null));
      router.push("/welcome");
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: t("errors.networkTitle"),
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-4xl">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <SignupWizard
          className="mb-4"
          ariaLabel="onboarding.signup"
          title={t("wizard.title")}
          description={t("wizard.description")}
          steps={buildOnboardingSteps(wizardState, stepLabels)}
          stateLabels={wizardStateLabels}
          controlLabels={{
            resume: onboarding("controls.resume"),
            skip: onboarding("controls.skip"),
          }}
          onSkip={() => {
            const dismissed = dismissOnboarding(wizardState);
            setWizardState(dismissed);
            setSupportVisible(false);
            saveOnboardingState(sessionStorage, dismissed);
          }}
          onResume={() => setSupportVisible(false)}
          supportPrompt={{
            visible: supportVisible,
            title: t("wizard.supportTitle"),
            description: t("wizard.supportDescription"),
            actionLabel: t("wizard.supportAction"),
            onAction: () => setSupportVisible(false),
            secondaryAction: {
              label: common("actions.openQuickstart"),
              href: QUICKSTART_URL,
            },
            dismissLabel: common("actions.later"),
            onDismiss: () => setSupportVisible(false),
          }}
        />
        <div className="mx-auto w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
          <header className="mb-6 text-center">
            <h1 className="text-2xl font-bold">{t("form.title")}</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("form.subtitle")}
            </p>
          </header>

          {error && (
            <div className="mb-4">
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
                  ariaLabel={`error.signup.${error.status}`}
                />
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="phone" className="mb-1 block text-sm font-medium">
                {t("form.phone")}
                <span className="ml-1 text-danger" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="phone"
                type="tel"
                required
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="+8613800138000"
                autoComplete="tel"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                aria-describedby="phone-hint"
              />
              <p id="phone-hint" className="mt-1 text-xs text-muted-foreground">
                {t("form.phoneHint")}
              </p>
            </fieldset>

            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="email" className="mb-1 block text-sm font-medium">
                {t("form.email")}
                <span className="ml-1 text-danger" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                autoComplete="email"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                aria-describedby="email-hint"
              />
              <p id="email-hint" className="mt-1 text-xs text-muted-foreground">
                {t("form.emailHint")}
              </p>
            </fieldset>

            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="age-years" className="mb-1 block text-sm font-medium">
                {t("form.age")}
                <span className="ml-1 text-danger" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="age-years"
                type="number"
                min={0}
                max={120}
                required
                value={form.ageYears}
                onChange={(e) => {
                  setForm({
                    ...form,
                    ageYears: e.target.value,
                    guardianConsentToken: "",
                  });
                  setGuardianPending(null);
                }}
                placeholder="18"
                autoComplete="off"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                aria-describedby="age-hint"
              />
              <p id="age-hint" className="mt-1 text-xs text-muted-foreground">
                {t("form.ageHint")}
              </p>
            </fieldset>

            {isMinorRequiringGuardian && (
              <fieldset className="mb-4" disabled={loading}>
                <label
                  htmlFor="guardian-email"
                  className="mb-1 block text-sm font-medium"
                >
                  {t("form.guardianEmail")}
                  <span className="ml-1 text-danger" aria-hidden="true">
                    *
                  </span>
                </label>
                <input
                  id="guardian-email"
                  type="email"
                  required
                  value={form.guardianEmail}
                  onChange={(e) => {
                    setForm({
                      ...form,
                      guardianEmail: e.target.value,
                      guardianConsentToken: "",
                    });
                    setGuardianPending(null);
                  }}
                  placeholder="guardian@example.com"
                  autoComplete="email"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  aria-describedby="guardian-email-hint"
                />
                <p
                  id="guardian-email-hint"
                  className="mt-1 text-xs text-muted-foreground"
                >
                  {t("form.guardianEmailHint")}
                </p>
              </fieldset>
            )}

            {guardianPending && (
              <div className="mb-4">
                <StatusCard
                  variant="warning"
                  title={t("form.guardianTitle")}
                  description={t("form.guardianDescription", {
                    email: guardianPending.guardianEmail,
                  })}
                  ariaLabel="signup.guardian_consent_required"
                />
                <label
                  htmlFor="guardian-token"
                  className="mb-1 mt-3 block text-sm font-medium"
                >
                  {t("form.guardianToken")}
                </label>
                <input
                  id="guardian-token"
                  type="text"
                  value={form.guardianConsentToken}
                  onChange={(e) =>
                    setForm({ ...form, guardianConsentToken: e.target.value })
                  }
                  placeholder={t("form.guardianTokenPlaceholder")}
                  autoComplete="one-time-code"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={
                loading ||
                !form.phone ||
                !form.email ||
                !form.ageYears ||
                (isMinorRequiringGuardian && !form.guardianEmail) ||
                (guardianPending !== null && !form.guardianConsentToken)
              }
              className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600 disabled:opacity-50"
            >
              {loading
                ? t("form.loading")
                : guardianPending
                  ? t("form.submitGuardian")
                  : t("form.submit")}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            {t("form.termsPrefix")}{" "}
            <a href="/legal/tos" className="text-primary hover:underline">
              {t("form.tos")}
            </a>{" "}
            +{" "}
            <a href="/legal/privacy" className="text-primary hover:underline">
              {t("form.privacy")}
            </a>{" "}
            {t("form.pipl")}
          </p>
        </div>
      </div>
    </main>
  );
}
