// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  signup: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  signup: mocks.signup,
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status: number;
    title: string;
    detail: string;
    errors?: unknown[];
    next_action_url?: string;
    constructor(payload: {
      status: number;
      title: string;
      detail: string;
      errors?: unknown[];
      next_action_url?: string;
    }) {
      super(payload.detail);
      this.status = payload.status;
      this.title = payload.title;
      this.detail = payload.detail;
      this.errors = payload.errors;
      this.next_action_url = payload.next_action_url;
    }
  },
}));

import SignupPage from "./page";

describe("SignupPage age gate", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.signup.mockReset();
    sessionStorage.clear();
  });

  it("shows guardian email for ages 14-18", () => {
    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText(/年龄/), {
      target: { value: "14" },
    });
    expect(screen.getByLabelText(/监护人邮箱/)).toBeTruthy();
  });

  it("keeps pending guardian users on auth surface", async () => {
    mocks.signup.mockResolvedValue({
      account_status: "pending_guardian_confirmation",
      user_id: "user-1",
      jwt_access: null,
      jwt_refresh: null,
      edu_tier: false,
      age_verified: false,
      guardian_email: "guardian@example.com",
      guardian_confirmation_url: "/auth/guardian-confirmation?token=t",
    });

    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText(/手机号/), {
      target: { value: "+8613800138000" },
    });
    fireEvent.change(screen.getByLabelText(/^邮箱/), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/年龄/), {
      target: { value: "14" },
    });
    fireEvent.change(screen.getByLabelText(/监护人邮箱/), {
      target: { value: "guardian@example.com" },
    });
    fireEvent.click(screen.getByText(/立即注册/));

    await waitFor(() =>
      expect(screen.getByText("等待监护人确认")).toBeTruthy(),
    );
    expect(mocks.push).not.toHaveBeenCalledWith("/welcome");
    expect(sessionStorage.getItem("jwt_access")).toBeNull();
    expect(sessionStorage.getItem("user_id")).toBeNull();
    const anonymousOnboarding = JSON.parse(
      sessionStorage.getItem("opticloud:onboarding:anonymous") ?? "{}",
    ) as { completedSteps?: string[]; lastCompletedStep?: string | null };
    expect(anonymousOnboarding.completedSteps).toEqual([]);
    expect(anonymousOnboarding.lastCompletedStep).toBeNull();
  });
});
