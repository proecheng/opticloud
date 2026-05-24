import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acceptFrozenAppeal,
  getFrozenAppeal,
  startFrozenAppeal,
  submitFrozenAppealProposal,
} from "./api";

describe("frozen appeal API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs frozen appeal start with phone and email", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          appeal_id: "a5d3d7f6-0000-4000-8000-000000000001",
          status: "started",
          user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
          tracking_token: "tracking-token",
          tracking_url: "/auth/frozen-appeal?appeal_id=a5d3d7f6-0000-4000-8000-000000000001",
          expires_at: "2026-05-24T12:00:00Z",
          risk_summary: {
            total_flag_count: 1,
            latest_rule_codes: ["ip_24_share"],
            latest_flag_at: "2026-05-24T11:00:00Z",
            risk_score: 0.35,
          },
          proposal: null,
          next_action: "submit_proposal",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await startFrozenAppeal({
      phone: "+8613800138000",
      email: "frozen@example.com",
    });

    expect(result.status).toBe("started");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/frozen-appeals/start");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
    expect(String(init?.body)).toContain("+8613800138000");
  });

  it("GETs frozen appeal with tracking token query", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          appeal_id: "a5d3d7f6-0000-4000-8000-000000000001",
          status: "started",
          expires_at: "2026-05-24T12:00:00Z",
          last_viewed_at: "2026-05-24T11:30:00Z",
          risk_summary: {
            total_flag_count: 1,
            latest_rule_codes: ["ip_24_share"],
            latest_flag_at: "2026-05-24T11:00:00Z",
            risk_score: 0.35,
          },
          proposal: null,
          next_action: "submit_proposal",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getFrozenAppeal("a5d3d7f6-0000-4000-8000-000000000001", "tracking-token");

    expect(result.next_action).toBe("submit_proposal");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toContain("/v1/auth/frozen-appeals/a5d3d7f6-0000-4000-8000-000000000001");
    expect(url).toContain("tracking_token=tracking-token");
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
  });

  it("POSTs proposal submission with tracking token in body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          appeal_id: "a5d3d7f6-0000-4000-8000-000000000001",
          status: "proposal_submitted",
          expires_at: "2026-05-24T12:00:00Z",
          last_viewed_at: null,
          risk_summary: {
            total_flag_count: 1,
            latest_rule_codes: ["ip_24_share"],
            latest_flag_at: "2026-05-24T11:00:00Z",
            risk_score: 0.35,
          },
          proposal: {
            id: "b5d3d7f6-0000-4000-8000-000000000001",
            requester_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
            primary_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
            duplicate_user_ids: ["b26a756e-2294-4cc3-a764-9ef289f4c100"],
            evidence: { reason: "我帮室友注册" },
            status: "auto_approved",
            review_mode: "auto",
            auto_score: 0.8,
            review_due_at: "2026-05-24T12:00:00Z",
            reviewed_at: null,
            reviewed_by: null,
            decision_reason: null,
            accepted_at: null,
            created_at: "2026-05-24T11:00:00Z",
            updated_at: "2026-05-24T11:00:00Z",
            next_action: "accept_merge",
          },
          next_action: "accept_merge",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await submitFrozenAppealProposal("a5d3d7f6-0000-4000-8000-000000000001", {
      tracking_token: "tracking-token",
      duplicate_user_ids: ["b26a756e-2294-4cc3-a764-9ef289f4c100"],
      reason: "我帮室友注册",
      contact_email: "review@example.com",
      team_size: 2,
    });

    expect(result.next_action).toBe("accept_merge");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toContain("/v1/auth/frozen-appeals/a5d3d7f6-0000-4000-8000-000000000001/proposal");
    expect(init?.method).toBe("POST");
    expect(String(init?.body)).toContain("tracking-token");
  });

  it("POSTs accept request with tracking token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          appeal_id: "a5d3d7f6-0000-4000-8000-000000000001",
          status: "accepted",
          expires_at: "2026-05-24T12:00:00Z",
          last_viewed_at: null,
          risk_summary: {
            total_flag_count: 1,
            latest_rule_codes: ["ip_24_share"],
            latest_flag_at: "2026-05-24T11:00:00Z",
            risk_score: 0.35,
          },
          proposal: {
            id: "b5d3d7f6-0000-4000-8000-000000000001",
            requester_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
            primary_user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
            duplicate_user_ids: ["b26a756e-2294-4cc3-a764-9ef289f4c100"],
            evidence: { reason: "我帮室友注册" },
            status: "accepted",
            review_mode: "auto",
            auto_score: 0.8,
            review_due_at: "2026-05-24T12:00:00Z",
            reviewed_at: null,
            reviewed_by: null,
            decision_reason: null,
            accepted_at: "2026-05-24T11:30:00Z",
            created_at: "2026-05-24T11:00:00Z",
            updated_at: "2026-05-24T11:30:00Z",
            next_action: "completed",
          },
          next_action: "completed",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await acceptFrozenAppeal("a5d3d7f6-0000-4000-8000-000000000001", {
      tracking_token: "tracking-token",
    });

    expect(result.status).toBe("accepted");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toContain("/v1/auth/frozen-appeals/a5d3d7f6-0000-4000-8000-000000000001/accept");
    expect(init?.method).toBe("POST");
    expect(String(init?.body)).toContain("tracking-token");
  });
});
