// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  startFrozenAppeal: vi.fn(),
  getFrozenAppeal: vi.fn(),
  submitFrozenAppealProposal: vi.fn(),
  acceptFrozenAppeal: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => mocks.params,
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status = 400;
    title = "Bad Request";
    detail = "Request failed";
    errors: Array<{
      field_path: string;
      value: unknown;
      constraint: string;
      remediation_hint_key: string;
    }> = [];
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
      Object.assign(this, payload);
      this.errors = payload.errors ?? [];
    }
  },
  startFrozenAppeal: mocks.startFrozenAppeal,
  getFrozenAppeal: mocks.getFrozenAppeal,
  submitFrozenAppealProposal: mocks.submitFrozenAppealProposal,
  acceptFrozenAppeal: mocks.acceptFrozenAppeal,
}));

import FrozenAppealPage from "./page";

describe("FrozenAppealPage", () => {
  beforeEach(() => {
    mocks.startFrozenAppeal.mockReset();
    mocks.getFrozenAppeal.mockReset();
    mocks.submitFrozenAppealProposal.mockReset();
    mocks.acceptFrozenAppeal.mockReset();
    mocks.params = new URLSearchParams();
    sessionStorage.clear();
  });

  it("runs start -> submit -> accept happy path", async () => {
    mocks.startFrozenAppeal.mockResolvedValue({
      appeal_id: "appeal-1",
      status: "started",
      user_id: "user-1",
      tracking_token: "token-1",
      tracking_url: "/auth/frozen-appeal?appeal_id=appeal-1&tracking_token=token-1",
      expires_at: "2026-05-25T00:00:00Z",
      risk_summary: {
        total_flag_count: 1,
        latest_rule_codes: ["ip_24_share"],
        latest_flag_at: "2026-05-24T00:00:00Z",
        risk_score: 0.35,
      },
      proposal: null,
      next_action: "submit_proposal",
    });
    mocks.submitFrozenAppealProposal.mockResolvedValue({
      appeal_id: "appeal-1",
      status: "proposal_submitted",
      expires_at: "2026-05-25T00:00:00Z",
      last_viewed_at: null,
      risk_summary: {
        total_flag_count: 1,
        latest_rule_codes: ["ip_24_share"],
        latest_flag_at: "2026-05-24T00:00:00Z",
        risk_score: 0.35,
      },
      proposal: {
        id: "proposal-1",
        requester_user_id: "user-1",
        primary_user_id: "user-1",
        duplicate_user_ids: ["dup-1"],
        evidence: { reason: "我帮室友注册" },
        status: "auto_approved",
        review_mode: "auto",
        auto_score: 0.8,
        review_due_at: "2026-05-24T12:00:00Z",
        reviewed_at: null,
        reviewed_by: null,
        decision_reason: null,
        accepted_at: null,
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T00:00:00Z",
        next_action: "accept_merge",
      },
      next_action: "accept_merge",
    });
    mocks.acceptFrozenAppeal.mockResolvedValue({
      appeal_id: "appeal-1",
      status: "accepted",
      expires_at: "2026-05-25T00:00:00Z",
      last_viewed_at: null,
      risk_summary: {
        total_flag_count: 1,
        latest_rule_codes: ["ip_24_share"],
        latest_flag_at: "2026-05-24T00:00:00Z",
        risk_score: 0.35,
      },
      proposal: {
        id: "proposal-1",
        requester_user_id: "user-1",
        primary_user_id: "user-1",
        duplicate_user_ids: ["dup-1"],
        evidence: { reason: "我帮室友注册" },
        status: "accepted",
        review_mode: "auto",
        auto_score: 0.8,
        review_due_at: "2026-05-24T12:00:00Z",
        reviewed_at: null,
        reviewed_by: null,
        decision_reason: null,
        accepted_at: "2026-05-24T12:30:00Z",
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T12:30:00Z",
        next_action: "completed",
      },
      next_action: "completed",
    });

    render(<FrozenAppealPage />);

    fireEvent.change(screen.getByLabelText("手机号"), { target: { value: "+8613800138000" } });
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "开始申诉" }));

    await waitFor(() => {
      expect(screen.getByTestId("appeal-submit-form")).toBeTruthy();
    });
    fireEvent.change(screen.getByLabelText("重复账户 ID"), { target: { value: "dup-1" } });
    fireEvent.change(screen.getByLabelText("联系邮箱"), { target: { value: "review@example.com" } });
    fireEvent.change(screen.getByLabelText("申诉说明"), { target: { value: "我帮室友注册" } });
    fireEvent.click(screen.getByRole("button", { name: "提交提案" }));

    await waitFor(() => {
      expect(screen.getByTestId("accept-merge-button")).toBeTruthy();
    });
    fireEvent.click(screen.getByTestId("accept-merge-button"));

    await waitFor(() => {
      expect(mocks.acceptFrozenAppeal).toHaveBeenCalledWith("appeal-1", {
        tracking_token: "token-1",
      });
    });
  });
});
