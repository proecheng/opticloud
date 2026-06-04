// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  submitLegalInquiry: vi.fn(),
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status: number;
    title: string;
    detail: string;
    constructor(payload: { status: number; title: string; detail: string }) {
      super(payload.detail);
      this.status = payload.status;
      this.title = payload.title;
      this.detail = payload.detail;
    }
  },
  submitLegalInquiry: mocks.submitLegalInquiry,
}));

import LegalInquiryPage from "./page";

function renderPageWithJwt(jwt = "jwt-team"): void {
  sessionStorage.setItem("jwt_access", jwt);
  render(<LegalInquiryPage />);
}

function fillValidForm(message = "Please review our DPA and data export terms."): void {
  fireEvent.change(screen.getByLabelText("联系邮箱"), {
    target: { value: "legal@example.com" },
  });
  fireEvent.change(screen.getByLabelText("公司/组织"), {
    target: { value: "ACME Optimization" },
  });
  fireEvent.change(screen.getByLabelText("主题"), {
    target: { value: "DPA review" },
  });
  fireEvent.change(screen.getByLabelText("问询内容"), {
    target: { value: message },
  });
}

describe("LegalInquiryPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.submitLegalInquiry.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("redirects to login when jwt is missing", async () => {
    render(<LegalInquiryPage />);

    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith("/auth/login");
    });
    expect(mocks.submitLegalInquiry).not.toHaveBeenCalled();
  });

  it("validates required fields before submitting", async () => {
    renderPageWithJwt();

    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(await screen.findByText("请输入有效联系邮箱。")).toBeTruthy();
    expect(mocks.submitLegalInquiry).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("联系邮箱"), {
      target: { value: "legal@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(await screen.findByText("请输入至少 3 个字符的主题。")).toBeTruthy();
    expect(mocks.submitLegalInquiry).not.toHaveBeenCalled();
  });

  it("validates maximum field lengths before submitting", async () => {
    renderPageWithJwt();
    fireEvent.change(screen.getByLabelText("联系邮箱"), {
      target: { value: "legal@example.com" },
    });
    fireEvent.change(screen.getByLabelText("公司/组织"), {
      target: { value: "A".repeat(161) },
    });
    fireEvent.change(screen.getByLabelText("主题"), {
      target: { value: "DPA review" },
    });
    fireEvent.change(screen.getByLabelText("问询内容"), {
      target: { value: "Please review our DPA and data export terms." },
    });

    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(await screen.findByText("公司/组织不能超过 160 个字符。")).toBeTruthy();
    expect(mocks.submitLegalInquiry).not.toHaveBeenCalled();
  });

  it("submits and renders only safe SLA/ticket fields without storage writes or message echo", async () => {
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    const rawMessage = "Please review our DPA and data export terms.";
    mocks.submitLegalInquiry.mockResolvedValue({
      inquiry_id: "8a0b30c1-7008-4d06-bf0b-e9d22270e66d",
      status: "submitted",
      submitted_at: "2026-06-04T02:00:00Z",
      sla_due_at: "2026-06-05T02:00:00Z",
      sla_hours: 24,
      linear_ticket: {
        provider: "linear",
        status: "pending",
        reference: "OPTI-LEGAL-20260604-ABC123",
      },
    });
    renderPageWithJwt();
    storageSet.mockClear();
    fillValidForm(rawMessage);

    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(mocks.submitLegalInquiry).toHaveBeenCalledWith(
      "jwt-team",
      expect.objectContaining({
        category: "pipl",
        contact_email: "legal@example.com",
        company_name: "ACME Optimization",
        subject: "DPA review",
        message: rawMessage,
        urgency: "normal",
      }),
    );
    expect(await screen.findByText("OPTI-LEGAL-20260604-ABC123")).toBeTruthy();
    expect(screen.getByText("submitted")).toBeTruthy();
    expect(screen.getByText("pending")).toBeTruthy();
    expect(screen.queryByText(rawMessage)).toBeNull();
    expect(screen.queryByText("DPA review")).toBeNull();
    expect((screen.getByLabelText("问询内容") as HTMLTextAreaElement).value).toBe("");
    expect(storageSet).not.toHaveBeenCalled();
  });

  it("renders safe Team+ entitlement error", async () => {
    mocks.submitLegalInquiry.mockRejectedValue(
      new Error("unexpected"),
    );
    renderPageWithJwt();
    fillValidForm();
    mocks.submitLegalInquiry.mockRejectedValueOnce({
      status: 403,
      title: "Team plan required",
      detail: "legal inquiry SLA is available only to active Team or Enterprise plans",
    });

    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(await screen.findByText("当前账号没有 active Team 或 Enterprise 法务问询 SLA。")).toBeTruthy();
    expect((screen.getByLabelText("问询内容") as HTMLTextAreaElement).value).toBe("");
    expect((screen.getByLabelText("主题") as HTMLInputElement).value).toBe("");
  });

  it("renders safe idempotency conflict error", async () => {
    renderPageWithJwt();
    fillValidForm();
    mocks.submitLegalInquiry.mockRejectedValueOnce({
      status: 409,
      title: "Idempotency Conflict",
      detail: "Idempotency-Key was reused with a different request body",
    });

    fireEvent.click(screen.getByRole("button", { name: "提交法务问询" }));

    expect(await screen.findByText("该提交凭证已被其他内容使用，请重新提交。")).toBeTruthy();
  });
});
