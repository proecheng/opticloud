import { afterEach, describe, expect, it, vi } from "vitest";

import { getAccountDeletionStatus, requestAccountDeletion } from "./api";

describe("account deletion API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs current deletion status with bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "none",
          user_id_snapshot: null,
          requested_at: null,
          hard_delete_at: null,
          completed_at: null,
          grace_period_days: 7,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getAccountDeletionStatus("jwt-test");

    expect(result.status).toBe("none");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/account-deletion");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
  });

  it("POSTs account deletion request with bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "scheduled",
          user_id_snapshot: "4ba6ce0b-9c3a-454a-a4d1-83380ec9924d",
          requested_at: "2026-05-20T00:00:00Z",
          hard_delete_at: "2026-05-27T00:00:00Z",
          completed_at: null,
          grace_period_days: 7,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await requestAccountDeletion("jwt-test");

    expect(result.status).toBe("scheduled");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/account-deletion");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
  });
});
