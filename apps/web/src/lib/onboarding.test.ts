import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ONBOARDING_STEP_IDS,
  buildOnboardingSteps,
  createInitialOnboardingState,
  getOnboardingStorageKey,
  loadOnboardingState,
  markOnboardingStep,
  saveOnboardingState,
  shouldResumeOnboardingAfterLogin,
  shouldShowOnboardingSupport,
} from "./onboarding";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => Array.from(values.keys())[index] ?? null,
    removeItem: (key: string) => {
      values.delete(key);
    },
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
}

describe("onboarding state", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-23T00:00:00Z"));
  });

  it("creates a session-scoped initial state", () => {
    const state = createInitialOnboardingState("user-1");

    expect(state.userKey).toBe("user-1");
    expect(state.lastCompletedStep).toBeNull();
    expect(state.completedSteps).toEqual([]);
    expect(state.completed).toBe(false);
    expect(state.supportPromptShown).toBe(false);
  });

  it("builds current/completed/pending wizard steps", () => {
    const state = markOnboardingStep(
      createInitialOnboardingState("user-1"),
      "verify",
      "complete",
    );

    const steps = buildOnboardingSteps(state);

    expect(steps.map((step) => step.state)).toEqual([
      "completed",
      "completed",
      "current",
      "pending",
      "pending",
    ]);
  });

  it("preserves completed progress when a later step is skipped", () => {
    let state = markOnboardingStep(
      createInitialOnboardingState("user-1"),
      "api-key",
      "complete",
    );
    state = markOnboardingStep(state, "postman", "skip");

    const steps = buildOnboardingSteps(state);

    expect(steps[2]?.state).toBe("completed");
    expect(steps[3]?.state).toBe("skipped");
    expect(state.completed).toBe(false);
  });

  it("does not implicitly complete a skipped middle step", () => {
    let state = markOnboardingStep(
      createInitialOnboardingState("user-1"),
      "api-key",
      "complete",
    );
    state = markOnboardingStep(state, "postman", "skip");
    state = markOnboardingStep(state, "hello-world", "complete");

    const steps = buildOnboardingSteps(state);

    expect(steps.map((step) => step.state)).toEqual([
      "completed",
      "completed",
      "completed",
      "skipped",
      "completed",
    ]);
    expect(state.completed).toBe(true);
  });

  it("marks onboarding complete only after hello-world completes", () => {
    const state = markOnboardingStep(
      createInitialOnboardingState("user-1"),
      "hello-world",
      "complete",
    );

    expect(state.completed).toBe(true);
    expect(state.completedAt).toBe("2026-05-23T00:00:00.000Z");
  });

  it("shows support after five minutes only once", () => {
    let state = createInitialOnboardingState("user-1");

    vi.advanceTimersByTime(4 * 60 * 1000 + 59_000);
    expect(shouldShowOnboardingSupport(state)).toBe(false);

    vi.advanceTimersByTime(1_000);
    expect(shouldShowOnboardingSupport(state)).toBe(true);

    state = { ...state, supportPromptShown: true };
    expect(shouldShowOnboardingSupport(state)).toBe(false);
  });

  it("uses a stable storage key for user or anonymous sessions", () => {
    expect(getOnboardingStorageKey("user-1")).toBe("opticloud:onboarding:user-1");
    expect(getOnboardingStorageKey(null)).toBe("opticloud:onboarding:anonymous");
  });

  it("persists anonymous signup progress across refresh", () => {
    const storage = createMemoryStorage();
    const skipped = markOnboardingStep(
      createInitialOnboardingState(null),
      "verify",
      "skip",
    );

    saveOnboardingState(storage, skipped);
    const loaded = loadOnboardingState(storage, null);

    expect(loaded.userKey).toBe("anonymous");
    expect(loaded.skippedSteps).toEqual(["verify"]);
  });

  it("detects login resume from URL state or persisted user progress", () => {
    const storage = createMemoryStorage();

    expect(
      shouldResumeOnboardingAfterLogin(
        new URLSearchParams("onboarding=1"),
        storage,
        "user-1",
      ),
    ).toBe(true);
    expect(
      shouldResumeOnboardingAfterLogin(new URLSearchParams(), storage, "user-1"),
    ).toBe(false);

    saveOnboardingState(storage, createInitialOnboardingState("user-1"));

    expect(
      shouldResumeOnboardingAfterLogin(new URLSearchParams(), storage, "user-1"),
    ).toBe(true);
  });

  it("exports the expected five step ids in order", () => {
    expect(ONBOARDING_STEP_IDS).toEqual([
      "signup",
      "verify",
      "api-key",
      "postman",
      "hello-world",
    ]);
  });
});
