// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "@/components/LocaleProvider";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  get: vi.fn(),
  submit: vi.fn(),
  accept: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => mocks.searchParams,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getRiskAppealStatus: mocks.get,
    submitRiskAppeal: mocks.submit,
    acceptRiskAppealMergeOffer: mocks.accept,
  };
});

import AppealPage from "./page";

const pendingStatus = {
  appeal_id: "00000000-0000-4000-8000-000000000001",
  status: "pending",
  review_mode: "manual_48h",
  submitted_at: "2026-05-25T00:00:00Z",
  sla_due_at: "2026-05-27T00:00:00Z",
  decided_at: null,
  decision: null,
  decision_reason: null,
  evidence_summary: [
    {
      rule_code: "ip_24_share",
      label_zh: "IP /24 同段",
      source: "auto",
      created_at: "2026-05-25T00:00:00Z",
      summary: "reason: test",
    },
  ],
  merge_offer: null,
  next_action_url: null,
};

const mergeStatus = {
  ...pendingStatus,
  status: "merge_offered",
  decision: "maintained",
  decision_reason: "risk maintained",
  merge_offer: {
    offer_type: "keep_one_account",
    title: "保留 1 个账号并恢复访问",
    description: "接受后当前冻结账号会恢复访问。",
    next_action: "accept_merge_to_resume",
  },
};

describe("AppealPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.get.mockReset();
    mocks.submit.mockReset();
    mocks.accept.mockReset();
    mocks.searchParams = new URLSearchParams();
  });

  it("submits an appeal and shows tracked pending status", async () => {
    mocks.submit.mockResolvedValue({
      appeal_id: pendingStatus.appeal_id,
      status: "pending",
      review_mode: "manual_48h",
      submitted_at: pendingStatus.submitted_at,
      sla_due_at: pendingStatus.sla_due_at,
      tracking_url: "/auth/appeal?token=tok-1",
      merge_offer: null,
    });
    mocks.get.mockResolvedValue(pendingStatus);

    render(<AppealPage />);
    fireEvent.change(screen.getByLabelText("手机号"), {
      target: { value: "+8613800138000" },
    });
    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("团队人数"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText("申诉说明"), {
      target: { value: "我们是三人团队共享实验室网络，请复核。" },
    });
    fireEvent.click(screen.getByText("提交申诉"));

    await waitFor(() =>
      expect(screen.getByText("申诉已提交，等待复核")).toBeTruthy(),
    );
    expect(mocks.submit).toHaveBeenCalledWith({
      phone: "+8613800138000",
      email: "user@example.com",
      reason: "我们是三人团队共享实验室网络，请复核。",
      team_size: 3,
      evidence: {},
    });
    expect(screen.getByText("IP /24 同段")).toBeTruthy();
  });

  it("loads token status and accepts a merge offer", async () => {
    mocks.searchParams = new URLSearchParams("token=tok-merge");
    mocks.get.mockResolvedValueOnce(mergeStatus).mockResolvedValueOnce({
      ...mergeStatus,
      status: "merge_accepted",
      decision: "merge_accepted",
      next_action_url: "/auth/login",
      merge_offer: null,
    });
    mocks.accept.mockResolvedValue({
      appeal_id: mergeStatus.appeal_id,
      status: "merge_accepted",
      decision: "merge_accepted",
      is_frozen: false,
      next_action_url: "/auth/login",
    });

    render(<AppealPage />);

    await waitFor(() =>
      expect(
        screen.getByText("复核维持原判，可接受合并提议"),
      ).toBeTruthy(),
    );
    fireEvent.click(screen.getByText("接受合并提议并恢复访问"));
    await waitFor(() => expect(screen.getByText("确认接受合并提议")).toBeTruthy());
    fireEvent.click(screen.getAllByText("接受合并提议并恢复访问")[1]);

    await waitFor(() =>
      expect(mocks.accept).toHaveBeenCalledWith(
        mergeStatus.appeal_id,
        "tok-merge",
      ),
    );
    expect(screen.getByText("已接受合并提议，账号已恢复")).toBeTruthy();
  });

  it("renders English copy", () => {
    render(
      <LocaleProvider initialLocale="en-US">
        <AppealPage />
      </LocaleProvider>,
    );

    expect(screen.getByText("Frozen account appeal")).toBeTruthy();
    expect(screen.getByText("Submit appeal")).toBeTruthy();
  });
});
