// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getAccountDeletionStatus: vi.fn(),
  listAccountMergeProposals: vi.fn(),
  requestAccountDeletion: vi.fn(),
  createAccountMergeProposal: vi.fn(),
  acceptAccountMergeProposal: vi.fn(),
  getNotificationPreferences: vi.fn(),
  putNotificationPreferences: vi.fn(),
  OptiCloudClientError: class MockOptiCloudClientError extends Error {
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
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: mocks.OptiCloudClientError,
  getAccountDeletionStatus: mocks.getAccountDeletionStatus,
  listAccountMergeProposals: mocks.listAccountMergeProposals,
  requestAccountDeletion: mocks.requestAccountDeletion,
  createAccountMergeProposal: mocks.createAccountMergeProposal,
  acceptAccountMergeProposal: mocks.acceptAccountMergeProposal,
  getNotificationPreferences: mocks.getNotificationPreferences,
  putNotificationPreferences: mocks.putNotificationPreferences,
}));

import AccountPage from "./page";

const accountStatus = {
  status: "none",
  user_id_snapshot: null,
  requested_at: null,
  hard_delete_at: null,
  completed_at: null,
  grace_period_days: 7,
};

const defaultPreferences = {
  items: [
    {
      event_type: "billing.budget.alerted",
      email: true,
      webhook: false,
      in_app: true,
      webhook_url: null,
      webhook_url_configured: false,
      channels: ["email", "in_app"],
    },
    {
      event_type: "billing.budget.paused",
      email: true,
      webhook: false,
      in_app: true,
      webhook_url: null,
      webhook_url_configured: false,
      channels: ["email", "in_app"],
    },
  ],
};

const savedPreferences = {
  items: [
    {
      event_type: "billing.budget.alerted",
      email: false,
      webhook: false,
      in_app: true,
      webhook_url: null,
      webhook_url_configured: false,
      channels: ["in_app"],
    },
    {
      event_type: "billing.budget.paused",
      email: true,
      webhook: true,
      in_app: false,
      webhook_url: "https://hooks.example.com/opticloud",
      webhook_url_configured: true,
      channels: ["email", "webhook"],
    },
  ],
};

function seedAuthStorage(): void {
  sessionStorage.setItem("jwt_access", "jwt-test");
  sessionStorage.setItem("user_id", "98cf1268-30d3-4f25-9a1f-f167b441d000");
}

describe("AccountPage notification preferences", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.getAccountDeletionStatus.mockReset();
    mocks.listAccountMergeProposals.mockReset();
    mocks.requestAccountDeletion.mockReset();
    mocks.createAccountMergeProposal.mockReset();
    mocks.acceptAccountMergeProposal.mockReset();
    mocks.getNotificationPreferences.mockReset();
    mocks.putNotificationPreferences.mockReset();
    mocks.getAccountDeletionStatus.mockResolvedValue(accountStatus);
    mocks.listAccountMergeProposals.mockResolvedValue([]);
    mocks.getNotificationPreferences.mockResolvedValue(defaultPreferences);
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    render(<AccountPage />);

    expect(mocks.push).toHaveBeenCalledWith("/auth/login");
  });

  it("loads account settings and notification preferences independently", async () => {
    seedAuthStorage();

    render(<AccountPage />);

    expect(await screen.findByText("账户删除")).toBeTruthy();
    expect(await screen.findByText("通知偏好")).toBeTruthy();
    expect(screen.getByText("预算达到提醒阈值")).toBeTruthy();
    expect(mocks.getAccountDeletionStatus).toHaveBeenCalledWith("jwt-test");
    expect(mocks.listAccountMergeProposals).toHaveBeenCalledWith("jwt-test");
    expect(mocks.getNotificationPreferences).toHaveBeenCalledWith("jwt-test");
  });

  it("saves preferences and rehydrates the form from the server response", async () => {
    seedAuthStorage();
    mocks.putNotificationPreferences.mockResolvedValue(savedPreferences);

    render(<AccountPage />);
    const notificationSection = (await screen.findByText("通知偏好")).closest("section");
    expect(notificationSection).not.toBeNull();
    const section = notificationSection as HTMLElement;
    const fields = within(section).getAllByRole("group");
    const alerted = fields[0]!;
    const paused = fields[1]!;

    fireEvent.click(within(alerted).getByLabelText("邮件"));
    fireEvent.click(within(paused).getByLabelText("站内"));
    fireEvent.click(within(paused).getByLabelText("Webhook"));
    fireEvent.change(within(paused).getByLabelText("Webhook URL"), {
      target: { value: "https://hooks.example.com/opticloud" },
    });
    fireEvent.click(within(section).getByRole("button", { name: "保存通知偏好" }));

    await waitFor(() => {
      expect(mocks.putNotificationPreferences).toHaveBeenCalledWith("jwt-test", {
        items: [
          {
            event_type: "billing.budget.alerted",
            email: false,
            webhook: false,
            in_app: true,
            webhook_url: null,
          },
          {
            event_type: "billing.budget.paused",
            email: true,
            webhook: true,
            in_app: false,
            webhook_url: "https://hooks.example.com/opticloud",
          },
        ],
      });
    });
    expect((within(paused).getByLabelText("Webhook URL") as HTMLInputElement).value).toBe(
      "https://hooks.example.com/opticloud",
    );
    expect(within(section).getByText(/预算自动暂停扣费=邮件、Webhook/)).toBeTruthy();
  });

  it("preserves edited form values when preference save fails", async () => {
    seedAuthStorage();
    mocks.putNotificationPreferences.mockRejectedValue(
      new mocks.OptiCloudClientError({
        status: 422,
        title: "Request failed",
        detail: "webhook_url must use https",
      }),
    );

    render(<AccountPage />);
    const notificationSection = (await screen.findByText("通知偏好")).closest("section");
    expect(notificationSection).not.toBeNull();
    const section = notificationSection as HTMLElement;
    const paused = within(section).getAllByRole("group")[1]!;
    fireEvent.click(within(paused).getByLabelText("Webhook"));
    fireEvent.change(within(paused).getByLabelText("Webhook URL"), {
      target: { value: "http://localhost/hook" },
    });
    fireEvent.click(within(section).getByRole("button", { name: "保存通知偏好" }));

    expect(await within(section).findByText(/webhook_url must use https/)).toBeTruthy();
    expect((within(paused).getByLabelText("Webhook URL") as HTMLInputElement).value).toBe(
      "http://localhost/hook",
    );
    expect(screen.getByText("账户删除")).toBeTruthy();
    expect(screen.getByText("账户合并")).toBeTruthy();
  });

  it("keeps account controls visible when notification loading fails and avoids storage writes", async () => {
    seedAuthStorage();
    mocks.getNotificationPreferences.mockRejectedValue(new Error("preferences unavailable"));
    const storageSet = vi.spyOn(Storage.prototype, "setItem");

    render(<AccountPage />);

    expect(await screen.findByText("账户删除")).toBeTruthy();
    expect(screen.getByText("账户合并")).toBeTruthy();
    expect(await screen.findByText(/preferences unavailable/)).toBeTruthy();
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/notification|preference|webhook/i),
      expect.any(String),
    );
  });
});
