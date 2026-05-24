// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requestOTP: vi.fn(),
  login: vi.fn(),
  push: vi.fn(),
  OptiCloudClientError: class MockOptiCloudClientError extends Error {
    status: number;
    title: string;
    detail: string;
    errors?: Array<{
      field_path: string;
      value: unknown;
      constraint: string;
      remediation_hint_key: string;
    }>;
    next_action_url?: string;

    constructor(payload: {
      status: number;
      title: string;
      detail: string;
      errors?: Array<{
        field_path: string;
        value: unknown;
        constraint: string;
        remediation_hint_key: string;
      }>;
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: mocks.OptiCloudClientError,
  requestOTP: mocks.requestOTP,
  login: mocks.login,
}));

import LoginPage from "./page";

describe("LoginPage frozen appeal CTA", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.requestOTP.mockReset();
    mocks.login.mockReset();
    sessionStorage.clear();
  });

  it("renders appeal CTA for frozen auth errors", async () => {
    mocks.requestOTP.mockRejectedValue(
      new mocks.OptiCloudClientError({
        status: 403,
        title: "账户已冻结",
        detail: "account frozen",
        errors: [
          {
            field_path: "account",
            value: null,
            constraint: "frozen",
            remediation_hint_key: "auth.frozen.appeal",
          },
        ],
        next_action_url:
          "/auth/frozen-appeal?phone=%2B8613800138000&email=user%40example.com",
      }),
    );

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("手机号"), { target: { value: "+8613800138000" } });
    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送 OTP →" }));

    await waitFor(() => {
      expect(screen.getByTestId("rfc7807-panel")).toBeTruthy();
    });
    expect(screen.getByTestId("next-action-url").getAttribute("href")).toBe(
      "/auth/frozen-appeal?phone=%2B8613800138000&email=user%40example.com",
    );
    expect(screen.getByTestId("frozen-appeal-cta").getAttribute("href")).toBe(
      "/auth/frozen-appeal?phone=%2B8613800138000&email=user%40example.com",
    );
  });
});
