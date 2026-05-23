import { afterEach, describe, expect, it, vi } from "vitest";

import { signup } from "./api";

describe("signup API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends age fields and returns completed signup", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
          jwt_access: "jwt-access",
          jwt_refresh: "jwt-refresh",
          edu_tier: false,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await signup({
      phone: "+8613800138000",
      email: "adult@example.com",
      age_years: 18,
    });

    expect("jwt_access" in result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/v1/auth/signup",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          phone: "+8613800138000",
          email: "adult@example.com",
          age_years: 18,
        }),
      }),
    );
  });

  it("returns pending guardian consent response for 202", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "guardian_consent_required",
          request_id: "b26a756e-2294-4cc3-a764-9ef289f4c100",
          expires_in_seconds: 86400,
          guardian_email: "parent@example.com",
          dev_guardian_consent_token: "dev-token",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await signup({
      phone: "+8613800138001",
      email: "minor@example.com",
      age_years: 16,
      guardian_email: "parent@example.com",
    });

    expect(result).toEqual({
      status: "guardian_consent_required",
      request_id: "b26a756e-2294-4cc3-a764-9ef289f4c100",
      expires_in_seconds: 86400,
      guardian_email: "parent@example.com",
      dev_guardian_consent_token: "dev-token",
    });
  });
});
