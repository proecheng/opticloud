// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requestOTP: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  requestOTP: mocks.requestOTP,
  login: vi.fn(),
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

import { OptiCloudClientError } from "@/lib/api";
import LoginPage from "./page";

describe("LoginPage age gate", () => {
  beforeEach(() => {
    mocks.requestOTP.mockReset();
    mocks.push.mockReset();
  });

  it("shows guardian confirmation copy for pending age gate", async () => {
    mocks.requestOTP.mockRejectedValue(
      new OptiCloudClientError({
        status: 403,
        title: "Forbidden",
        detail: "age gate pending: finish guardian confirmation first",
      }),
    );

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/手机号/), {
      target: { value: "+8613800138000" },
    });
    fireEvent.change(screen.getByLabelText(/邮箱/), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByText(/发送 OTP/));

    await waitFor(() =>
      expect(
        screen.getByText(
          "Age gate pending, finish guardian confirmation first",
        ),
      ).toBeTruthy(),
    );
  });
});

describe("LoginPage frozen appeal CTA", () => {
  beforeEach(() => {
    mocks.requestOTP.mockReset();
    mocks.push.mockReset();
  });

  it("links frozen users to the appeal flow when backend returns next_action_url", async () => {
    mocks.requestOTP.mockRejectedValue(
      new OptiCloudClientError({
        status: 403,
        title: "Account Frozen",
        detail: "account frozen",
        next_action_url: "/auth/appeal",
      }),
    );

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/手机号/), {
      target: { value: "+8613800138000" },
    });
    fireEvent.change(screen.getByLabelText(/邮箱/), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByText(/发送 OTP/));

    await waitFor(() => expect(screen.getByText("提交冻结申诉")).toBeTruthy());
    fireEvent.click(screen.getByText("提交冻结申诉"));
    expect(mocks.push).toHaveBeenCalledWith("/auth/appeal");
  });
});
