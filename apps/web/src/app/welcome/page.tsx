/** Welcome page — Story 1.1b + Story 3.1 整合.
 *
 * Flow:
 *   1. 自动调 createApiKey 拿首个 API Key
 *   2. ConfirmationModal 展示 cURL + 一键 Postman
 *   3. "试跑 LP" 按钮 — 真实调 solver-orchestrator + 显示结果
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  APIKeyManager,
  ConfirmationModal,
  RFC7807Panel,
  SignupWizard,
  StatusCard,
} from "@opticloud/ui";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePreferredLocale } from "@/components/LocaleProvider";
import {
  APIKeyCreateResponse,
  OptiCloudClientError,
  OptimizationResponse,
  createApiKey,
  postOptimization,
} from "@/lib/api";
import { translateWithLocale } from "@/lib/messages";
import {
  buildOnboardingSteps,
  createInitialOnboardingState,
  dismissOnboarding,
  loadOnboardingState,
  markOnboardingStep,
  markSupportPromptShown,
  resumeOnboarding,
  saveOnboardingState,
  shouldShowOnboardingSupport,
} from "@/lib/onboarding";
import { downloadPostmanCollection } from "@/lib/postman";

const SOLVER_URL =
  process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002";
const QUICKSTART_URL = "/docs/quickstart";
const EXCEL_CONSOLE_URL = "/console/excel";

export default function WelcomePage(): JSX.Element {
  const router = useRouter();
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);
  const [apiKey, setApiKey] = useState<APIKeyCreateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // LP solve state
  const [solving, setSolving] = useState(false);
  const [lpResult, setLpResult] = useState<OptimizationResponse | null>(null);
  const [lpError, setLpError] = useState<OptiCloudClientError | null>(null);
  const [wizardState, setWizardState] = useState(() =>
    createInitialOnboardingState(null),
  );
  const [supportVisible, setSupportVisible] = useState(false);

  useEffect(() => {
    const jwt = sessionStorage.getItem("jwt_access");
    const userId = sessionStorage.getItem("user_id");
    if (!jwt || jwt.trim() === "") {
      router.push("/auth/signup");
      return;
    }
    const loaded = loadOnboardingState(sessionStorage, userId);
    const verified = markOnboardingStep(loaded, "verify", "complete");
    setWizardState(verified);
    saveOnboardingState(sessionStorage, verified);
    void (async () => {
      try {
        const result = await createApiKey(jwt, {
          label: "First Key (auto-generated)",
          scope: ["optimize:write", "predict:write", "billing:read"],
        });
        setApiKey(result);
        const withKey = markOnboardingStep(verified, "api-key", "complete");
        setWizardState(withKey);
        saveOnboardingState(sessionStorage, withKey);
        setModalOpen(true);
      } catch (err) {
        setError(String((err as Error).message));
      }
    })();
  }, [router]);

  useEffect(() => {
    if (wizardState.completed || wizardState.dismissed) return;
    const timeout = window.setInterval(() => {
      if (modalOpen) return;
      if (shouldShowOnboardingSupport(wizardState)) {
        const shown = markSupportPromptShown(wizardState);
        setWizardState(shown);
        saveOnboardingState(sessionStorage, shown);
        setSupportVisible(true);
      }
    }, 1000);
    return () => window.clearInterval(timeout);
  }, [modalOpen, wizardState]);

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <StatusCard
          variant="error"
          title={t("welcome.createKeyError")}
          description={error}
          ariaLabel="welcome.create_key.error"
        />
      </main>
    );
  }

  if (!apiKey) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted">
        <div className="text-center">
          <div className="mb-4 text-4xl" aria-hidden="true">
            ⏳
          </div>
          <p className="text-muted-foreground">{t("welcome.loadingKey")}</p>
        </div>
      </main>
    );
  }

  const cURLExample = `curl -X POST ${SOLVER_URL}/v1/optimizations \\
  -H "Authorization: Bearer ${apiKey.api_key}" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d '{"task_type":"lp","minimize":{"c":[1,1]},"st":{"A":[[1,1]],"b":[10]}}'`;

  const handleCopy = (): void => {
    void navigator.clipboard.writeText(cURLExample);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePostman = (): void => {
    downloadPostmanCollection({ apiKey: apiKey.api_key });
    const next = markOnboardingStep(wizardState, "postman", "complete");
    setWizardState(next);
    saveOnboardingState(sessionStorage, next);
  };

  const handleSolve = async (): Promise<void> => {
    setSolving(true);
    setLpError(null);
    setLpResult(null);
    try {
      const result = await postOptimization(apiKey.api_key, {
        task_type: "lp",
        // 案例 1 — 同城配送：min 5x₁+8x₂+12x₃+10y₁+4y₂+6y₃ (2车3客分配)
        minimize: { c: [5, 8, 12, 10, 4, 6] },
        st: {
          A: [
            [1, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 1],
            [-1, 0, 0, -1, 0, 0],
            [0, -1, 0, 0, -1, 0],
            [0, 0, -1, 0, 0, -1],
          ],
          b: [1, 1, 1, -1, -1, -1],
        },
      });
      setLpResult(result);
      if (result.status === "completed") {
        const next = markOnboardingStep(wizardState, "hello-world", "complete");
        setWizardState(next);
        saveOnboardingState(sessionStorage, next);
      }
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setLpError(err);
      } else {
        setLpError(
          new OptiCloudClientError({
            status: 0,
            title: "Network Error",
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setSolving(false);
    }
  };
  const wizardStateText = {
    completed: t("signup.stepCompleted"),
    current: t("signup.stepCurrent"),
    pending: t("signup.stepPending"),
    skipped: t("signup.stepSkipped"),
  };
  const wizardStepLabels = {
    signup: t("signup.stepSignup"),
    verify: t("signup.stepVerify"),
    "api-key": t("signup.stepApiKey"),
    postman: t("signup.stepPostman"),
    "hello-world": t("signup.stepHelloWorld"),
  };

  return (
    <main className="min-h-screen bg-muted p-4">
      <div className="mx-auto max-w-3xl py-12">
        <div className="mb-4 flex justify-end">
          <LanguageSwitcher />
        </div>
        <SignupWizard
          className="mb-6"
          ariaLabel="onboarding.welcome"
          title={t("welcome.wizardTitle")}
          description={t("welcome.wizardDescription")}
          steps={buildOnboardingSteps(wizardState, wizardStepLabels)}
          stateText={wizardStateText}
          actionLabels={{
            resume: t("welcome.wizardResume"),
            skip: t("welcome.wizardSkip"),
          }}
          onSkip={() => {
            const dismissed = dismissOnboarding(wizardState);
            setWizardState(dismissed);
            setSupportVisible(false);
            saveOnboardingState(sessionStorage, dismissed);
          }}
          onResume={() => {
            const resumed = resumeOnboarding(wizardState);
            setWizardState(resumed);
            setSupportVisible(false);
            saveOnboardingState(sessionStorage, resumed);
          }}
          supportPrompt={{
            visible: supportVisible,
            title: t("welcome.supportTitle"),
            description: t("welcome.supportDescription"),
            actionLabel: t("welcome.supportAction"),
            onAction: () => setSupportVisible(false),
            dismissLabel: t("common.later"),
            onDismiss: () => setSupportVisible(false),
            secondaryAction: {
              label: t("common.openQuickstart"),
              href: QUICKSTART_URL,
            },
          }}
        />
        <header className="mb-8 text-center">
          <div className="mb-3 text-5xl" aria-hidden="true">
            🎉
          </div>
          <h1 className="text-balance text-3xl font-bold">
            {t("welcome.title")}
          </h1>
          <p className="mt-2 text-balance text-muted-foreground">
            {t("welcome.description")}
          </p>
        </header>

        <APIKeyManager
          newKeyValue={apiKey.api_key}
          keys={[
            {
              id: apiKey.id,
              prefix: apiKey.prefix,
              label: apiKey.label,
              scope: apiKey.scope,
              createdAt: apiKey.created_at,
              expiresAt: apiKey.expires_at,
            },
          ]}
          ariaLabel="welcome.api_keys"
        />

        {/* 🧪 试跑 LP 求解（Story 3.1 in-browser demo）*/}
        <section className="mt-6 rounded-lg border border-primary/30 bg-primary/5 p-6">
          <h2 className="text-lg font-semibold">{t("welcome.solveTitle")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("welcome.solveDescription")}
          </p>
          <button
            type="button"
            onClick={handleSolve}
            disabled={solving}
            className="mt-3 min-h-touch rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 disabled:opacity-50"
          >
            {solving ? t("welcome.solveLoading") : t("welcome.solveAction")}
          </button>

          {lpError && (
            <div className="mt-4">
              {lpError.errors && lpError.errors.length > 0 ? (
                <RFC7807Panel
                  payload={{
                    title: lpError.title,
                    status: lpError.status,
                    detail: lpError.detail,
                    errors: lpError.errors,
                    next_action_url: lpError.next_action_url,
                  }}
                />
              ) : (
                <StatusCard
                  variant="error"
                  title={lpError.title}
                  description={lpError.detail}
                  ariaLabel="welcome.solve.error"
                />
              )}
            </div>
          )}

          {lpResult && lpResult.solution && (
            <div className="mt-4 rounded-md border border-success bg-success/5 p-4">
              <h3 className="font-semibold text-success">
                {t("welcome.solveDone")}（
                {(lpResult.solve_seconds * 1000).toFixed(1)} ms）
              </h3>
              <p className="mt-2 text-sm">
                <span className="font-medium">{t("welcome.minimumCost")}</span>
                <span className="font-mono text-lg text-primary">
                  ¥{lpResult.objective?.toFixed(2)}
                </span>
              </p>
              <p className="mt-2 text-sm">
                <span className="font-medium">{t("welcome.assignment")}</span>
              </p>
              <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                {JSON.stringify(lpResult.solution.x, null, 2)}
              </pre>
              <details className="mt-3 text-xs text-muted-foreground">
                <summary className="cursor-pointer">
                  {t("welcome.solverInfo")}
                </summary>
                <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono">
                  {JSON.stringify(lpResult.model_version, null, 2)}
                </pre>
                <p className="mt-1">
                  optimization_id:{" "}
                  <code className="font-mono">{lpResult.optimization_id}</code>
                </p>
              </details>
            </div>
          )}
        </section>

        {/* Story 1.1b ConfirmationModal — signup_success variant (FG1.1) */}
        <ConfirmationModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onConfirm={handleCopy}
          variant="signup_success"
          ariaLabel="modal.signup.success"
          title={t("welcome.modalTitle")}
          description={t("welcome.modalDescription")}
          body={
            <div>
              <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
                {cURLExample}
              </pre>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600"
                >
                  {copied ? t("welcome.copied") : t("welcome.copyCurl")}
                </button>
                <button
                  type="button"
                  onClick={handlePostman}
                  className="min-h-touch rounded-md border border-primary bg-background px-4 py-2 text-sm text-primary hover:bg-primary/5"
                >
                  {t("welcome.importPostman")}
                </button>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                {t("welcome.apiKeyWarning")}
              </p>
            </div>
          }
          confirmLabel={t("welcome.startUsing")}
          cancelLabel={t("common.later")}
        />

        <section className="mt-6 rounded-lg border border-border bg-background p-6">
          <h2 className="font-semibold">{t("welcome.nextTitle")}</h2>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <a href="/algorithms" className="text-primary hover:underline">
                {t("welcome.browseAlgorithms")}
              </a>
            </li>
            <li>
              <Link
                href={EXCEL_CONSOLE_URL}
                data-testid="welcome-excel-upload-link"
                className="text-primary hover:underline"
              >
                {t("welcome.uploadExcel")}
              </Link>
            </li>
            <li>
              <a href={QUICKSTART_URL} className="text-primary hover:underline">
                {t("welcome.quickstart")}
              </a>
            </li>
            <li>
              <a href="/console/billing" className="text-primary hover:underline">
                {t("welcome.credits")}
              </a>
            </li>
          </ul>
        </section>
      </div>
    </main>
  );
}
