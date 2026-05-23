import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acceptAccountMergeProposal,
  createAccountMergeProposal,
  listAccountMergeProposals,
} from "./api";

const responseBody = {
  id: "9c8835fd-1245-4d7e-bd96-6a1b2d5a6166",
  requester_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
  primary_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
  duplicate_user_ids: ["b26a756e-2294-4cc3-a764-9ef289f4c100"],
  evidence: { reason: "我帮室友注册" },
  status: "auto_approved",
  review_mode: "auto",
  auto_score: 0.8,
  review_due_at: "2026-05-21T00:00:00Z",
  reviewed_at: null,
  reviewed_by: null,
  decision_reason: null,
  accepted_at: null,
  created_at: "2026-05-20T00:00:00Z",
  updated_at: "2026-05-20T00:00:00Z",
  next_action: "accept_merge",
};

describe("account merge API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs merge proposal with bearer token and body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(responseBody), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await createAccountMergeProposal("jwt-test", {
      primary_user_id: responseBody.primary_user_id,
      duplicate_user_ids: responseBody.duplicate_user_ids,
      evidence: {
        reason: "我帮室友注册",
        contact_email: "review@example.com",
        team_size: 2,
      },
    });

    expect(result.status).toBe("auto_approved");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/v1/auth/account-merge-proposals",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer jwt-test" }),
        body: expect.stringContaining(responseBody.primary_user_id),
      }),
    );
  });

  it("GETs merge proposals with bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([responseBody]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await listAccountMergeProposals("jwt-test");

    expect(result).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/v1/auth/account-merge-proposals",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer jwt-test" }),
      }),
    );
  });

  it("POSTs accept request using proposal id path and bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ...responseBody, status: "accepted" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await acceptAccountMergeProposal("jwt-test", responseBody.id);

    expect(result.status).toBe("accepted");
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8001/v1/auth/account-merge-proposals/${responseBody.id}/accept`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer jwt-test" }),
      }),
    );
  });
});
