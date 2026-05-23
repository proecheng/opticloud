import type { SignupWizardStep, SignupWizardStepState } from "@opticloud/ui";

export const ONBOARDING_STEP_IDS = [
  "signup",
  "verify",
  "api-key",
  "postman",
  "hello-world",
] as const;

export type OnboardingStepId = (typeof ONBOARDING_STEP_IDS)[number];

export interface OnboardingState {
  userKey: string;
  startedAt: string;
  lastCompletedStep: OnboardingStepId | null;
  completedSteps: OnboardingStepId[];
  skippedSteps: OnboardingStepId[];
  completed: boolean;
  completedAt: string | null;
  supportPromptShown: boolean;
  dismissed: boolean;
}

export const ONBOARDING_SUPPORT_DELAY_MS = 5 * 60 * 1000;

export const DEFAULT_ONBOARDING_STEP_LABELS: Record<OnboardingStepId, string> = {
  signup: "注册",
  verify: "验证",
  "api-key": "拿 API Key",
  postman: "Postman 导入",
  "hello-world": "Hello World 跑通",
};

function nowIso(): string {
  return new Date().toISOString();
}

function stepIndex(step: OnboardingStepId | null): number {
  return step ? ONBOARDING_STEP_IDS.indexOf(step) : -1;
}

export function getOnboardingStorageKey(userKey: string | null | undefined): string {
  return `opticloud:onboarding:${userKey || "anonymous"}`;
}

export function createInitialOnboardingState(userKey: string | null): OnboardingState {
  return {
    userKey: userKey || "anonymous",
    startedAt: nowIso(),
    lastCompletedStep: null,
    completedSteps: [],
    skippedSteps: [],
    completed: false,
    completedAt: null,
    supportPromptShown: false,
    dismissed: false,
  };
}

export function safeParseOnboardingState(
  value: string | null,
  userKey: string | null,
): OnboardingState {
  if (!value) return createInitialOnboardingState(userKey);
  try {
    const parsed = JSON.parse(value) as Partial<OnboardingState>;
    const initial = createInitialOnboardingState(userKey);
    return {
      ...initial,
      ...parsed,
      userKey: parsed.userKey || initial.userKey,
      completedSteps: Array.isArray(parsed.completedSteps)
        ? parsed.completedSteps.filter((step): step is OnboardingStepId =>
            ONBOARDING_STEP_IDS.includes(step as OnboardingStepId),
          )
        : parsed.lastCompletedStep
          ? ONBOARDING_STEP_IDS.slice(0, stepIndex(parsed.lastCompletedStep) + 1)
          : [],
      skippedSteps: Array.isArray(parsed.skippedSteps)
        ? parsed.skippedSteps.filter((step): step is OnboardingStepId =>
            ONBOARDING_STEP_IDS.includes(step as OnboardingStepId),
          )
        : [],
    };
  } catch {
    return createInitialOnboardingState(userKey);
  }
}

export function loadOnboardingState(storage: Storage, userKey: string | null): OnboardingState {
  return safeParseOnboardingState(
    storage.getItem(getOnboardingStorageKey(userKey)),
    userKey,
  );
}

export function saveOnboardingState(storage: Storage, state: OnboardingState): void {
  storage.setItem(getOnboardingStorageKey(state.userKey), JSON.stringify(state));
}

export function shouldResumeOnboardingAfterLogin(
  searchParams: URLSearchParams,
  storage: Storage,
  userKey: string,
): boolean {
  return (
    searchParams.get("onboarding") === "1" ||
    storage.getItem(getOnboardingStorageKey(userKey)) !== null
  );
}

export function markOnboardingStep(
  state: OnboardingState,
  step: OnboardingStepId,
  action: "complete" | "skip",
): OnboardingState {
  const next: OnboardingState = {
    ...state,
    skippedSteps: state.skippedSteps.filter((skipped) => skipped !== step),
  };

  if (action === "skip") {
    return {
      ...next,
      skippedSteps: Array.from(new Set([...next.skippedSteps, step])),
      dismissed: false,
    };
  }

  const impliedCompletedSteps = ONBOARDING_STEP_IDS.slice(0, stepIndex(step) + 1).filter(
    (id) => !next.skippedSteps.includes(id),
  );
  const completedSteps = Array.from(
    new Set([...next.completedSteps, ...impliedCompletedSteps]),
  );
  const contiguousCompleted = ONBOARDING_STEP_IDS.filter((id, index) =>
    ONBOARDING_STEP_IDS.slice(0, index + 1).every((candidate) =>
      completedSteps.includes(candidate),
    ),
  );
  const isComplete = step === "hello-world";
  return {
    ...next,
    completedSteps,
    lastCompletedStep: contiguousCompleted.at(-1) ?? null,
    completed: isComplete ? true : state.completed,
    completedAt: isComplete ? nowIso() : state.completedAt,
    dismissed: false,
  };
}

export function dismissOnboarding(state: OnboardingState): OnboardingState {
  return { ...state, dismissed: true };
}

export function markSupportPromptShown(state: OnboardingState): OnboardingState {
  return { ...state, supportPromptShown: true };
}

export function shouldShowOnboardingSupport(
  state: OnboardingState,
  now: Date = new Date(),
): boolean {
  if (state.completed || state.dismissed || state.supportPromptShown) return false;
  return now.getTime() - new Date(state.startedAt).getTime() >= ONBOARDING_SUPPORT_DELAY_MS;
}

export function buildOnboardingSteps(
  state: OnboardingState,
  stepLabels: Record<OnboardingStepId, string> = DEFAULT_ONBOARDING_STEP_LABELS,
): SignupWizardStep[] {
  const completed = new Set(state.completedSteps);
  const skipped = new Set(state.skippedSteps);
  let currentAssigned = false;

  return ONBOARDING_STEP_IDS.map((id, index) => {
    let stepState: SignupWizardStepState = "pending";
    if (completed.has(id)) {
      stepState = "completed";
    } else if (skipped.has(id)) {
      stepState = "skipped";
    } else if (!currentAssigned && !state.completed && !state.dismissed) {
      stepState = "current";
      currentAssigned = true;
    }

    return {
      id,
      label: stepLabels[id],
      state: stepState,
    };
  });
}
